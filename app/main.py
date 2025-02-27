import database as database
import uvicorn
import app

# Create instance of live updates ws handler
live_ws_conn_handler = live_ws_handler()

# List of users connected to the push-notifications service
push_notification_sockets = []

@app.application.get('/')
async def home():
    return {"name": "Ringer Server", "version": version}
                
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
