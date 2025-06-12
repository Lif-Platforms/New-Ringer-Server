from fastapi import APIRouter, Request, HTTPException
import app.auth as auth
from app.database import conversations, messages, exceptions

router = APIRouter()

@router.get("/v1/load/{conversation_id}")
async def load_messages_v2(
    request: Request,
    conversation_id: str,
    offset: int = 0,
):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Get api route version from headers
    route_version = request.headers.get("version")

    # Verifies token with auth server
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    try:
        # Get all members of conversation
        members = await conversations.get_members(conversation_id)
    except exceptions.ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation Not Found")
    except:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    # Check to ensure that the user is a member of the conversation they are trying to load
    if username in members:
        try:
            # Get all messages from database
            messages_, unread_messages = await messages.get_messages(
                conversation_id=conversation_id,
                offset=offset,
                account=username
            )
            messages_.reverse()

            # Set conversation name based on who is loading it
            if members[0] == username:
                conversation_name = members[1]
            else:
                conversation_name = members[0]

            # Format data for client
            data = {
                "conversation_name": conversation_name,
                "conversation_id": conversation_id,
                "unread_messages": unread_messages,
                "messages": messages_
            }

            # Mark messages as viewed
            await messages.mark_message_viewed_bulk(conversation_name, conversation_id, offset)

            # Check what route version the client requested
            if route_version == "2.0":
                return data
            else:
                return messages_
        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal Server Error")
    else:
        raise HTTPException(status_code=403, detail="You are not a member of this conversation")