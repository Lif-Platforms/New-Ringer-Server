import requests
import yaml

# Loads Config
with open("config.yml", "r") as config:
    configuration = yaml.safe_load(config)

def verify_token(username, token):
    status = None

    response = requests.get(f"{configuration['Auth-Server-URL']}/verify_token/{username}/{token}")
    response_status = response.json()

    if response_status['Status'] == "Successful":
        status = "GOOD!"

    else: 
        status = "INVALID_TOKEN"

    return status