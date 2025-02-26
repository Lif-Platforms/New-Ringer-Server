from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from __version__ import version
import sentry_sdk
import os
from auth import auth_server_interface
import database
import yaml
import json
from contextlib import asynccontextmanager
import asyncio
import routers

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

# Get resources folder
# Holds data like the default config template
resources_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recourses")

# Get run environment
__env__= os.getenv('RUN_ENVIRONMENT')

# Determine whether or not to show the documentation
if __env__ == "PRODUCTION":
    docs_url = None
else:
    docs_url = '/docs'

if not os.path.isfile("config.yml"):
    with open("config.yml", 'x') as config:
        config.close()

with open("config.yml", "r") as config:
    contents = config.read()
    configurations = yaml.safe_load(contents)
    config.close()

# Ensure the configurations are not None
if configurations == None:
    configurations = {}

# Open reference json file for config
with open(f"{resources_folder}/json data/default_config.json", "r") as json_file:
    json_data = json_file.read()
    default_config = json.loads(json_data)
    
# Compare config with json data
for option in default_config:
    if not option in configurations:
        configurations[option] = default_config[option]
        
# Open config in write mode to write the updated config
with open("config.yml", "w") as config:
    new_config = yaml.safe_dump(configurations)
    config.write(new_config)
    config.close()

# Set config in utility scripts
database.set_config(configurations)

# Init auth server interface
auth_server = auth_server_interface(configurations['auth-server-url'])

async def destruct_messages():
    while True:
        # Get delete messages
        messages = await database.get_delete_messages()
        
        # Notify clients to delete the message
        for message in messages:
            members = await database.get_members(message['conversation_id'])

            await live_ws_handler.send_message(
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
application = FastAPI(
    title="Ringer Server",
    description="Official server for the Ringer messaging app.",
    version=version,
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=None
)

# Allow Cross-Origin Resource Sharing (CORS) for all origins
application.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Include all routers in app
application.include_router(routers)