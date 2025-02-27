from .database import database
from .auth import auth_server
from .websocket import live_updates_handler

def get_db():
    with database.get_connection() as conn:
        yield conn

def get_auth():
    yield auth_server

def get_ws():
    yield live_updates_handler