from connections import get_connection

async def search_users(user: str):
    """
    ## Search Users
    Searches the database for users.

    ### Parameters
    user: user that is being searched.

    ### Returns
    list: list of users.
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT account FROM users WHERE account SOUNDS LIKE %s", (user,))
    database_users = cursor.fetchall()
    conn.close()

    return_users = []

    for user_ in database_users:
        return_users.append(user_[0])

    return return_users