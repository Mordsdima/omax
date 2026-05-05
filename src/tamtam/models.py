import pydantic

class UserAgentModel(pydantic.BaseModel):
    deviceType: str
    appVersion: str
    osVersion: str = None
    timezone: str = None
    screen: str = None
    pushDeviceType: str = None
    locale: str = None
    deviceName: str
    deviceLocale: str = None

class HelloPayloadModel(pydantic.BaseModel):
    userAgent: UserAgentModel
    deviceId: str = None

class RequestCodePayloadModel(pydantic.BaseModel):
    phone: str

class VerifyCodePayloadModel(pydantic.BaseModel):
    verifyCode: str
    authTokenType: str = None
    token: str

class FinalAuthPayloadModel(pydantic.BaseModel):
    deviceType: str
    tokenType: str
    deviceId: str
    token: str

class LoginPayloadModel(pydantic.BaseModel):
    interactive: bool = None
    token: str

class SearchUsersPayloadModel(pydantic.BaseModel):
    contactIds: list

class PingPayloadModel(pydantic.BaseModel):
    interactive: bool

class ChatHistoryPayloadModel(pydantic.BaseModel):
    chatId: int
    backward: int

class UpdateProfilePayloadModel(pydantic.BaseModel):
    pass

class SearchChatsPayloadModel(pydantic.BaseModel):
    chatIds: list

class AssetsPayloadModel(pydantic.BaseModel):
    sync: int
    type: str = None
    userId: int = None

class GetCallTokenPayloadModel(pydantic.BaseModel):
    userId: int
    value: str

class GetCallHistoryPayloadModel(pydantic.BaseModel):
    forward: bool
    count: int

class ChatSubscribePayloadModel(pydantic.BaseModel):
    chatId: int
    subscribe: bool

class ContactListPayloadModel(pydantic.BaseModel):
    status: str
    count: int = None

class ContactPresencePayloadModel(pydantic.BaseModel):
    contactIds: list

class ContactUpdatePayloadModel(pydantic.BaseModel):
    action: str
    contactId: int
    firstName: str
    lastName: str = None

class TypingPayloadModel(pydantic.BaseModel):
    chatId: int
    type: str = None

class MessageModel(pydantic.BaseModel):
    isLive: bool = None
    detectShare: bool = None
    elements: list = None
    attaches: list = None
    cid: int = None
    text: str = None

class SendMessagePayloadModel(pydantic.BaseModel):
    userId: int = None
    chatId: int = None
    message: MessageModel