from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import utils.auth_server_interface as auth_server
import utils.db_interface as database
from utils.db_interface import ConversationNotFound
from urllib.parse import quote
import json
import uvicorn
import os
import yaml
from __version__ import version
import requests
import asyncio
from pysafebrowsing import SafeBrowsing
from contextlib import asynccontextmanager
import sentry_sdk
from datetime import datetime, timezone

# Init sentry
sentry_sdk.init(
    dsn="https://f6207dc4d931cccac8338baa0cfb4440@o4507181227769856.ingest.us.sentry.io/4508237654982656",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    _experiments={
        # Set continuous_profiling_auto_start to True
        # to automatically start the profiler on when
        # possible.
        "continuous_profiling_auto_start": True,
    },
)

resources_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recourses")

# Get run environment
__env__= os.getenv('RUN_ENVIRONMENT')

# Determine whether or not to show the documentation
if __env__ == "PRODUCTION":
    docs_url = None
else:
    docs_url = '/docs'

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

async def destruct_messages():
    while True:
        # Get delete messages
        messages = await database.get_delete_messages()
        
        # Notify clients to delete the message
        for message in messages:
            members = await database.get_members(message['conversation_id'])

            for member in members:
                for user in notification_sockets:
                    if user['User'] == member:
                        await user['Socket'].send_text(json.dumps({
                            "Type": "DELETE_MESSAGE",
                            "Conversation_Id": message['conversation_id'],
                            "Message_Id": message['message_id']
                        }))

        await database.destruct_messages()

        await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run at startup
    task = asyncio.create_task(destruct_messages())
    yield
    # Code to run at shutdown
    task.cancel()

app = FastAPI(
    title="Ringer Server",
    description="Official server for the Ringer messaging app.",
    version=version,
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=None
)

# Allow Cross-Origin Resource Sharing (CORS) for all origins
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# List users currently connected to the notification service
notification_sockets = []

# List of users connected to the push-notifications service
push_notification_sockets = []

async def send_push_notification(title: str, body: str, data: dict, account: str):
    # Get push tokens from database
    push_tokens = await database.get_mobile_push_token(account)

    # Check if database returned any tokens
    if len(push_tokens) > 0:
        # Create messages to send to clients
        messages = []

        for token in push_tokens:
            messages.append({
                'to': token,
                'title': title,
                'body': body,
                'data': data,
                'sound': 'default'
            })
        
        # Send notifications to devices
        requests.post("https://exp.host/--/api/v2/push/send", json=messages, timeout=10)

@app.get('/')
async def home():
    return {"name": "Ringer Server", "version": version}

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
    
@app.get("/get_friends")
async def get_friends_v2(request: Request):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify user token
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        friends_list = json.loads(await database.get_friends_list(username))

        # Cycle through friends and add their online status
        for friend in friends_list:
            # Check if any socket in notification_sockets has the same User as the friend
            if any(socket['User'] == friend["Username"] for socket in notification_sockets):
                friend["Online"] = True
            else:
                friend["Online"] = False

        conversation_ids = []
                
        # Create a list of conversation ids
        for friend in friends_list:
            conversation_ids.append(friend['Id'])

        # Get last message sent in each conversation
        last_messages = await database.fetch_last_messages(conversation_ids)

        # Add messages to friends list
        for message in last_messages:
            for friend in friends_list:
                if friend["Id"] == message['id']:
                    friend["Last_Message"] = message['message']

        return friends_list
    
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")

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
    
@app.get("/get_friend_requests")
async def get_friend_requests_v2(request: Request):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify user token
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        # Get user friends list
        requests_list = await database.get_friend_requests(account=username)

        return json.loads(requests_list)
    
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@app.get('/add_friend/{username}/{token}/{add_user}') 
async def add_friend(username, token, add_user):
    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        await database.add_new_friend(account=add_user, username=username)

        return {"Status": "Ok"}
    
    else: 
        return {"Status" : "Bad"}
    
@app.post("/add_friend")
async def add_friend_v2(request: Request, background_tasks: BackgroundTasks, user: str = Form()):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        # Add request to database
        await database.add_new_friend(account=user, username=username)

        exists = any(socket['User'] == user for socket in notification_sockets)

        # Checks if recipient is online. If not, a push notification will be sent to their devices
        if not exists:
            background_tasks.add_task(send_push_notification, username, f"{username} sent you a friend request!", {}, user)

        return "Request Sent!"
    
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
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
    
