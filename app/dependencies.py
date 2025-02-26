from .database import database
from .auth import auth_server

def get_db():
    with database.get_connection() as conn:
        yield conn

def get_auth():
    yield auth_server