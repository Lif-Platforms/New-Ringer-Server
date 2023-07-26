import requests

def verify_token(username, token):
    status = None

    response = requests.get(f"http://localhost:8002/verify_token/{username}/{token}")
    response_status = response.json()

    if response_status['Status'] == "Successful":
        status = "GOOD!"

    else: 
        status = "INVALID_TOKEN"

    return status