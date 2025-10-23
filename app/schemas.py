from pydantic import BaseModel
from typing import Optional

class AddFriendRequest(BaseModel):
    recipient: str
    message: Optional[str] = None