@app.post("/accept_friend_request")
async def accept_friend_request_v2(request: Request, background_tasks: BackgroundTasks, user: str = Form()):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        # Accept friend request and get new conversation id
        conversation_id = await database.accept_friend(account=username, friend=user)

        # Notify sender request was accepted (if online)
        for notify_user in notification_sockets:
            if notify_user['User'] == user:
                await notify_user['Socket'].send_text(json.dumps({"Type": "FRIEND_REQUEST_ACCEPT", "User": username, "Id": conversation_id}))
                break

        exists = any(socket['User'] == user for socket in notification_sockets)

        # Checks if recipient is online. If not, a push notification will be sent to their devices
        if not exists:
            background_tasks.add_task(send_push_notification, username, f"{username} accepted your friend request", {}, user)

        return "Request Accepted!"
    
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@app.get('/deny_friend_request/{username}/{token}/{deny_user}')
async def deny_friend(username, token, deny_user):
    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        await database.deny_friend(username, deny_user)

        return {"Status": "Ok"}
    else:
        return HTTPException(status_code=401, detail="Invalid Token!")
    
@app.post("/deny_friend_request")
async def deny_friend_v2(request: Request, user: str = Form()):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        # Deny friend request
        await database.deny_friend(username, user)

        return "Request Denied!"
    
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
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
    
@app.get("/load_messages/{conversation_id}")
async def load_messages_v2(request: Request, conversation_id: str, offset: int = 0):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Get api route version from headers
    route_version = request.headers.get("version")

    # Verifies token with auth server
    status = await auth_server.verify_token(username, token)

    if status == "GOOD!":
        try:
            # Get all members of conversation
            members = await database.get_members(conversation_id)
        except ConversationNotFound:
            raise HTTPException(status_code=404, detail="Conversation Not Found")
        except:
            raise HTTPException(status_code=500, detail="Internal Server Error")
        
        # Check to ensure that the user is a member of the conversation they are trying to load
        if username in members:
            try:
                # Get all messages from database
                messages = await database.get_messages(conversation_id, offset)
                messages.reverse()

                # Set conversation name based on who is loading it
                if members[0] == username:
                    conversation_name = members[1]
                else:
                    conversation_name = members[0]

                # Format data for client
                data = {
                    "conversation_name": conversation_name,
                    "conversation_id": conversation_id,
                    "messages": messages
                }

                # Mark messages as viewed
                await database.mark_message_viewed_bulk(conversation_name, conversation_id, offset)

                # Check what route version the client requested
                if route_version == "2.0":
                    return data
                else:
                    return messages
            except Exception as e:
                print(e)
                raise HTTPException(status_code=500, detail="Internal Server Error")
        else:
            raise HTTPException(status_code=403, detail="You are not a member of this conversation")
                        
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid Token")
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
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
    
