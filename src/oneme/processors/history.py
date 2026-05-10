import pydantic
import json
import time
from classes.baseprocessor import BaseProcessor
from oneme.models import ChatHistoryPayloadModel

class HistoryProcessors(BaseProcessor):
    async def chat_history(self, payload, seq, writer, senderId):
        """Обработчик получения истории чата"""
        # Валидируем данные пакета
        try:
            ChatHistoryPayloadModel.model_validate(payload)
        except pydantic.ValidationError as error:
            self.logger.error(f"Возникли ошибки при валидации пакета: {error}")
            await self._send_error(seq, self.opcodes.CHAT_HISTORY, self.error_types.INVALID_PAYLOAD, writer)
            return

        # Извлекаем данные из пакета
        chatId = payload.get("chatId")
        forward = payload.get("forward", 0)
        backward = payload.get("backward", 0)
        from_time = payload.get("from", 0)
        getMessages = payload.get("getMessages", True)
        getChat = payload.get("getChat", False)
        messages = []
        backward_count = 0
        forward_count = 0

        # Если пользователь хочет получить историю из избранного,
        # то выставляем в качестве ID чата отрицательный ID отправителя
        isFavourite = chatId == (senderId ^ senderId)
        if isFavourite:
            chatId = -senderId

        # Проверяем, существует ли чат
        async with self.db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Проверяем состоит ли пользователь в чате,
                # только в случае того, если это не избранное
                if not isFavourite:
                    await cursor.execute("SELECT * FROM chats WHERE id = %s", (chatId,))
                    chat = await cursor.fetchone()

                    # Выбрасываем ошибку, если чата нет
                    if not chat:
                        await self._send_error(seq, self.opcodes.CHAT_HISTORY, self.error_types.CHAT_NOT_FOUND, writer)
                        return

                    # Проверяем, является ли пользователь участником чата
                    participants = await self.tools.get_chat_participants(chatId, self.db_pool)
                    if int(senderId) not in participants:
                        await self._send_error(seq, self.opcodes.CHAT_HISTORY, self.error_types.CHAT_NOT_ACCESS, writer)
                        return

                # Если запрошены сообщения
                if getMessages:
                    if backward > 0:
                        await cursor.execute(
                            "SELECT * FROM messages WHERE chat_id = %s AND time < %s ORDER BY time ASC LIMIT %s",
                            (chatId, from_time, backward)
                        )

                        result = await cursor.fetchall()

                        for row in result:
                            messages.append(self.tools.build_message_dict(row, self.type))
                        backward_count = len(result)
                    if forward > 0:
                        await cursor.execute(
                            "SELECT * FROM messages WHERE chat_id = %s AND time > %s ORDER BY time ASC LIMIT %s",
                            (chatId, from_time, forward)
                        )

                        result = await cursor.fetchall()

                        for row in result:
                            messages.append(self.tools.build_message_dict(row, self.type))
                        forward_count = len(result)

        # Сортируем сообщения по времени
        messages.sort(key=lambda x: x["time"])

        # КОСТЫЛЬ: клиент MAX в fz2.b() фильтрует сообщения по условию
        # `message.time >= chat.createTime`. Если у пользователя чат был
        # создан недавно, а наши сообщения в БД старые — все они отбрасываются
        # (см. реверс defpackage.fz2.java:89). Сдвигаем time всех сообщений
        # на «сейчас минус 1 секунда * (N-i)», чтобы все были после createTime.
        if messages:
            now_ms = int(time.time() * 1000)
            n = len(messages)
            for i, m in enumerate(messages):
                m["time"] = now_ms - (n - 1 - i) * 1000   # самое новое = сейчас
                m["updateTime"] = m["time"]

        # Формируем ответ.
        # Реальный парсер ответа CHAT_HISTORY в MAX 26.15.x — это az2.j(),
        # который ждёт всего 3 поля:
        #   chat       — qs2-объект чата (опционально, если getChat=False)
        #   messages   — массив сообщений (jr4.a → u6h.Q для каждого)
        #   messageIds — Set<Long> списка id сообщений в этом ответе
        # Поля forward/backward/pos/total — это парсер a23 для CHAT_MEDIA,
        # к chat_history они не имеют отношения.
        payload = {
            "chat":       {},                            # qs2-объект чата (пустой)
            "messages":   messages,
            "messageIds": [m["id"] for m in messages],
        }

        # Собираем пакет
        packet = self.proto.pack_packet(
            cmd=self.proto.CMD_OK, seq=seq, opcode=self.opcodes.CHAT_HISTORY, payload=payload
        )

        # Отправялем
        await self._send(writer, packet)