from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
import app.auth as auth
from app.database import friends, exceptions
from app.websocket import live_updates
from app.push_notifications import send_push_notification

router = APIRouter()

@router.get("/v1/get_requests")
async def get_friend_requests(request: Request):
    """
    # Get Friend Requests
    Get a list of friend requests for the user.

    ## Request Headers
    - `username`: The username of the user making the request.
    - `token`: The authentication token for the user.

    ## Response
    - `200 OK`: A list of friend requests.
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

    # Get user friends list
    requests_list = await friends.get_friend_requests(account=username)

    return requests_list

@router.post("/v1/accept_request")
async def accept_friend_request(request: Request, background_tasks: BackgroundTasks):
    """
    ## Accept Friend Request
    Accept a friend request and create a conversation.

    ### Headers:
    - **username (str):** The username of the user.
    - **token (str):** The user's token.

    ### Body:
    - **request_id (str):** The ID of the friend request to accept.

    ### Returns:
    - **JSON:** Data associated with the new conversation.
    """
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")
    
    # Get request body
    request_body = await request.json()

    # Ensure request body is valid
    if "request_id" not in request_body:
        raise HTTPException(status_code=400, detail="Invalid request body. Missing 'request_id'.")
    
    # Get request id from body
    request_id = request_body["request_id"]

    # Accept friend request and get new conversation id as well as sender
    try:
        conversation_id, request_sender = await friends.accept_friend(request_id=request_id, account=username)
    except exceptions.NotFound:
        raise HTTPException(status_code=404, detail="Request not found.")
    except exceptions.NoPermission:
        raise HTTPException(status_code=403, detail="You cannot accept this request.")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Notify sender request was accepted (if online)
    await live_updates.send_message(
        users=request_sender,
        message={
            "Type": "FRIEND_REQUEST_ACCEPT",
            "User": username,
            "Id": conversation_id
        }
    )

    # Checks if recipient is online. If not, a push notification will be sent to their devices
    user_online = await live_updates.get_presence(request_sender)

    if not user_online:
        background_tasks.add_task(send_push_notification, username, f"{username} accepted your friend request", {}, request_sender)

    return {"name": request_sender, "conversation_id": conversation_id, "sender_presence": user_online}

@router.post("/v1/deny_request")
async def deny_friend_request(request: Request):
    # Get username and toke from headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verifies token with auth server
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")
    
    # Get request body
    request_body = await request.json()
    
    # Ensure request body is valid
    if "request_id" not in request_body:
        raise HTTPException(status_code=400, detail="Invalid request body. Missing 'request_id'.")
    
    # Get request id from body
    request_id = request_body["request_id"]

    # Deny friend request
    try:
        await friends.deny_friend(request_id=request_id, account=username)
    except exceptions.NotFound:
        raise HTTPException(status_code=404, detail="Request not found.")
    except exceptions.NoPermission:
        raise HTTPException(status_code=403, detail="You cannot deny this request.")

    return "Request Denied!"

@router.get('/v1/outgoing_requests')
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
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    requests_list = await friends.get_outgoing_friend_requests(account=username)

    return requests_list