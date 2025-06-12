from fastapi import WebSocket

# Keep a list of active connections
connections = []

async def connect_user(websocket: WebSocket, user: str) -> None:
    """
    Connects a user to the WebSocket server.
    Args:
        websocket (WebSocket): The WebSocket connection.
        user (str): The username of the user connecting.
    Returns:
        None
    """
    # Add the new connection to the list
    connections.append({'user': user, 'websocket': websocket})

async def disconnect_user(websocket: WebSocket) -> None:
    """
    Disconnects a user from the WebSocket server.
    Args:
        websocket (WebSocket): The WebSocket connection to disconnect.
    Returns:
        None
    """
    # Remove the connection from the list
    for connection in connections:
        if connection['websocket'] == websocket:
            connections.remove(connection)
            break

async def send_notification(users: list, message: object) -> None:
    """
    Sends a notification to a list of users.
    Args:
        users (list): A list of usernames to send the notification to.
        message (object): The message to send.
    Returns:
        None
    """
    # Keep track of connections the message has been sent to
    sent_conns = []

    # Parse through listed users and check if online
    for user in users:
        # Parse through active connections to check if online
        for connection in connections:
            if connection['user'] == user and connection['websocket'] not in sent_conns:
                # Try to send message to user
                # If fails, disconnect user
                try:
                    await connection['websocket'].send_json(message)
                except:
                    # Remove user from sockets list
                    await disconnect_user(connection['websocket'])

                # Add websocket to sent connections to avoid duplicate sending
                sent_conns.append(connection['websocket'])