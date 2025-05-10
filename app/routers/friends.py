from fastapi import APIRouter, HTTPException, Request
import app.auth as auth
from app.database import friends, conversations
from app.websocket import live_updates

router = APIRouter()

@router.get('/v1/get_friends')
async def get_friends(request: Request):
    """
    # Get Friends (v1)
    Get a list of friends for the user. This includes their online status and last message sent.

    ## Request Headers
    - `username`: The username of the user making the request.
    - `token`: The authentication token for the user.

    ## Response
    - `200 OK`: A list of friends with their online status and last message sent.
    - `401 Unauthorized`: If the token is invalid or missing.
    """
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify user token
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    friends_list = await friends.get_friends_list(username)

    # Cycle through friends and add their online status
    for friend in friends_list:
        friend_online = await live_updates.get_presence(friend['Username'])
        friend['Online'] = friend_online

    conversation_ids = []
            
    # Create a list of conversation ids
    for friend in friends_list:
        conversation_ids.append(friend['Id'])

    # Get last message sent in each conversation
    last_messages = await conversations.fetch_last_messages(conversation_ids)

    # Add messages to friends list
    for message in last_messages:
        for friend in friends_list:
            if friend["Id"] == message['id']:
                friend["Last_Message"] = message['message']

    return friends_list