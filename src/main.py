from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from utils.auth_server_interface import auth_server_interface
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

resources_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recourses")

# Get run environment
__env__= os.getenv('RUN_ENVIRONMENT')

# Set sentry env based on run env
if __env__ == "PRODUCTION":
    sentry_env = "production"
else:
    sentry_env = "development"

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
    environment=sentry_env
)

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
database.set_config(configurations)

# Init auth server interface
auth_server = auth_server_interface(configurations['auth-server-url'])

# Create live updates websocket class for handling this connection
class live_ws_handler:
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
                    await connection['websocket'].send_json(message)

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

# Create instance of live updates ws handler
live_ws_conn_handler = live_ws_handler()

async def destruct_messages():
    while True:
        # Get delete messages
        messages = await database.get_delete_messages()
        
        # Notify clients to delete the message
        for message in messages:
            members = await database.get_members(message['conversation_id'])

            await live_ws_handler.send_message(
                users=members,
                message={
                    "Type": "DELETE_MESSAGE",
                    "Conversation_Id": message['conversation_id'],
                    "Message_Id": message['message_id']
                }
            )

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
    # Authenticate credentials with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Get friends list from server
    friends_list = await database.get_friends_list(username)
    
    return friends_list
       
@app.get("/get_friends")
async def get_friends_v2(request: Request):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify user token
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    friends_list = await database.get_friends_list(username)

    # Cycle through friends and add their online status
    for friend in friends_list:
        friend_online = await live_ws_conn_handler.get_presence(friend['Username'])
        friend['Online'] = friend_online

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
    
@app.get('/get_friend_requests/{username}/{token}')
async def get_friend_requests(username: str, token: str):
    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    requests_list = await database.get_friend_requests(account=username)

    if requests_list:
        return requests_list
    else:
        raise HTTPException(status_code=404, detail="Friend requests not found!")
    
@app.get("/get_friend_requests")
async def get_friend_requests_v2(request: Request):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify user token
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Get user friends list
    requests_list = await database.get_friend_requests(account=username)

    return requests_list

@app.get('/add_friend/{username}/{token}/{add_user}') 
async def add_friend(username, token, add_user):
    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    await database.add_new_friend(account=add_user, username=username)

    return {"Status": "Ok"}
    
@app.post("/add_friend")
async def add_friend_v2(request: Request, background_tasks: BackgroundTasks, recipient: str = Form()):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")
    
    # Get user friends to prevent sending a friend request to friends
    user_friends = await database.get_friends_list(username)

    # Check if user is already friends with recipient
    for user in user_friends:
        if user['Username'] == recipient:
            raise HTTPException(status_code=409, detail="Already friends with this user.")

    # Add request to database
    try:
        await database.add_new_friend(sender=username, recipient=recipient)
    except database.AccountNotFound:
        raise HTTPException(status_code=404, detail="User not found.")
    except database.RequestAlreadyOutgoing:
        raise HTTPException(status_code=409, detail="You already have an outgoing friend request to this user.")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Check if user is online
    user_online = await live_ws_conn_handler.get_presence(recipient)

    # Checks if recipient is online. If not, a push notification will be sent to their devices
    if not user_online:
        background_tasks.add_task(send_push_notification, username, f"{username} sent you a friend request!", {}, recipient)

    return "Request Sent!"
    
@app.get('/accept_friend_request/{username}/{token}/{accept_user}')
async def add_friend(username, token, accept_user): 
    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    conversation_id = await database.accept_friend(account=username, friend=accept_user)

    # Notify sender request was accepted
    await live_ws_conn_handler.send_message(
        users=[accept_user],
        message={
            "Type": "FRIEND_REQUEST_ACCEPT",
            "User": username,
            "Id": conversation_id
        }
    )
    
    return {"Status": "Ok"}
    
@app.post("/accept_friend_request")
async def accept_friend_request_v2(request: Request, background_tasks: BackgroundTasks, request_id: str = Form()):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Accept friend request and get new conversation id as well as sender
    try:
        conversation_id, request_sender = await database.accept_friend(request_id=request_id, account=username)
    except database.NotFound:
        raise HTTPException(status_code=404, detail="Request not found.")
    except database.NoPermission:
        raise HTTPException(status_code=403, detail="You cannot accept this request.")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Notify sender request was accepted (if online)
    await live_ws_conn_handler.send_message(
        users=request_sender,
        message={
            "Type": "FRIEND_REQUEST_ACCEPT",
            "User": username,
            "Id": conversation_id
        }
    )

    # Checks if recipient is online. If not, a push notification will be sent to their devices
    user_online = await live_ws_conn_handler.get_presence(request_sender)

    if not user_online:
        background_tasks.add_task(send_push_notification, username, f"{username} accepted your friend request", {}, request_sender)

    return {"name": request_sender, "conversation_id": conversation_id, "sender_presence": user_online}

