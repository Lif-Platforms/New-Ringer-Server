import requests
from urllib3 import encode_multipart_formdata
import app.config as config

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