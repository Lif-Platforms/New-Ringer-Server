from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)
import app.auth as auth
from app.database import push_notification_tokens

router = APIRouter()

@router.post("/v1/register")
async def register_push_notifications(request: Request):
    # Get auth info
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify auth info
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Get push token from body
    body = await request.json()
    push_token = body.get("push-token")

    await push_notification_tokens.add_mobile_notifications_device(push_token, username)

    return "Ok"

@router.post("/v1/unregister")
async def unregister_push_notifications(request: Request):
    # Get auth info
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Verify auth info
    try:
        await auth.verify_token(username, token)
    except auth.InvalidToken:
        raise HTTPException(status_code=401, detail="Invalid token!")
    except:
        raise HTTPException(status_code=500, detail="Internal server error.")

    # Get push token from body
    body = await request.json()
    push_token = body.get("push-token")

    await push_notification_tokens.remove_mobile_notifications_device(push_token)

    return "Ok"