@app.get('/deny_friend_request/{username}/{token}/{deny_user}')
async def deny_friend(username, token, deny_user):
    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    await database.deny_friend(username, deny_user)

    return {"Status": "Ok"}

@app.post("/deny_friend_request")
async def deny_friend_v2(request: Request, request_id: str = Form()):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Deny friend request
    try:
        await database.deny_friend(request_id=request_id, account=username)
    except database.NotFound:
        raise HTTPException(status_code=404, detail="Request not found.")
    except database.NoPermission:
        raise HTTPException(status_code=403, detail="You cannot deny this request.")

    return "Request Denied!"

@app.get('/outgoing_friend_requests')
async def outgoing_friend_requests(request: Request):
    """
    ## Outgoing Friend Requests
    Get a list of outgoing friend requests for the user.

    ### Headers:
    - **username (str):** The username of the user.
    - **token (str):** The user's token.

    ### Returns:
    - **JSON:** A list of outgoing friend requests.
    """
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    requests_list = await database.get_outgoing_friend_requests(account=username)

    return requests_list

@app.post('/send_message')
async def send_message(request: Request):
    data = await request.json()  # Parse JSON data from the request body
    username = data.get('username')
    token = data.get('token')
    message = data.get('message')
    conversation_id = data.get('conversation_id')

    # Verifies token
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    await database.send_message(username, conversation_id, message)

    # Get conversation members
    conversation_members = await database.get_members(conversation_id)

    # Send message to conversation members
    await live_ws_conn_handler.send_message(
        users=conversation_members,
        message={
            "Type": "MESSAGE_UPDATE",
            "Id": conversation_id,
            "Message": {
                "Author": username,
                "Message": message
            }
        }
    )

    return {"Status": "Ok"}

@app.get("/load_messages/{conversation_id}")
async def load_messages_v2(request: Request, conversation_id: str, offset: int = 0):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Get api route version from headers
    route_version = request.headers.get("version")

    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

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
            messages, unread_messages = await database.get_messages(
                conversation_id=conversation_id,
                offset=offset,
                account=username
            )
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
                "unread_messages": unread_messages,
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

@app.get('/remove_conversation/{conversation_id}/{username}/{token}')
async def remove_conversation(conversation_id, username, token):
    # Verify token 
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Get conversation members to notify later
    members = await database.get_members(conversation_id)

    # Use database interface to remove conversation
    remove_status = await database.remove_conversation(conversation_id, username)

    # Check the status of the operation
    if remove_status == "OK":
        # Create a list of users to notify based on conversation members
        # This also excludes the user who made the request
        notify_users = []

        for member in members:
            if member != username:
                notify_users.append(member)

        # Send alert to members that conversation was deleted
        await live_ws_conn_handler.send_message(
            users=notify_users,
            message={
                "Type": "REMOVE_CONVERSATION",
                "Id": conversation_id
            }
        )

        return {"Status": "Ok"}
    
    elif remove_status == "NO_PERMISSION":
        raise HTTPException(status_code=403, detail="No Permission!")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error!")

@app.delete("/remove_conversation/{conversation_id}")
async def remove_conversation_v2(request: Request, conversation_id: str):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Get conversation members to notify later
    members = await database.get_members(conversation_id)

    # Use database interface to remove conversation
    remove_status = await database.remove_conversation(conversation_id, username)

    # Check the status of the operation
    if remove_status == "OK":
        # Create a list of users to notify based on conversation members
        # This also excludes the user who made the request
        notify_users = []

        for member in members:
            if member != username:
                notify_users.append(member)

        # Send alert to members that conversation was deleted
        await live_ws_conn_handler.send_message(
            users=notify_users,
            message={
                "Type": "REMOVE_CONVERSATION",
                "Id": conversation_id
            }
        )

        return "Conversation Removed!"
    
    elif remove_status == "NO_PERMISSION":
        raise HTTPException(status_code=403, detail="No Permission!")
    
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error!")

