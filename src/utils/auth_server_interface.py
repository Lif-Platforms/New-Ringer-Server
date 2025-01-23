import requests
from urllib3 import encode_multipart_formdata

class auth_server_interface:
    def __init__(self, auth_server_url) -> None:
        self.auth_server_url = auth_server_url

    async def verify_token(self, username: str, token: str):
        """
        Verify the provided token for a given username by making a request to the authentication server.
        Args:
            username (str): The username to verify the token for.
            token (str): The token to be verified.
        Returns:
            str: The status of the token verification. Returns True if authentication was successful.
        Raises:
            requests.exceptions.RequestException: If there is an issue with the HTTP request.
            auth_server_interface.InvalidToken: If the token is invalid.
        """
        # Create form data fro request
        request_body, content_type = encode_multipart_formdata([
            ('username', username),
            ('token', token),
        ])

        # Make auth request to server
        response = requests.post(
            url=f"{self.auth_server_url}/auth/verify_token",
            headers={'Content-Type': content_type},
            data=request_body,
            timeout=10
        )

        # Check request status code
        if response.status_code == 200:
            return True
        else:
            raise self.InvalidToken
    
    class InvalidToken(Exception):
        pass