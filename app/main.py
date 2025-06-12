import app.database as database
import sentry_sdk
import app.config as cf
from app.__version__ import version
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.websocket import live_updates
from app.routers import (
    legacy,
    friends,
    friend_requests,
    notifications,
    gifs,
    conversations,
    messages,
)

# Get run environment
__env__= os.getenv('RUN_ENVIRONMENT')

# Determine whether or not to show the documentation
if __env__ == "PRODUCTION":
    docs_url = None
else:
    docs_url = '/docs'

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

async def destruct_messages():
    while True:
        # Get delete messages
        messages = await database.get_delete_messages()
        
        # Notify clients to delete the message
        for message in messages:
            members = await database.get_members(message['conversation_id'])

            await live_updates.send_message(
                users=members,
                message={
                    "Type": "DELETE_MESSAGE",
                    "Conversation_Id": message['conversation_id'],
                    "Message_Id": message['message_id']
                }
            )

        await database.destruct_messages()

        await asyncio.sleep(10)

@asynccontextmanager
async def lifespan(application: FastAPI):
    # Code to run at startup
    task = asyncio.create_task(destruct_messages())
    yield
    # Code to run at shutdown
    task.cancel()


# Create the FastAPI instance
app = FastAPI(
    title="Ringer Server",
    description="Official server for the Ringer messaging app.",
    version=version,
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=None
)

# Allow Cross-Origin Resource Sharing (CORS) for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers in app
app.include_router(router=legacy.main_router, tags=["Legacy"])
app.include_router(router=friends.router, prefix="/friends", tags=["Friends"])
app.include_router(router=friend_requests.router, prefix="/friend_requests", tags=["Friend Requests"])
app.include_router(router=notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(router=gifs.router, prefix="/gifs", tags=["GIFs"])
app.include_router(router=conversations.router, prefix="/conversations", tags=["Conversations"])
app.include_router(router=messages.router, prefix="/messages", tags=["Messages"])

# Init config
cf.init_config()

@app.get('/')
async def home():
    return {"name": "Ringer Server", "version": version}
