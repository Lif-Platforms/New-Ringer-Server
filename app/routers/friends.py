from fastapi import APIRouter, Depends
from app.database import friends, conversations
from app.websocket import live_updates
from app.auth import useAuth

router = APIRouter()

@router.get('/v1/get_friends')
async def get_friends(account = Depends(useAuth)):
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
    username = account[0]

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