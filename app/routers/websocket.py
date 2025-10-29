from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from app.auth import useAuth_websocket
from app.websocket import live_updates_v1
from app.database import messages, conversations, friends
from app.database import exceptions as db_exceptions
from datetime import datetime, timezone
from app import push_notifications
import app.responses as responses

router = APIRouter()

async def handle_send_message(websocket: WebSocket, account: str, requestId: str, body: dict):
    # Ensure all required fields are present
    required_fields = ["conversationId", "text"]
    for field in required_fields:
        if field not in body:
            await websocket.send_json(responses.WsRequestResponse(
                requestId=requestId,
                statusCode=400,
                message=f"Missing request field: {field}"
            ).model_dump())
            return

    # Extract message details
    conversationId = body["conversationId"]
    message = body["text"]
    messageType = body["messageType"] if "messageType" in body else None
    gifURL = body["gifURL"] if "gifURL" in body else None

    # Ensure message type is valid
    if messageType and messageType != "GIF":
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=400,
            message="Invalid message type."
        ).model_dump())
        return
    
    # Ensure user is a member of the conversation
    try:
        conversationMembers = await conversations.get_members(conversationId)
    except db_exceptions.ConversationNotFound:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=400,
            message="Conversation not found!"
        ).model_dump())
        return

    # Ensure user is a member of the conversation
    if account not in conversationMembers:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=403,
            message="You are not a member of this conversation."
        ).model_dump())
        return
    
    # Store the message in the database
    try:
        messageId = await messages.send_message(
            conversation_id=conversationId,
            message=message,
            self_destruct=None,
            gif_url=gifURL,
            author=account
        )
    except db_exceptions.ConversationNotFound:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=404,
            message="Conversation not found!"
        ).model_dump())
        return
    
    # Alert the client of a successful response
    await websocket.send_json(responses.WsRequestResponse(
        requestId=requestId,
        statusCode=200,
        message="Message send!"
    ).model_dump())
    
    # Remove message sender from conversation members
    if account in conversationMembers:
        conversationMembers.remove(account)

    # Get current UTC time of the message
    current_utc_time = datetime.now(timezone.utc) 

    message_ = responses.Message(
        author=account,
        text=message,
        id=messageId,
        type=str(messageType),
        gifURL=str(gifURL),
        sendTime=current_utc_time
    )

    # Send message update to all online members of the conversation
    await live_updates_v1.send_event(
        conversationMembers,
        "NEW_MESSAGE",
        responses.WsNewMessageEvent(
            conversationId=conversationId,
            message=message_
        ).model_dump()
    )

    # Get users that are offline in the conversation
    userPresence = await live_updates_v1.get_presence(conversationMembers)

    # Send a notification for all offline users
    for user in userPresence:
        if not user.online:
            # Get total unread messages to set the badge number
            unreadMessages = friends.get_unread_message_count(user.user)

            await push_notifications.send_push_notification(
                title=account,
                body=message,
                data={
                    "conversationId": conversationId
                },
                badge=unreadMessages,
                account=user.user
            )

async def handle_message_view(websocket: WebSocket, account: str, requestId: str, body: dict):
    # Ensure all required fields are present
    required_fields = ["conversationId", "messageId"]
    for field in required_fields:
        if field not in body:
            await websocket.send_json(responses.WsRequestResponse(
                requestId=requestId,
                statusCode=400,
                message=f"Missing required field: {field}"
            ).model_dump())
            return

    # Extract message details
    conversationId = body["conversationId"]
    messageId = body["messageId"]

    # Ensure user is a member of the conversation
    try:
        conversationMembers = await conversations.get_members(conversationId)
    except db_exceptions.ConversationNotFound:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=404,
            message="Conversation not found"
        ).model_dump())
        return

    # Ensure user is a member of the conversation
    if account not in conversationMembers:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=403,
            message="You are not a member of this conversation"
        ).model_dump())
        return

    message = await messages.get_message(messageId)

    # Ensure message is part of the conversation
    if message.conversationId != conversationId:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=404,
            message="Message not found in this conversation"
        ).model_dump())
        return
    
    # Ensure user is not the author of the message
    if message.author == account:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=403,
            message="You cannot view your own message"
        ).model_dump())
        return

    # Mark the message as viewed in the database
    await messages.view_message(messageId)

    # Acknowledge successful marking of message as viewed
    await websocket.send_json(responses.WsRequestResponse(
        requestId=requestId,
        statusCode=200,
        message="Message marked as viewed"
    ).model_dump())

async def handle_user_typing(websocket: WebSocket, account: str, requestId: str, body: dict):
    requiredFields = ["conversationId", "isTyping"]
    for key in requiredFields:
        if key not in body:
            await websocket.send_json(responses.WsRequestResponse(
                requestId=requestId,
                statusCode=400,
                message=f"Missing field: {key}"
            ).model_dump())
            return
    
    try:
        conversationMembers = await conversations.get_members(body["conversationId"])
    except db_exceptions.ConversationNotFound:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=404,
            message="Conversation not found."
        ))
        return
    
    if account not in conversationMembers:
        await websocket.send_json(responses.WsRequestResponse(
            requestId=requestId,
            statusCode=403,
            message="You are not a member of this conversation."
        ))
        return

    # Ensure we dont alert the request sender of the typing change
    alertMembers = conversationMembers
    alertMembers.remove(account)

    event = responses.UserTypingEvent(
        conversationId=body["conversationId"],
        user=account,
        isTyping=body["isTyping"]
    ).model_dump()

    await live_updates_v1.send_event(
        eventType="USER_TYPING",
        users=alertMembers,
        data=event
    )

    await websocket.send_json(responses.WsRequestResponse(
        requestId=requestId,
        statusCode=200
    ).model_dump())

handlers = {
    "SEND_MESSAGE": handle_send_message,
    "VIEW_MESSAGE": handle_message_view,
    "USER_TYPING": handle_user_typing
}

@router.websocket("/v1/live-updates")
async def websocket_endpoint(websocket: WebSocket, account: str = Depends(useAuth_websocket)):
    await live_updates_v1.connect_user(websocket, account)
    while True:
        try:
            data = await websocket.receive_json()
            requestType = data.get("requestType")
            requestId = data.get("requestId")
            body = data.get("body", {})

            # Ensure requestType and requestId are provided
            if not requestType or not requestId:
                await websocket.send_json(responses.WsRequestResponse(
                    requestId=requestId or "unknown", 
                    statusCode=400, 
                    message="Missing requestType or requestId"
                ).model_dump())
                continue

            handler = handlers.get(requestType)
            if handler:
                await handler(
                    account=account,
                    websocket=websocket,
                    requestId=requestId,
                    body=body
                )
            else:
                await websocket.send_json(responses.WsRequestResponse(
                    requestId=requestId, 
                    statusCode=400, 
                    message=f"Unknown requestType: {requestType}"
                ).model_dump())
            
        except WebSocketDisconnect:
            await live_updates_v1.disconnect_user(websocket)
            break