@app.websocket("/live_updates")
async def live_updates(websocket: WebSocket):
    # Accept the connection
    await websocket.accept()

    authenticated = False
    username = None

    try:
        while True:
            if not authenticated:
                auth_details = await websocket.receive_json()

                # Verify auth credentials with auth server
                try:
                    await auth_server.verify_token(auth_details['Username'], auth_details['Token'])
                except auth_server.InvalidToken:
                    await websocket.send_json({"Status": "Failed", "Reason": "INVALID_TOKEN"})
                    await websocket.close()
                    break
                except:
                    await websocket.send_json({"Status": "Failed", "Reason": "SERVER_ERROR"})
                    await websocket.close()
                    break

                await websocket.send_json({"Status": "Ok"})

                # Update auth status/details
                authenticated = True
                username = auth_details['Username']

                # Add user to connected sockets
                await live_ws_conn_handler.connect_user(websocket, username)

                # Get user friends from database
                # This will be used to send a presence update to all friends
                friends = await database.get_friends_list(username)

                # Create user list based on friends list
                # This essentially removes the conversation id from the data and just has a list of usernames
                notify_users = []

                for friend in friends:
                    notify_users.append(friend['Username'])

                # Send presence update to all online friends
                await live_ws_conn_handler.send_message(
                    users=notify_users,
                    message={"Type": "USER_STATUS_UPDATE", "Online": True, "User": username}
                )

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
                            await websocket.send_json({
                                "ResponseType": "ERROR",
                                "ErrorCode": "NOT_FOUND",
                                "Detail": "Provided conversation was not found."
                            })
                            continue
                        except Exception:
                            await websocket.send_json({
                                "ResponseType": "ERROR",
                                "ErrorCode": "SERVER_ERROR",
                                "Detail": "Internal Server Error"
                            })
                            continue

                        # Tell client message was sent
                        await websocket.send_json({"ResponseType": "MESSAGE_SENT", "Message_Id": message_id})

                        # Get current UTC time of the message
                        current_utc_time = datetime.now(timezone.utc) 
                        formatted_utc_time = current_utc_time.strftime("%Y-%m-%d %H:%M:%S")

                        # Notify conversation members that the message was sent
                        await live_ws_conn_handler.send_message(
                            users=members,
                            message={
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
                            }
                        )
                        
                        # If user is offline then a push notification will be sent to their devices
                        for member in members:
                            # Check to ensure member is not current user
                            if member == username:
                                continue

                            # Get online status of member
                            member_online = await live_ws_conn_handler.get_presence(member)
                            
                            # If user is not online then send a push notification to their devices
                            if not member_online:
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
                        await websocket.send_json({
                            "ResponseType": "ERROR",
                            "ErrorCode": "NO_PERMISSION",
                            "Detail": "You are not a member of this conversation."
                        })
                
                elif data["MessageType"] == "USER_TYPING":
                    # Get conversation members
                    members = await database.get_members(data['ConversationId'])

                    # Send typing status to conversation members
                    await live_ws_conn_handler.send_message(
                        users=members,
                        message={
                            "Type": "USER_TYPING", 
                            "Id": data["ConversationId"], 
                            "User": username, 
                            "Typing": data['Typing']
                        }
                    )
                elif data["MessageType"] == "VIEW_MESSAGE":
                    conversation_id = data['Conversation_Id']

                    # Get conversation members
                    members = await database.get_members(conversation_id)

                    # Ensure user is a member of the conversation
                    if username not in members:
                        await websocket.send_json({
                            "ResponseType": "ERROR",
                            "ErrorCode": "NO_PERMISSION",
                            "Detail": "You don't have permission to view this message."
                        })
                        continue

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

                elif data["MessageType"] == "PIN_CONVERSATION":
                    # Ensure all data needed is present
                    if "Conversation_Id" not in data or "Pinned" not in data:
                        await websocket.send_json({
                            "ResponseType": "ERROR",
                            "ErrorCode": "BAD_REQUEST",
                            "Detail": "Bad data provided"
                        })
                        continue
                    
                    # Pull conversation id and pin boolean from data
                    conversation_id = data['Conversation_Id']
                    pinned = data['Pinned']

                    # Ensure data is the correct data types
                    if type(conversation_id) != str or type(pinned) != bool:
                        await websocket.send_json({
                            "ResponseType": "ERROR",
                            "ErrorCode": "BAD_REQUEST",
                            "Detail": "Bad data provided"
                        })
                        continue

                    # Get conversation members
                    try:
                        conversation_members = await database.get_members(conversation_id)
                    except ConversationNotFound:
                        await websocket.send_json({
                            "ResponseType": "ERROR",
                            "ErrorCode": "NOT_FOUND",
                            "Detail": "Conversation not found"
                        })
                        continue
                    
                    # Ensure user is a member of the conversation
                    if username not in conversation_members:
                        await websocket.send_json({
                            "ResponseType": "ERROR",
                            "ErrorCode": "NO_PERMISSION",
                            "Detail": "You are not a member of this conversation"
                        })
                        continue
                    
                    # Pin conversation in database
                    await database.pin_conversation(
                        conversation_id=conversation_id,
                        username=username,
                        pinned=pinned
                    )

                    # Tell client that the operation completed successfully
                    await websocket.send_json({"ResponseType": "OK"})
                else:
                    await websocket.send_json(json.dumps({"ResponseType": "ERROR", "ErrorCode": "BAD_REQUEST"}))

    except WebSocketDisconnect:
        if authenticated:
            # Remove user from notification sockets
            await live_ws_conn_handler.disconnect_user(websocket)

            # Check if user is still online on another device
            user_online = await live_ws_conn_handler.get_presence(username)

            # If user is not online, send a presence update to all friends reflecting this change
            if not user_online:
                # Get users friends
                friends = await database.get_friends_list(username)

                # Make a new list of friends without the conversation ids
                notify_users = []

                for friend in friends:
                    notify_users.append(friend['Username'])

                # Send presence update to friends
                await live_ws_conn_handler.send_message(
                    users=notify_users,
                    message={
                        "Type": "USER_STATUS_UPDATE",
                        "Online": False,
                        "User": username
                    }
                )

