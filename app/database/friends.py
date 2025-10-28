from app.database.connections import get_connection
import json
import uuid
import datetime
import app.database.exceptions as exceptions
from pydantic import BaseModel
from typing import Optional

async def get_friends_list(account: str) -> list:
    """
    Gets all friends of a user.
    Args:
        account (str): The account identifier of the user.
    Raises:
        None
    Returns:
        friends_list (list): A list of friends.
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    friends_list = None

    # Gets all data from the database
    cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
    item = cursor.fetchone()

    # Check if friends list is present
    # If not, then it will be created
    if not item:
        cursor.execute("INSERT INTO users (account, friend_requests, friends) VALUES (%s, %s, %s)", (account, "[]", "[]"))
        conn.commit()

        return "[]"

    # Get friends list from the data
    friends_list = json.loads(item[3])

    # Go through each conversation and get number of unread messages
    for friend in friends_list:
        cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s AND (viewed = 0 OR viewed IS NULL) AND author != %s", (friend["Id"], account))
        unread_messages = cursor.fetchone()

        # Add unread messages to friend
        friend["Unread_Messages"] = unread_messages[0]

    # Close db connection once complete
    conn.close()

    return friends_list

class Friend(BaseModel):
    username: str
    conversationId: str
    lastMessage: Optional[str] = None
    unreadMessages: int

async def get_friends(account: str) -> list[Friend]:
    """
    Gets all friends of a user.
    Args:
        account (str): The account identifier of the user.
    Raises:
        None
    Returns:
        friends_list (list): A list of friends.
    """
    conn = get_connection()
    cursor = conn.cursor()

    friends_list: list[Friend] = []

    # Get friends from database
    cursor.execute("SELECT friends_list FROM users WHERE account = %s", (account,))
    friendsRAW = cursor.fetchone()

    if not friendsRAW:
        # Add user to database if they do not exist
        cursor.execute("INSERT INTO users (account, friend_requests, friends) VALUES (%s, %s, %s)", 
                       (account, "[]", "[]"))
        conn.commit()
        return friends_list
    
    if not isinstance(friendsRAW, tuple) or not isinstance(friendsRAW[0], str):
        raise exceptions.DatabaseError()

    friendsData = json.loads(friendsRAW[0])

    for friend in friendsData:
        # Get number of unread messages
        cursor.execute("""SELECT COUNT(*) FROM messages WHERE conversation_id = %s
                       AND (viewed = 0 OR viewed IS NULL)
                       AND author != %s""",
                       (friend["Id"], account))
        unread_messages = cursor.fetchone()

        if not isinstance(unread_messages, tuple) or not isinstance(unread_messages[0], int):
            raise exceptions.DatabaseError()

        # Get last message
        cursor.execute("""SELECT content FROM messages 
                       WHERE conversation_id = %s 
                       ORDER BY create_time DESC LIMIT 1""",
                       (friend["Id"],))
        last_message = cursor.fetchone()

        if last_message and isinstance(last_message, tuple) and isinstance(last_message[0], str):
            last_message_content = last_message[0]
        else:
            last_message_content = None

        friends_list.append(Friend(
            username=friend["Username"],
            conversationId=friend["Id"],
            lastMessage=last_message_content,
            unreadMessages=unread_messages[0]
        ))
    
    conn.close()
    return friends_list

async def get_friend_requests(account: str):
    """
    Get all friend requests for a user.
    Args:
        account (str): The account identifier of the user.
    Returns:
        friend_requests (list): A list of friend requests.
    Raises:
        None
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
    item = cursor.fetchone()

    # Check if friend requests list is present
    # If not, then it will be created
    if not item:
        cursor.execute("INSERT INTO users (account, friend_requests, friends) VALUES (%s, %s, %s)", (account, "[]", "[]"))
        conn.commit()

        # Close db connection once complete
        conn.close()

        return []
    else:
        # Get all friend requests from the database
        cursor.execute("SELECT * FROM friend_requests WHERE recipient = %s", (account,))
        data = cursor.fetchall()

        friend_requests = []

        # Format friend requests
        for request in data:
            friend_requests.append({
                "Sender": request[1],
                "Recipient": request[2],
                "Request_Id": request[4],
                "Create_Time": request[3]
            })

        # Close db connection once complete
        conn.close()

        return friend_requests

