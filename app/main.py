import database as database
import uvicorn
import app
import sentry_sdk
import config as cf

# Init sentry
sentry_sdk.init(
    dsn="https://f6207dc4d931cccac8338baa0cfb4440@o4507181227769856.ingest.us.sentry.io/4508237654982656",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    _experiments={
        # Set continuous_profiling_auto_start to True
        # to automatically start the profiler on when
        # possible.
        "continuous_profiling_auto_start": True,
    },
)

# Init config
config = cf.Config()
config.init_config()

# Create instance of live updates ws handler
live_ws_conn_handler = live_ws_handler()

# List of users connected to the push-notifications service
push_notification_sockets = []

@app.application.get('/')
async def home():
    return {"name": "Ringer Server", "version": version}
                
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
