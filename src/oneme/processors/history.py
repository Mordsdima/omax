import pydantic
import json
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

        # Формируем ответ.
        # Парсер a23 в MAX-клиенте ждёт ВСЕГДА все 5 полей (messages,
        # forward, backward, pos, total). Если каких-то нет — клиент
        # бросает соединение и история не отображается.
        # ВАЖНО: forward/backward здесь = СКОЛЬКО СООБЩЕНИЙ ВЕРНУЛИ
        # (а не "сколько ещё осталось"). Если 0 — клиент игнорирует
        # массив messages и считает что "ничего нет".
        payload = {
            "messages": messages,
            "forward":  forward_count,          # сколько вернули вперёд
            "backward": backward_count,         # сколько вернули назад
            "pos":      0,                      # позиция курсора (offset)
            "total":    len(messages),          # всего в этой пачке
        }

        # Собираем пакет.
        # MAX 26.15.x: в switch-парсере cwb.c() (диспатч по полю u4d.d=short opcode)
        # обработчик CHAT_HISTORY (создание a23) висит на #int 51, а не 49.
        # opcode 49 в этом switch вообще отсутствует — пакет с ним игнорируется.
        # Поэтому отвечаем opcode=51 несмотря на то, что в нашем opcodes.py
        # CHAT_HISTORY=49 (это для роутинга запросов, а не для ответов).
        packet = self.proto.pack_packet(
            cmd=self.proto.CMD_OK, seq=seq, opcode=51, payload=payload
        )

        # Отправялем
        await self._send(writer, packet)