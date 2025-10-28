import requests
from urllib3 import encode_multipart_formdata
import app.config as config
from fastapi import Request, HTTPException, WebSocket, WebSocketException

async def verify_token(username: str, token: str):
    """
    Verify the provided token for a given username by making a request to the authentication server.
    Args:
        username (str): The username to verify the token for.
        token (str): The token to be verified.
    Returns:
        str: The status of the token verification. Returns True if authentication was successful.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
        InvalidToken: If the token is invalid.
    """
    # Create form data for request
    request_body, content_type = encode_multipart_formdata([
        ('username', username),
        ('token', token),
    ])

    # Get auth server url from config
    auth_server_url = config.get_config('auth-server-url')

    # Make auth request to server
    response = requests.post(
        url=f"{auth_server_url}/auth/verify_token",
        headers={'Content-Type': content_type},
        data=request_body,
        timeout=10
    )

    # Check request status code
    if response.status_code == 200:
        return True
    else:
        raise InvalidToken

class InvalidToken(Exception):
    pass

def useAuth(request: Request) -> tuple[str, str]:
    """
    Verify user credentials from request data.
    Args:
        request (fastapi.Request): The FastAPI request data.
    Returns:
        username,token (str,str): Auth details for the account.
    Raises:
        fastapi.HTTPException: Problem with the authentication.
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
    """
    # Get auth headers
    username = request.headers.get("username")
    token = request.headers.get("token")

    # Ensure both auth headers exist
    if not username or not token:
        raise HTTPException(
            status_code=400,
            detail="\"username\" and \"token\" headers are required."
        )

    # Create form data for request
    request_body, content_type = encode_multipart_formdata([
        ('username', username),
        ('token', token),
    ])

    # Get auth server url from config
    auth_server_url = config.get_config('auth-server-url')

    # Make auth request to server
    response = requests.post(
        url=f"{auth_server_url}/auth/verify_token",
        headers={'Content-Type': content_type},
        data=request_body,
        timeout=10
    )

    # Check auth response
    status = response.status_code
    if status == 200:
        return username, token
    elif status == 401:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or token."
        )
    elif status == 403:
        raise HTTPException(
            status_code=403,
            detail="Account suspended."
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Internal server error."
        )


async def useAuth_websocket(websocket: WebSocket) -> str:
    """
    WebSocket-compatible dependency that verifies auth headers from the WebSocket connection
    and returns the username on success. Raises `WebSocketException` on error so FastAPI
    closes the connection with an appropriate WebSocket code.
    """
    username = websocket.headers.get("username")
    token = websocket.headers.get("token")

    if not username or not token:
        raise WebSocketException(code=1008)

    # Create form data for request
    request_body, content_type = encode_multipart_formdata([
        ('username', username),
        ('token', token),
    ])

    # Get auth server url from config
    auth_server_url = config.get_config('auth-server-url')

    # Make auth request to server
    response = requests.post(
        url=f"{auth_server_url}/auth/verify_token",
        headers={'Content-Type': content_type},
        data=request_body,
        timeout=10
    )

    status = response.status_code
    if status == 200:
        return username
    elif status in (401, 403):
        raise WebSocketException(code=1008)
    else:
        raise WebSocketException(code=1011)