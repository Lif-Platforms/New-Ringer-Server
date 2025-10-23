from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BasicStatusResponse(BaseModel):
    status: str

class FriendRequestResponse(BaseModel):
    Sender: str
    Recipient: str
    Request_Id: str
    Create_Time: datetime
    Message: Optional[str] = None