@app.post("/register_push_notifications/{device_type}")
async def register_push_notifications(request: Request, device_type: str):
    # Get auth info
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify auth info
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Check device type
    if device_type == "mobile":
        # Get push token from body
        body = await request.json()
        push_token = body.get("push-token")

        await database.add_mobile_notifications_device(push_token, username)

        return "Ok"
    else:
        raise HTTPException(status_code=400, detail="Invalid device type. Supported types: 'mobile'.")

@app.post("/unregister_push_notifications/{device_type}")
async def unregister_push_notifications(request: Request, device_type: str):
    # Get auth info
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify auth info
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Check device type
    if device_type == "mobile":
        # Get push token from body
        body = await request.json()
        push_token = body.get("push-token")

        await database.remove_mobile_notifications_device(push_token)

        return "Ok"
    else:
        raise HTTPException(status_code=400, detail="Invalid device type. Supported types: 'mobile'.")

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
                    try:
                        await auth_server.verify_token(credentials['username'], credentials['token'])
                    except auth_server.InvalidToken:
                        await websocket.send_json({"responseType": "authSuccess", "detail": "Authentication was successful"})
                        continue
                    except:
                        await websocket.send_json({"responseType": "ERROR", "errorCode": "SERVER_ERROR"})
                        continue

                    # Add user to push notifications sockets
                    push_notification_sockets.append({"user": credentials['username'], "socket": websocket})

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

@app.get('/app_refresh')
async def app_refresh(request: Request, last_message_id: str = None, conversation_id: str = None):
    """
    ## App Refresh
    Used by Ringer Client to refresh data such as last message sent, new messages, and user presence.
    
    ### Query Parameters:
    - **last_message_id (str):** The id of the last message the client has in the conversation.
    - **conversation_id (str):** The conversation id the message is in.

    ### Returns:
    - **JSON:** Data requested by client.
    """
    data = {}

    # Get auth credentials
    username = request.headers.get('username')
    token = request.headers.get('token')

    # Verify credentials
    try:
        await auth_server.verify_token(username, token)
    except auth_server.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Check if last message if was provided
    if last_message_id:
        # Check if conversation id was provided
        if conversation_id:
            # Get conversation members
            try:
                members = await database.get_members(conversation_id)
            except ConversationNotFound:
                raise HTTPException(status_code=404, detail="Conversation not found")

            if username not in members:
                raise HTTPException(status_code=403, detail="You are not a member of this conversation")

            # Get all messages after the last message id
            results = await database.get_messages_after(
                message_id=last_message_id,
                conversation_id=conversation_id,
            )

            data['new_messages'] = results
        else:
            raise HTTPException(status_code=400, detail="Conversation id needed for last message")
    
    friends_presence = []
    
    # Get friends of user
    friends = await database.get_friends_list(username)

    # Add all online friends to list
    for friend in friends:
        is_online = await live_ws_conn_handler.get_presence(friend['Username'])
        friends_presence.append({'username': friend['Username'], 'online': is_online})

    # Add friend presence to list
    data['friend_presence'] = friends_presence

    conversation_ids = []

    # Create a list of conversation ids for each friend
    for friend in friends:
        conversation_ids.append(friend['Id'])

    # Get last sent message from each conversation
    last_messages = await database.fetch_last_messages(conversation_ids)

    # Add last sent messages to data
    data['last_sent_messages'] = last_messages

    # Get list of friends and add it to data
    friends_list = await database.get_friends_list(username)
    data['friends_list'] = friends_list

    return data
                
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
