from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import utils.auth_server_interface as auth_server
import utils.db_interface as database
import json
import uvicorn

app = FastAPI()

# Allow Cross-Origin Resource Sharing (CORS) for all origins
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get('/')
def home():
    return 'Welcome to the Ringer API!'

@app.get('/get_friends_list/{username}/{token}')
def get_friends(username: str, token: str):
    status = auth_server.verify_token(username, token)

    # Checks the status of the verification
    if status == "GOOD!":
        friends_list = database.get_friends_list(username)

        if friends_list:
            load_friends_list = json.loads(friends_list)
            print(type(load_friends_list))
            return load_friends_list
        else:
            raise HTTPException(status_code=404, detail="Friends list not found!")

    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")

    else:
        raise HTTPException(status_code=500, detail="Internal server error!")

@app.get('/get_friend_requests/{username}/{token}')
def get_friend_requests(username: str, token: str):
    # Verifies token with auth server
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        requests_list = database.get_friend_requests(account=username)

        if requests_list:
            return requests_list
        else:
            raise HTTPException(status_code=404, detail="Friend requests not found!")

    elif status == "INVALID_TOKEN":
        raise HTTPException(status_code=401, detail="Invalid token!")

    else:
        raise HTTPException(status_code=500, detail="Internal server error!")
    
@app.get('/add_friend/{username}/{token}/{add_user}') 
def add_friend(username, token, add_user):
    # Verifies token with auth server
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        database.add_new_friend(account=username, username=add_user)

        return {"Status": "Ok"}
    
    else: 
        return {"Status" : "Bad"}
    
@app.get('/accept_friend_request/{username}/{token}/{accept_user}')
def add_friend(username, token, accept_user): 
    # Verifies token with auth server
    status = auth_server.verify_token(username, token)

    if status == "GOOD!":
        database.accept_friend(account=username, friend=accept_user)

        return {"Status": "Ok"}
    else:
        return {"Status": "Unsuccessful"}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
