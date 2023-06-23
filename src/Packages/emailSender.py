from nylas import APIClient
from dotenv import load_dotenv
import os

# Load api credentials for nylas api
load_dotenv(override=True)

clientId = os.getenv("CLIENT_ID")
clientSecret = os.getenv("CLIENT_SECRET")
accessToken = os.getenv("ACCESS_TOKEN")

# Create an instance of nylas api client
nylas = APIClient(clientId, clientSecret, accessToken,)

# Function for sending reset code emails
def ResetCodeEmail(code, username, userEmail):
    # Creates a new email draft
    draft = nylas.drafts.create()
    draft.subject = "Lif Account Password Reset"

    # Load html email template
    with open("src/email.html", "r") as email:
        content = email.read()

    draft.body = content.replace("[code]", str(code)) 

    draft.to = [{'name': username, 'email': userEmail}]

    # Sends the email and closes the html template
    draft.send()
    email.close()