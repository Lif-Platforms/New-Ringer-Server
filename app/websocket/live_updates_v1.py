from pydantic import BaseModel
from fastapi import WebSocket
from typing import List
from app.database import friends

class ConnectionType(BaseModel):
    websocket: WebSocket
    account: str
    model_config = {"arbitrary_types_allowed": True}

connections: List[ConnectionType] = []

async def handle_presence_change(user: str, online: bool) -> None:
    """
    Handles a user's presence change by notifying their friends.
    Args:
        user (str): The username of the user whose presence changed.
        online (bool): The new presence status of the user (True for online, False for offline).
    Returns:
        None
    """
    # Get user's friends
    friends_list = await friends.get_friends(user)

    # Notify friends of presence change
    for connection in connections:
        for friend in friends_list:
            if connection.account == friend.username:
                await connection.websocket.send_json({
                    "eventType": "PRESENCE_CHANGE",
                    "data": {
                        "user": user,
                        "online": online
                    }
                })

async def connect_user(websocket: WebSocket, account: str) -> None:
    """
    Connects a user to the WebSocket server.
    Args:
        websocket (WebSocket): The WebSocket connection.
        account (str): The account identifier of the user connecting.
    Returns:
        None
    """
    await websocket.accept()
    connection = ConnectionType(websocket=websocket, account=account)
    connections.append(connection)

    # Alert all friends of the presence change
    await handle_presence_change(account, online=True)

async def disconnect_user(websocket: WebSocket) -> None:
    """
    Disconnects a user from the WebSocket server.
    Args:
        websocket (WebSocket): The WebSocket connection to disconnect.
    Returns:
        None
    """
    for connection in connections:
        if connection.websocket == websocket:
            account = connection.account
            connections.remove(connection)

            # Check if user is still connected on another device
            user_still_connected = any(conn.account == account for conn in connections)
            if not user_still_connected:
                # Alert all friends of the presence change
                await handle_presence_change(account, online=False)
            break

async def send_request_response(
    websocket: WebSocket,
    requestId: str,
    statusCode: int,
    message: str,
) -> None:
    """
    Sends an error message to a specific WebSocket connection.
    Args:
        websocket (WebSocket): The WebSocket connection to send the error to.
        requestId (str): The request identifier.
        statusCode (int): The HTTP status code representing the error.
        message (str): The error message.
    Returns:
        None
    """
    # Determine response type based on status code
    if 200 <= statusCode < 300:
        responseType = "response"
    elif 400 <= statusCode < 500:
        responseType = "error"
    else:
        responseType = "unknown"

    await websocket.send_json({
        "responseType": responseType,
        "requestId": requestId,
        "statusCode": statusCode,
        "message": message
    })

async def send_event(users: List[str], eventType: str, data: dict) -> None:
    """
    Sends live event to list of users.
    Args:
        users (List[str]): List of users to send the event to.
        eventType (str): The type of event being sent.
        data (dict): The data to send with the event.
    Returns:
        None
    """
    for user in connections:
        if user.account in users:
            await user.websocket.send_json({
                "eventType": eventType,
                "data": data
            })

class UserPresenceList(BaseModel):
    user: str
    online: bool

async def get_presence(users: List[str]) -> List[UserPresenceList]:
    """
    Get the presence of a list of users.
    Args:
        users (List[str]): List of users to check presence on.
    Returns:
        out (List[UserPresenceList]): List of users and their presence.
    """
    out: List[UserPresenceList] = []

    for username in users:
        # If the user is found they are online
        userFound: bool = any(conn.account == username for conn in connections)

        # Add user to list
        out.append(UserPresenceList(user=username, online=userFound))

    return out