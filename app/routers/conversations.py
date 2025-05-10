from fastapi import APIRouter, Request, HTTPException
import app.auth as auth
from app.database import conversations
from app.websocket import live_updates

router = APIRouter()

@router.delete("/v1/remove/{conversation_id}")
async def remove_conversation_v2(request: Request, conversation_id: str):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

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