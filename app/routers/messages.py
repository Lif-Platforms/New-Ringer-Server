from fastapi import APIRouter, Request, HTTPException, Depends
from app.database import conversations, messages, exceptions
from app.auth import useAuth

router = APIRouter()

@router.get("/v1/load/{conversation_id}")
async def load_messages(
    conversation_id: str,
    offset: int = 0,
    account = Depends(useAuth),
):
    username = account[0]

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

            return data
        except Exception:
            raise HTTPException(status_code=500, detail="Internal Server Error")
    else:
        raise HTTPException(status_code=403, detail="You are not a member of this conversation")