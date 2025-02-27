from fastapi import WebSocket

# Create live updates websocket class for handling this connection
class LiveUpdates:
    def __init__(self):
        self.active_connections = []

    async def connect_user(self, websocket: WebSocket, user: str):
        self.active_connections.append({'user': user, 'websocket': websocket})

    async def send_message(self, users: list, message: object):
        # Keep track of connections message has been sent to
        # This is to prevent sending the same message twice to any client
        sent_conns = []

        # Parse through listed users and check if online
        for user in users:
            # Parse through active connections to check if online
            for connection in self.active_connections:
                if connection['user'] == user and connection['websocket'] not in sent_conns:
                    # Try to send message to user
                    # If fails, disconnect user
                    try:
                        await connection['websocket'].send_json(message)
                    except:
                        # Remove user from sockets list
                        self.disconnect_user(connection['websocket'])

                    # Add websocket to sent connections to avoid duplicate sending
                    sent_conns.append(connection['websocket'])
    
    async def get_presence(self, user: str):
        # If user is on active connections return true
        # Otherwise return false
        for connection in self.active_connections:
            if connection['user'] == user:
                return True
            
        return False
    
    async def disconnect_user(self, websocket: WebSocket):
        # Remove user from active connections
        for connection in self.active_connections:
            if connection['websocket'] == websocket:
                self.active_connections.remove(connection)

# Create global websocket instance
live_updates_handler = LiveUpdates()