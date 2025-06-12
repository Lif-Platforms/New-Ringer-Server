from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Depends,
)
import app.auth as auth
from app.database import push_notification_tokens
from app.auth import useAuth

router = APIRouter()

@router.post("/v1/register")
async def register_push_notifications(request: Request, account = Depends(useAuth)):
    """
    ## Register Push Notifications (v1)
    Register a device for Expo push notifications.

    ### Headers:
    - **username (str):** The username for the the account.
    - **token (str):** The token for the account.

    ### Body:
    - **push-token (str):** The Expo push token for the device.
    """
    username = account[0]

    # Get push token from body
    body = await request.json()
    push_token = body.get("push-token")

    # Check if push token was provided
    if not push_token:
        raise HTTPException(
            status_code=400,
            detail="\"push-token\" key required."
        )

    await push_notification_tokens.add_mobile_notifications_device(push_token, username)

    return "Ok"

@router.post("/v1/unregister")
async def unregister_push_notifications(request: Request):
    """
    ## Unregister Push Notifications (v1)
    Unregister a device for Expo push notifications.

    ### Body:
    - **push-token (str):** The Expo push token for the device.
    """
    # Get push token from body
    body = await request.json()
    push_token = body.get("push-token")

    # Check if push token was provided
    if not push_token:
        raise HTTPException(
            status_code=400,
            detail="\"push-token\" key required."
        )

    await push_notification_tokens.remove_mobile_notifications_device(push_token)

    return "Ok"
