import requests

# Allows config to be set by main script
def set_config(config):
    global configuration
    configuration = config

def verify_token(username, token):
    status = None

    response = requests.get(f"{configuration['auth-server-url']}/verify_token/{username}/{token}")
    response_status = response.json()

    if response_status['Status'] == "Successful":
        status = "GOOD!"

    else: 
        status = "INVALID_TOKEN"

    return status