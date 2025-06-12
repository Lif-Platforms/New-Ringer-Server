from app.database.connections import get_connection
from mysql.connector import connection

async def search_users(user: str, db_conn: connection = None):
    """
    Searches the database for users.
    Parameters:
        user (str): user that is being searched.
        db_conn (mysql.connector.connection): database connection (optional).
    Returns:
        users (list): list of users.
    """
    # Create/ensure database connection
    if connection is None:
        conn = get_connection()
    else:
        conn = db_conn
    cursor = conn.cursor()

    cursor.execute("SELECT account FROM users WHERE account SOUNDS LIKE %s", (user,))
    database_users = cursor.fetchall()

    if connection is None:
        # Close the connection if it was created here
        # Connections not created here are managed by the caller
        cursor.close()

    return_users = []

    for user_ in database_users:
        return_users.append(user_[0])

    return return_users