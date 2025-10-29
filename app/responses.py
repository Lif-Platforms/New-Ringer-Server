from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, Literal

class BasicStatusResponse(BaseModel):
    status: str

class FriendRequestResponse(BaseModel):
    Sender: str
    Recipient: str
    Request_Id: str
    Create_Time: datetime
    Message: Optional[str] = None

class Message(BaseModel):
    author: str
    text: str
    id: str
    type: str
    gifURL: str
    sendTime: datetime

class WsRequestResponse(BaseModel):
    msgType: Literal["RESPONSE"] = Field(default="RESPONSE", frozen=True)
    requestId: str
    statusCode: int
    message: Optional[str] = None

class WsNewMessageEvent(BaseModel):
    conversationId: str
    message: Message

class WsEvent(BaseModel):
    msgType: Literal["EVENT"] = Field(default="EVENT", frozen=True)
    eventType: str
    data: Any

class UserTypingEvent(BaseModel):
    conversationId: str
    user: str
    isTyping: bool