async def add_new_friend(sender: str, recipient: str) -> str:
    """
    Adds a new friend request from the sender to the recipient.
    Args:
        sender (str): The account identifier of the sender.
        recipient (str): The account identifier of the recipient.
    Raises:
        AccountNotFound: If the recipient account does not exist.
        RequestAlreadyOutgoing: If there is already an outgoing friend request from the sender to the recipient.
    Returns:
        request_id (str): The id of the newly created request.
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM users WHERE account = %s", (recipient,))
    database_account = cursor.fetchone()

    # Check if account exists
    if not database_account:
        raise exceptions.AccountNotFound()

    # Check if a request is already outgoing to this user
    cursor.execute("SELECT * FROM friend_requests WHERE sender = %s AND recipient = %s", (sender, recipient,))
    request = cursor.fetchone()

    # If request exists then throw an error
    if request:
        raise exceptions.RequestAlreadyOutgoing()
    
    # Generate request info
    request_id = str(uuid.uuid4())
    request_date = datetime.datetime.now(datetime.timezone.utc)

    # Add request to database
    cursor.execute("""INSERT INTO friend_requests (sender, recipient, create_time, request_id)
                VALUES (%s, %s, %s, %s)""", (sender, recipient, request_date, request_id,))
    conn.commit()

    # Close db connection once complete
    conn.close()

    return request_id

async def accept_friend(request_id: str, account: str) -> str:
    """
    Accepts a friend request from a user.
    Args:
        request_id (str): The identifier for the request.
        account (str): The account accepting the request.
    Raises:
        NotFound: If the request does not exist.
        NoPermission: If the user does not have permission to accept the request.
    Returns:
        conversation_id (str): The id of the newly created conversation.
        sender (str): The user who sent the request.
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch request from database
    cursor.execute("SELECT * FROM friend_requests WHERE request_id = %s", (request_id,))
    request = cursor.fetchone()

    # Check if request exists
    if not request:
        raise exceptions.NotFound()
    
    # Check if user has permission to accept this request
    if request[2] != account:
        raise exceptions.NoPermission()
    
    # Generate a conversation id
    conversation_id = str(uuid.uuid4())

    # Get sender account friends
    cursor.execute("SELECT friends FROM users WHERE account = %s", (request[1],))
    sender_account = cursor.fetchone()

    # Load sender friends
    sender_friends = json.loads(sender_account[0])

    # Add friend to user friends
    sender_friends.append({"Username": request[2], "Id": conversation_id})

    # Update friends in database
    cursor.execute("UPDATE users SET friends = %s WHERE account = %s",
                (json.dumps(sender_friends), request[1]))
    
    # Get recipient friends
    cursor.execute("SELECT friends FROM users WHERE account = %s", (request[2],))
    recipient_account = cursor.fetchone()

    # Load recipient friends
    recipient_friends = json.loads(recipient_account[0])

    # Add friend to user friends
    recipient_friends.append({"Username": request[1], "Id": conversation_id})

    # Update friends in database
    cursor.execute("UPDATE users SET friends = %s WHERE account = %s",
                (json.dumps(recipient_friends), request[2]))
    
    # Create conversation
    cursor.execute("INSERT INTO conversations (conversation_id, members) VALUES (%s, %s)",
                (conversation_id, json.dumps([request[1], request[2]])))
    
    # Remove request from database
    cursor.execute("DELETE FROM friend_requests WHERE request_id = %s", (request_id,))
    
    conn.commit()

    # Close db connection once complete
    conn.close()

    return conversation_id, request[1]

async def deny_friend(request_id: str, account: str) -> None:
    """
    Denies a friend request from a user.
    Args:
        request_id (str): The identifier for the request.
        account (str): The account denying the request.
    Raises:
        NotFound: If the request does not exist.
        NoPermission: If the user does not have permission to deny the request.
    Returns:
        None
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Get request from database
    cursor.execute("SELECT * from friend_requests WHERE request_id = %s", (request_id,))
    request = cursor.fetchone()

    # Check if request exists
    if not request:
        raise exceptions.NotFound()
    
    # Check if user has permission to deny the request
    if request[2] != account:
        raise exceptions.NoPermission()
    
    # Remove request from database
    cursor.execute("DELETE FROM friend_requests WHERE request_id = %s", (request_id,))
    conn.commit()

    # Close db connection once complete
    conn.close()

async def get_outgoing_friend_requests(account: str) -> list:
    """
    Get all outgoing friend requests for a user.
    Args:
        account (str): The account identifier of the user.
    Returns:
        friend_requests (list): A list of outgoing friend requests.
    Raises:
        None
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Get all friend requests from the database
    cursor.execute("SELECT * FROM friend_requests WHERE sender = %s", (account,))
    data = cursor.fetchall()

    friend_requests = []

    # Format friend requests
    for request in data:
        friend_requests.append({
            "Sender": request[1],
            "Recipient": request[2],
            "Request_Id": request[4],
            "Create_Time": request[3]
        })

    # Close db connection once complete
    conn.close()

    return friend_requests

def get_unread_message_count(user: str) -> int:
    """
    Get the number of unread messages a user has for all their conversations.
    Args:
        member (str): The member accessing the unread messages.
    Raises:
        database.exceptions.NotFound: User was not found.
    Returns:
        messageCount (int): The number of unread messages.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get the users friends list
    cursor.execute(
        "SELECT friends FROM users WHERE account = %s",
        (user,)
    )
    friendsListRAW = cursor.fetchone()['friends']

    if friendsListRAW:
        friendsList = json.loads(friendsListRAW)
    else:
        raise exceptions.NotFound()
    
    # Return 0 if the user has no friends :(
    if len(friendsList) == 0:
        return 0
    
    # Create a list of conversation ids from the friends list
    # and SQL placeholders for each
    conversations = []

    for friend in friendsList:
        conversations.append(friend['Id'])

    placeholders = ', '.join(['%s'] * len(conversations))

    # Get number of unread messages from the database
    params = conversations + [user] 
    cursor.execute(
        f"""SELECT COUNT(*) FROM messages
        WHERE conversation_id IN ({placeholders}) AND
        (viewed = 0 OR viewed IS NULL) AND
        author != %s""",
        params
    )
    messageCount = cursor.fetchone()

    conn.close()
    return messageCount['COUNT(*)']