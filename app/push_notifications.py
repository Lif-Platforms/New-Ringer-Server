from app.database import push_notification_tokens
import requests

async def send_push_notification(title: str, body: str, data: dict, account: str) -> None:
    """
    Send push notification to all devices of a user.
    Args:
        title (str): Title of the notification.
        body (str): Body of the notification.
        data (dict): Additional data to send with the notification.
        account (str): Account identifier for the user.
    Returns:
        None
    """
    # Get push tokens from database
    push_tokens = await push_notification_tokens.get_mobile_push_token(account)

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