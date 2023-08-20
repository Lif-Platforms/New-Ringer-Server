from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import utils.auth_server_interface as auth_server
import utils.db_interface as database
import json
import uvicorn

app = FastAPI()

# Allow Cross-Origin Resource Sharing (CORS) for all origins
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# List users currently connected to the notification service
notification_sockets = []

@app.get('/')
def home():
    return 'Welcome to the Ringer API!'

@app.get('/get_friends_list/{username}/{token}')
def get_friends(username: str, token: str):
    status = auth_server.verify_token(username, token)

    # Checks the status of the verification
    if status == "GOOD!":
        friends_list = database.get_friends_list(username)

        if friends_list:
            load_friends_list = json.loads(friends_list)
            print(type(load_friends_list))
            return load_friends_list
        else:
            raise HTTPException(status_code=404, detail="Friends list not found!")

    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")

    else:
        raise HTTPException(status_code=500, detail="Internal server error!")

@app.get('/get_friend_requests/{username}/{token}')
def get_friend_requests(username: str, token: str):
    # Verifies token with auth server
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        requests_list = database.get_friend_requests(account=username)

        if requests_list:
            return requests_list
        else:
            raise HTTPException(status_code=404, detail="Friend requests not found!")

    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")

    else:
        raise HTTPException(status_code=500, detail="Internal server error!")
    
@app.get('/add_friend/{username}/{token}/{add_user}') 
def add_friend(username, token, add_user):
    # Verifies token with auth server
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        database.add_new_friend(account=add_user, username=username)

        return {"Status": "Ok"}
    
    else: 
        return {"Status" : "Bad"}
    
@app.get('/accept_friend_request/{username}/{token}/{accept_user}')
def add_friend(username, token, accept_user): 
    # Verifies token with auth server
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        database.accept_friend(account=username, friend=accept_user)

        return {"Status": "Ok"}
    else:
        return {"Status": "Unsuccessful"}
    
@app.get('/send_message/{username}/{token}/{message}/{conversation_id}')
async def send_message(username, token, message, conversation_id):
    # Verifies token
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        database.send_message(username, conversation_id, message)

        # Get conversation members
        conversation_members = database.get_members(conversation_id)

        print(notification_sockets)

        # Create a set to keep track of users to whom messages are sent
        sent_users = set()

        for member in conversation_members:
            for user in notification_sockets:
                socket_username = user['User']
                socket_client = user['Socket']

                if member == socket_username and socket_username not in sent_users:
                    # Prepare data for sending
                    data = {"Type": "MESSAGE_UPDATE", "Id": conversation_id, "Message": {"Author": username, "Message": message}}

                    await socket_client.send_text(json.dumps(data))
                    print("Sent message to users!")

                    # Mark the user as sent
                    sent_users.add(socket_username)

        return {"Status": "Ok"}
    else:
        return {"Status": "Unsuccessful"}
    
@app.get('/load_messages/{username}/{token}/{conversation}')
def load_messages(username, token, conversation):
    # Verify token 
    status = auth_server.verify_token(username, token)

    if status == 'GOOD!':
        messages = database.get_messages(conversation)

        return messages
    
    else:
        return {'status': "Unsuccessful"}
    
@app.websocket("/live_updates")
async def websocket_endpoint(websocket: WebSocket):
    # Accept the connection
    await websocket.accept()

    authenticated = False
    user_socket = None

    try:
        while True:
            if not authenticated:
                auth_details = json.loads(await websocket.receive_text())
                status = auth_server.verify_token(auth_details['Username'], auth_details['Token'])
                if status == "GOOD!":
                    await websocket.send_text(json.dumps({"Status": "Ok"}))
                    authenticated = True
                    user_socket = {"User": auth_details['Username'], "Socket": websocket}
                    notification_sockets.append(user_socket)
                    print(notification_sockets)
                else:
                    await websocket.send_text(json.dumps({"Status": "Failed", "Reason": "INVALID_TOKEN"}))
                    await websocket.close()
            else:
                data = await websocket.receive_text()
                # Process incoming data from the client
    except WebSocketDisconnect:
        if authenticated:
            notification_sockets.remove(user_socket)
            # Handle client disconnection
            pass

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
