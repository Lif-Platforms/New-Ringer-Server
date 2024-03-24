from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import utils.auth_server_interface as auth_server
import utils.db_interface as database
import json
import uvicorn
from fastapi import Request
import os
import yaml

resources_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recourses")

if not os.path.isfile("config.yml"):
    with open("config.yml", 'x') as config:
        config.close()

with open("config.yml", "r") as config:
    contents = config.read()
    configurations = yaml.safe_load(contents)
    config.close()

# Ensure the configurations are not None
if configurations == None:
    configurations = {}

# Open reference json file for config
with open(f"{resources_folder}/json data/default_config.json", "r") as json_file:
    json_data = json_file.read()
    default_config = json.loads(json_data)
    
# Compare config with json data
for option in default_config:
    if not option in configurations:
        configurations[option] = default_config[option]
        
# Open config in write mode to write the updated config
with open("config.yml", "w") as config:
    new_config = yaml.safe_dump(configurations)
    config.write(new_config)
    config.close()

# Set config in utility scripts
auth_server.set_config(configurations)
database.set_config(configurations)

app = FastAPI()

# Allow Cross-Origin Resource Sharing (CORS) for all origins
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# List users currently connected to the notification service
notification_sockets = []

@app.get('/')
async def home():
    return 'Welcome to the Ringer API!'

@app.get('/get_friends_list/{username}/{token}')
async def get_friends(username: str, token: str):
    status = await auth_server.verify_token(username, token)

    # Checks the status of the verification
    if status == "GOOD!":
        friends_list = await database.get_friends_list(username)

        load_friends_list = json.loads(friends_list)
        print(type(load_friends_list))
        
        return load_friends_list
       
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")

    else:
        raise HTTPException(status_code=500, detail="Internal server error!")

@app.get('/get_friend_requests/{username}/{token}')
async def get_friend_requests(username: str, token: str):
    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        requests_list = await database.get_friend_requests(account=username)

        if requests_list:
            return requests_list
        else:
            raise HTTPException(status_code=404, detail="Friend requests not found!")

    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")

    else:
        raise HTTPException(status_code=500, detail="Internal server error!")
    
@app.get('/add_friend/{username}/{token}/{add_user}') 
async def add_friend(username, token, add_user):
    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        await database.add_new_friend(account=add_user, username=username)

        return {"Status": "Ok"}
    
    else: 
        return {"Status" : "Bad"}
    
@app.get('/accept_friend_request/{username}/{token}/{accept_user}')
async def add_friend(username, token, accept_user): 
    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        conversation_id = await database.accept_friend(account=username, friend=accept_user)

        # Notify sender request was accepted
        for user in notification_sockets:
            if user['User'] == accept_user:
                await user['Socket'].send_text(json.dumps({"Type": "FRIEND_REQUEST_ACCEPT", "User": username, "Id": conversation_id}))
                break

        return {"Status": "Ok"}
    else:
        return {"Status": "Unsuccessful"}
    
@app.get('/deny_friend_request/{username}/{token}/{deny_user}')
async def deny_friend(username, token, deny_user):
    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        await database.deny_friend(username, deny_user)

        return {"Status": "Ok"}
    else:
        return HTTPException(status_code=401, detail="Invalid Token!")
    
@app.post('/send_message')
async def send_message(request: Request):
    data = await request.json()  # Parse JSON data from the request body
    username = data.get('username')
    token = data.get('token')
    message = data.get('message')
    conversation_id = data.get('conversation_id')

    # Verifies token
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        await database.send_message(username, conversation_id, message)

        # Get conversation members
        conversation_members = await database.get_members(conversation_id)

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
async def load_messages(username, token, conversation):
    # Verify token 
    status = await auth_server.verify_token(username, token)

    if status == 'GOOD!':
        try:
            messages = await database.get_messages(conversation)

            # Remove all but the last 20 messages
            if len(messages) > 20:
                messages = messages[-20:]

            return messages
        except:
            raise HTTPException(status_code=404, detail="Conversation Not Found")
    
    else:
        return {'status': "Unsuccessful"}
    
@app.get('/remove_conversation/{conversation_id}/{username}/{token}')
async def remove_conversation(conversation_id, username, token):
    # Verify token 
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        # Get conversation members to notify later
        members = await database.get_members(conversation_id)

        # Use database interface to remove conversation
        remove_status = await database.remove_conversation(conversation_id, username)

        # Check the status of the operation
        if remove_status == "OK":
            # Notify conversation members
            for member in members:
                # Stops from notifying user that sent the request
                if member != username:
                    # Check if member is online
                    for user in notification_sockets:
                        if user["User"] == member:
                            await user["Socket"].send_text(json.dumps({"Type": "REMOVE_CONVERSATION", "Id": conversation_id}))

            return {"Status": "Ok"}
        
        elif remove_status == "NO_PERMISSION":
            raise HTTPException(status_code=403, detail="No Permission!")
        
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error!")
    else:
        raise HTTPException(status_code=401, detail="Invalid token!")
    
@app.websocket("/live_updates")
async def websocket_endpoint(websocket: WebSocket):
    # Accept the connection
    await websocket.accept()

    authenticated = False
    user_socket = None
    username = None

    try:
        while True:
            if not authenticated:
                auth_details = json.loads(await websocket.receive_text())
                status = await auth_server.verify_token(auth_details['Username'], auth_details['Token'])
                if status == "GOOD!":
                    await websocket.send_text(json.dumps({"Status": "Ok"}))
                    authenticated = True
                    user_socket = {"User": auth_details['Username'], "Socket": websocket}
                    notification_sockets.append(user_socket)
                    username = auth_details['Username']
                    print(notification_sockets)
                else:
                    await websocket.send_text(json.dumps({"Status": "Failed", "Reason": "INVALID_TOKEN"}))
                    await websocket.close()
            else:
                data = await websocket.receive_json()
                
                if data["MessageType"] == "SEND_MESSAGE":
                    # Get conversation members to ensure authorization
                    members = await database.get_members(data["ConversationId"])

                    # Check if user is a member of the conversation
                    if username in members:
                        # Add message to database
                        await database.send_message(username, data["ConversationId"], data["Message"])

                        # Tell client message was sent
                        await websocket.send_text(json.dumps({"ResponseType": "MESSAGE_SENT"}))

                        # Notify conversation members that the message was sent
                        for user in notification_sockets:
                            if user["User"] in members:
                                await user["Socket"].send_text(json.dumps({"Type": "MESSAGE_UPDATE", "Id": data["ConversationId"], "Message": {"Author": username, "Message": data["Message"]}}))
                                print("sent notification to: " + user["User"])
                    else:
                        await websocket.send_text(json.dumps({"ResponseType": "ERROR", "ErrorCode": "NO_PERMISSION"}))
                else:
                    await websocket.send_json(json.dumps({"ResponseType": "ERROR", "ErrorCode": "BAD_REQUEST"}))

    except WebSocketDisconnect:
        if authenticated:
            notification_sockets.remove(user_socket)
            # Handle client disconnection
            pass

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