@app.delete("/remove_conversation/{conversation_id}")
async def remove_conversation_v2(request: Request, conversation_id: str):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
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

            return "Conversation Removed!"
        
        elif remove_status == "NO_PERMISSION":
            raise HTTPException(status_code=403, detail="No Permission!")
        
        else:
            raise HTTPException(status_code=500, detail="Internal Server Error!")
        
    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error!")
    
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

                    friends = json.loads(await database.get_friends_list(username))

                    # Send status update to all online friends
                    for friend in friends:
                        # Check if the friend is online by looking for their socket in notification_sockets
                        for socket in notification_sockets:
                            if socket['User'] == friend["Username"]:
                                # If the friend is online, send them the message
                                await socket['Socket'].send_text(json.dumps({"Type": "USER_STATUS_UPDATE", "Online": True, "User": username}))
                else:
                    await websocket.send_text(json.dumps({"Status": "Failed", "Reason": "INVALID_TOKEN"}))
                    await websocket.close()
            else:
                data = await websocket.receive_json()
                
                if data["MessageType"] == "SEND_MESSAGE":
                    # Check send time
                    # If it was more than 5 seconds ago then discard the message
                    # If key is not present, ignore it and move on
                    if "SendTime" in data:
                        # Parse send time
                        send_time = datetime.strptime(data["SendTime"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

                        # Get the current UTC time 
                        current_time = datetime.now(timezone.utc) 
                        
                        # Calculate the time difference 
                        time_difference = current_time - send_time 
                        
                        # Convert the time difference to seconds 
                        seconds_passed = time_difference.total_seconds()

                        if seconds_passed > 5:
                            continue

                    # Get conversation members to ensure authorization
                    members = await database.get_members(data["ConversationId"])

                    # Check if user is a member of the conversation
                    if username in members:
                        # Check if message is self-destructing
                        self_destruct = "False"

                        if data.get('Self-Destruct') is not None:
                            self_destruct = data['Self-Destruct']

                        # Add message to database
                        try:
                            # See if user is sending a GIF message
                            gif_url = None
                            message_type = None

                            if data.get('Message_Type') is not None:
                                if data['Message_Type'] == "GIF":
                                    message_type = "GIF"
                                    gif_url = data['GIF_URL']

                            message_id = await database.send_message(username, data["ConversationId"], data["Message"], self_destruct, message_type, gif_url)
                        except ConversationNotFound:
                            await websocket.send_text(json.dumps({
                                "ResponseType": "ERROR",
                                "ErrorCode": "NOT_FOUND",
                                "Detail": "Provided conversation was not found."
                            }))
                            continue
                        except Exception:
                            await websocket.send_text(json.dumps({
                                "ResponseType": "ERROR",
                                "ErrorCode": "SERVER_ERROR",
                                "Detail": "Internal Server Error"
                            }))

                        # Tell client message was sent
                        await websocket.send_text(json.dumps({"ResponseType": "MESSAGE_SENT", "Message_Id": message_id}))

                        # Get current UTC time of the message
                        current_utc_time = datetime.now(timezone.utc) 
                        formatted_utc_time = current_utc_time.strftime("%Y-%m-%d %H:%M:%S")

                        # Notify conversation members that the message was sent
                        for user in notification_sockets:
                            if user["User"] in members:
                                await user["Socket"].send_text(json.dumps({
                                    "Type": "MESSAGE_UPDATE",
                                    "Id": data["ConversationId"],
                                    "Message": {
                                        "Author": username,
                                        "Message": data["Message"],
                                        "Message_Id": message_id,
                                        "Self_Destruct": self_destruct,
                                        "Message_Type": message_type,
                                        "GIF_URL": gif_url,
                                        "Send_Time": formatted_utc_time
                                    }
                                }))
                        
                        # If user is offline then a push notification will be sent to their devices
                        for member in members:
                            print(member)
                            if member != username:
                                exists = any(socket['User'] == member for socket in notification_sockets)

                                if not exists:
                                    asyncio.ensure_future(send_push_notification(
                                        username, data['Message'],
                                        {"conversation_id": data['ConversationId']},
                                        member
                                    ))

                                    # If user is connected to notifications websocket service
                                    # a notification will be delivered that way
                                    for user in push_notification_sockets:
                                        if user['user'] == member:
                                            await user['socket'].send_json({
                                                "responseType": "notification",
                                                "title": username,
                                                "body": data['Message'],
                                                "conversation_id": data['ConversationId']
                                            })

                    else:
                        await websocket.send_text(json.dumps({"ResponseType": "ERROR", "ErrorCode": "NO_PERMISSION"}))
                
                elif data["MessageType"] == "USER_TYPING":
                    # Get conversation members
                    members = await database.get_members(data['ConversationId'])

                    # Notify users of the change
                    for user in notification_sockets:
                        if user["User"] in members:
                            await user["Socket"].send_text(json.dumps({
                                "Type": "USER_TYPING", 
                                "Id": data["ConversationId"], 
                                "User": username, 
                                "Typing": data['Typing']
                            }))
                elif data["MessageType"] == "VIEW_MESSAGE":
                    conversation_id = data['Conversation_Id']

                    # Get conversation members
                    members = await database.get_members(conversation_id)

                    if username in members:
                        # Get message from database and check to ensure the viewer is not the author
                        message = await database.get_message(data['Message_Id'])

                        if message:
                            if message['author'] != username:
                                await database.view_message(data['Message_Id'])

                                await websocket.send_text(json.dumps({"ResponseType": "OK"}))
                            else:
                                await websocket.send_text(json.dumps({
                                    "ResponseType": "ERROR",
                                    "ErrorCode": "NO_PERMISSION",
                                    "Detail": "You cannot view your own message."
                                }))
                        else:
                            await websocket.send_text(json.dumps({'ResponseType': "ERROR", "ErrorCode": "NOT_FOUND"}))
                    else:
                        await websocket.send_text(json.dumps({"ResponseType": "ERROR", "ErrorCode": "NO_PERMISSION"}))
                else:
                    await websocket.send_json(json.dumps({"ResponseType": "ERROR", "ErrorCode": "BAD_REQUEST"}))

    except WebSocketDisconnect:
        if authenticated:
            # Get users friends
            friends = json.loads(await database.get_friends_list(username))

            # Gets a list of the sockets from a user
            def get_user_sockets(username):
                sockets = []

                for user in notification_sockets:
                    if username == user['User']:
                        sockets.append(user)

                return sockets
            
            def if_in_friends(user):
                for friend in friends:
                    if friend["Username"] == user:
                        return True
                return False

            # Remove user from notification sockets
            for user in notification_sockets:
                if user['Socket'] == websocket:
                    notification_sockets.remove(user)

            # Check if user is still online on another device
            user_sockets = get_user_sockets(username)
            
            if len(user_sockets) == 0:
                # Notify all online friends of thr status change
                for user in notification_sockets:
                    if if_in_friends(user["User"]):
                        await user['Socket'].send_text(json.dumps({"Type": "USER_STATUS_UPDATE", "Online": False, "User": username}))

@app.post("/register_push_notifications/{device_type}")
async def register_push_notifications(request: Request, device_type: str):
    # Get auth info
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify auth info
    if await auth_server.verify_token(username, token) == "GOOD!":
        # Check device type
        if device_type == "mobile":
            # Get push token from body
            body = await request.json()
            push_token = body.get("push-token")

            await database.add_mobile_notifications_device(push_token, username)

            return "Ok"
        else:
            raise HTTPException(status_code=400, detail="Invalid device type. Supported types: 'mobile'.")
    else:
        raise HTTPException(status_code=401, detail="Invalid Token")
    
@app.post("/unregister_push_notifications/{device_type}")
async def unregister_push_notifications(request: Request, device_type: str):
    # Get auth info
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify auth info
    if await auth_server.verify_token(username, token) == "GOOD!":
        # Check device type
        if device_type == "mobile":
            # Get push token from body
            body = await request.json()
            push_token = body.get("push-token")

            await database.remove_mobile_notifications_device(push_token)

            return "Ok"
        else:
            raise HTTPException(status_code=400, detail="Invalid device type. Supported types: 'mobile'.")
    else:
        raise HTTPException(status_code=401, detail="Invalid Token")
    
@app.post("/link_safety_check")
async def link_safety_check(request: Request):
    # Load API key from config
    api_key = configurations['safe-browsing-api-key']

    # Initialize the SafeBrowsing client
    safe_browsing = SafeBrowsing(api_key)

    # Get JSON body
    body = await request.json()

    # Get URL from body
    check_url = body['url']

    # Lookup the URL
    result = safe_browsing.lookup_urls([check_url])

    if result[check_url]['malicious']:
        return {"safe": False}
    else:
        return {"safe": True}
    
@app.get("/search_gifs")
async def search_gifs(search: str = None):
    if search:
        sanitized_search = quote(search)
        url = f"https://api.giphy.com/v1/gifs/search?api_key={configurations['giphy-api-key']}&q={sanitized_search}&limit=20"
        response = requests.get(url, timeout=20)
        return response.json()
    else:
        raise HTTPException(status_code=400, detail="No search query provided.")
    
@app.websocket("/user_search")
async def user_search(websocket: WebSocket):
    # Accept user connection
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if "user" in data:
                results = await database.search_users(data['user'])

                await websocket.send_json(results)
            else:
                await websocket.send_json({
                    "responseType": "ERROR",
                    "errorCode": "BAD_REQUEST",
                    "detail": "Data must contain a 'user' key."
                })
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        if websocket.client_state.name == "CONNECTED":
            await websocket.close()

@app.websocket("/live_notifications")
async def live_notifications(websocket: WebSocket):
    await websocket.accept()

    authenticated = False
    user_socket = None

    try:
        while True:
            data = await websocket.receive_json()

            if not authenticated and "credentials" in data:
                credentials = data['credentials']
                # Check request to ensure its good
                if "username" in credentials and "token" in credentials:
                    # Verify credentials with auth server
                    auth_status = await auth_server.verify_token(credentials['username'], credentials['token'])

                    if auth_status == "GOOD!":
                        await websocket.send_json({"responseType": "authSuccess", "detail": "Authentication was successful"})

                        user_socket = {"user": credentials['username'], "socket": websocket}

                        # Add user to push notifications sockets
                        push_notification_sockets.append(user_socket)
                    else:
                        await websocket.send_json({"responseType": "ERROR", "errorCode": "INVALID_CREDENTIALS"})
            elif authenticated and "credentials" not in data:
                await websocket.send_json({"responseType": "ERROR", "errorCode": "BAD_REQUEST"})
            else:
                await websocket.send_json({"responseType": "ERROR", "errorCode": "NOT_AUTHENTICATED"})
    except WebSocketDisconnect:
        print("Client disconnected")

        # Remove user from notification sockets
        if user_socket in push_notification_sockets:
            push_notification_sockets.remove(user_socket)
    finally:
        if websocket.client_state.name == "CONNECTED":
            await websocket.close()

        # Remove user from notification sockets
        if user_socket in push_notification_sockets:
            push_notification_sockets.remove(user_socket)
                
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
