from fastapi import APIRouter, HTTPException, Depends
from app.database import conversations
from app.websocket import live_updates
from app.auth import useAuth

router = APIRouter()

@router.delete("/v1/remove/{conversation_id}")
async def remove_conversation_v2(conversation_id: str, account = Depends(useAuth)):
    username = account[0]

    # Get conversation members to notify later
    members = await conversations.get_members(conversation_id)

    # Use database interface to remove conversation
    remove_status = await conversations.remove_conversation(conversation_id, username)

    # Check the status of the operation
    if remove_status == "OK":
        # Create a list of users to notify based on conversation members
        # This also excludes the user who made the request
        notify_users = []

        for member in members:
            if member != username:
                notify_users.append(member)

        # Send alert to members that conversation was deleted
        await live_updates.send_message(
            users=notify_users,
            message={
                "Type": "REMOVE_CONVERSATION",
                "Id": conversation_id
            }
        )

        return "Conversation Removed!"
    
    elif remove_status == "NO_PERMISSION":
        raise HTTPException(status_code=403, detail="No Permission!")
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error!")