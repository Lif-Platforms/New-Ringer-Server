from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from app.database import friends, exceptions
from app.websocket import live_updates
from app.push_notifications import send_push_notification
from app.auth import useAuth
import app.responses as responses
import app.schemas as schemas
from typing import List

router = APIRouter()

@router.get("/v1/get_requests")
async def get_friend_requests(account = Depends(useAuth)) -> List[responses.FriendRequestResponse]:
    """
    # Get Friend Requests (v1)
    Get a list of friend requests for the user.

    ## Request Headers
    - `username`: The username of the user making the request.
    - `token`: The authentication token for the user.

    ## Response
    - `200 OK`: A list of friend requests.
    - `401 Unauthorized`: If the token is invalid or missing.
    """
    username = account[0]

    # Get user friends list
    requests_list = await friends.get_friend_requests(account=username)

    return requests_list

@router.post("/v1/add_friend")
async def add_friend(
    background_tasks: BackgroundTasks,
    request: schemas.AddFriendRequest,
    account = Depends(useAuth)
) -> responses.BasicStatusResponse:    
    # Get user friends to prevent sending a friend request to friends
    user_friends = await friends.get_friends_list(account[0])

    # Check if user is already friends with recipient
    for user in user_friends:
        if user['Username'] == request.recipient:
            raise HTTPException(status_code=409, detail="Already friends with this user.")

    # Add request to database
    try:
        await friends.add_new_friend(
            sender=account[0],
            recipient=request.recipient,
            message=request.message
        )
    except exceptions.AccountNotFound:
        raise HTTPException(status_code=404, detail="User not found.")
    except exceptions.RequestAlreadyOutgoing:
        raise HTTPException(status_code=409, detail="You already have an outgoing friend request to this user.")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Check if user is online
    user_online = await live_updates.get_presence(request.recipient)

    # Checks if recipient is online. If not, a push notification will be sent to their devices
    if not user_online:
        background_tasks.add_task(
            send_push_notification,
            account[0],
            f"{account[0]} sent you a friend request!",
            {},
            request.recipient
        )

    return responses.BasicStatusResponse(status="Ok")

@router.post("/v1/accept_request")
async def accept_friend_request(
    request: Request,
    background_tasks: BackgroundTasks,
    account = Depends(useAuth)
):
    """
    ## Accept Friend Request (v1)
    Accept a friend request and create a conversation.

    ### Headers:
    - **username (str):** The username of the user.
    - **token (str):** The user's token.

    ### Body:
    - **request_id (str):** The ID of the friend request to accept.

    ### Returns:
    - **JSON:** Data associated with the new conversation.
    """
    username = account[0]
    
    # Get request body
    request_body = await request.json()

    # Ensure request body is valid
    if "request_id" not in request_body:
        raise HTTPException(status_code=400, detail="Invalid request body. Missing 'request_id'.")
    
    # Get request id from body
    request_id = request_body["request_id"]

    # Accept friend request and get new conversation id as well as sender
    try:
        conversation_id, request_sender = await friends.accept_friend(
            request_id=request_id,
            account=username
        )
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
        background_tasks.add_task(
            send_push_notification,
            username,
            f"{username} accepted your friend request",
            {},
            request_sender
        )

    return {
        "name": request_sender,
        "conversation_id": conversation_id,
        "sender_presence": user_online
    }

@router.post("/v1/deny_request")
async def deny_friend_request(request: Request, account = Depends(useAuth)):
    """
    ## Deny Friend Request (v1)
    Deny a friend request from a user.

    ### Headers:
    - **username (str):** Username for the account.
    - **token (str):** Token for the account.

    ### Body:
    - **request_id (str):** The id of the request.

    ### Returns:
    - **string:** Status of the request.
    """
    username = account[0]

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
async def outgoing_friend_requests(account = Depends(useAuth)):
    """
    ## Outgoing Friend Requests (v1)
    Get a list of outgoing friend requests for the user.

    ### Headers:
    - **username (str):** The username of the user.
    - **token (str):** The user's token.

    ### Returns:
    - **JSON:** A list of outgoing friend requests.
    """
    username = account[0]

    requests_list = await friends.get_outgoing_friend_requests(account=username)

    return requests_list