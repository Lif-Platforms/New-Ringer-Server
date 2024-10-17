import mysql.connector
from mysql.connector.constants import ClientFlag
import json
import uuid

# Allows config to be set by main script
def set_config(config):
    global configuration
    configuration = config

# Global database connection
conn = None

# Define database errors
class ConversationNotFound(Exception):
    """Error for when the conversation supplied could not be found in the database."""
    pass

# Function to establish a database connection
async def connect_to_database():
    # Handle connecting to the database
    def connect():
        global conn

        # async Define configurations
        mysql_configs = {
            "host": configuration['mysql-host'],
            "port": configuration['mysql-port'],
            "user": configuration['mysql-user'],
            "password": configuration['mysql-password'],
            "database": configuration['mysql-database'], 
        }

        # Check if SSL is enabled
        if configuration['mysql-ssl']:
            # Add ssl configurations to connection
            mysql_configs['client_flags'] = [ClientFlag.SSL]
            mysql_configs['ssl_ca'] = configuration['mysql-cert-path']

        conn = mysql.connector.connect(**mysql_configs)
    
    # Check if there is a MySQL connection
    if conn is None:
        connect()
    else:
        # Check if existing connection is still alive
        if not conn.is_connected():
            connect()

async def get_friends_list(account):
    await connect_to_database()

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

        friends_list = "[]"
    else:
        friends_list = item[3]

    print(friends_list)

    return friends_list

async def get_friend_requests(account):
    await connect_to_database()

    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
    item = cursor.fetchone()

    requests_list = None

    # Check if friend requests list is present
    # If not, then it will be created
    if not item:
        cursor.execute("INSERT INTO users (account, friend_requests, friends) VALUES (%s, %s, %s)", (account, "[]", "[]"))
        conn.commit()

        requests_list = "[]"
    else:
        requests_list = item[2]
    
    return requests_list

async def add_new_friend(account, username): 
    await connect_to_database()

    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
    database_account = cursor.fetchone()

    # Check if account exists
    if database_account:
        # Load current requests
        requests = json.loads(database_account[2])

        # Add request
        requests.append({'name': username})
        
        # Update requests in database
        cursor.execute("UPDATE users SET friend_requests = %s WHERE account = %s", (json.dumps(requests), account))

        conn.commit()

async def accept_friend(account, friend): 
    await connect_to_database()

    cursor = conn.cursor()

    # Get account and friend from database
    cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
    database_account = cursor.fetchone()

    cursor.execute("SELECT * FROM users WHERE account = %s", (friend,))
    database_friend = cursor.fetchone()

    # Generate a conversation id
    conversation_id = str(uuid.uuid4())

    # Load account friend requests
    account_friend_requests = json.loads(database_account[2])

    # Keep track of list index
    index = 0

    # Remove friend request
    for request in account_friend_requests:
        if request["name"] == friend:
            account_friend_requests.remove(account_friend_requests[index]) 
        else:
            index += 1

    # Update database
    cursor.execute("UPDATE users SET friend_requests = %s WHERE account = %s", (json.dumps(account_friend_requests), account))
    conn.commit()

    # Load account friends
    account_friends = json.loads(database_account[3])

    # Add friend to account
    account_friends.append({"Username": friend, "Id": conversation_id})

    # Update database
    cursor.execute("UPDATE users SET friends = %s WHERE account = %s", (json.dumps(account_friends), account))
    conn.commit()

    # Load friend's friends
    friend_friends = json.loads(database_friend[3])

    # Add friend
    friend_friends.append({"Username": account, "Id": conversation_id})

    # Update database
    cursor.execute("UPDATE users SET friends = %s WHERE account = %s", (json.dumps(friend_friends), friend))
    conn.commit()

    # Create conversation
    cursor.execute("INSERT INTO conversations (conversation_id, members) VALUES (%s, %s)", (conversation_id, json.dumps([account, friend])))
    conn.commit()

    return conversation_id

async def deny_friend(username, deny_user): 
    await connect_to_database()

    cursor = conn.cursor()

    # Get account requests
    cursor.execute("SELECT * FROM users WHERE account = %s", (username,))
    account = cursor.fetchone()

    # Load friend requests
    friend_requests = json.loads(account[2])

    # Keep track of list index
    index = 0

    # Remove user
    for request in friend_requests:
        if request["name"] == deny_user:
            friend_requests.remove(friend_requests[index])
        else:
            index += 1

    # Update database
    cursor.execute("UPDATE users SET friend_requests = %s WHERE account = %s", (json.dumps(friend_requests), username))
    conn.commit()

async def send_message(author, conversation_id, message, self_destruct, message_type = None, gif_url = None):
    await connect_to_database()

    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Check if conversation exists
    if conversation:
        # Generate random message id
        message_id = str(uuid.uuid4())

        # Insert message into database
        cursor.execute("""
            INSERT INTO messages (author, content, message_id, conversation_id, self_destruct, message_type, GIF_URL) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
            (author, message, message_id, conversation_id, self_destruct, message_type, gif_url)
        )
        conn.commit()

        return message_id
    else:
        raise ConversationNotFound()
    
async def get_messages(conversation_id: str, offset: int):
    await connect_to_database()

    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Used for formatting messages
    messages = []

    # Check if conversation exists
    if conversation:
        # Get all messages
        cursor.execute("""
            SELECT * FROM messages
            WHERE conversation_id = %s
            ORDER BY id DESC
            LIMIT 20 OFFSET %s
        """, (conversation_id, offset))
        database_messages = cursor.fetchall()

        # Format messages
        for message in database_messages:
            # Format self destruct for messages
            if bool(message[5]) is not False:
                self_destruct = message[5]
            else:
                self_destruct = False

            messages.append({
                "Author": message[1],
                "Message": message[2],
                "Message_Id": message[3],
                "Self_Destruct": self_destruct,
                "Message_Type": message[8],
                "GIF_URL": message[9]
            })

        return messages
    else:
        raise Exception("Conversation Not Found")

async def get_members(conversation_id: str):
    await connect_to_database()

    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Check if conversation exists
    if conversation:
        members = json.loads(conversation[2])

        return members
    else:
        raise ConversationNotFound()

async def remove_conversation(conversation_id: str, username: str):
    await connect_to_database()

    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Check if conversation exists
    if conversation:
        # Get conversation members
        conversation_members = json.loads(conversation[2])

        # Check if user is a member of this conversation
        if username in conversation_members:
            # Delete conversation
            cursor.execute("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))
            conn.commit()

            # Delete conversation messages
            cursor.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
            conn.commit()

            # For each member, remove conversation from friends
            for member in conversation_members:
                # Get member account
                cursor.execute("SELECT * FROM users WHERE account = %s", (member,))
                member_account = cursor.fetchone()

                # Get member friends
                member_friends = json.loads(member_account[3])

                # Keep track of list index
                index = 0

                # Remove conversation
                for friend in member_friends:
                    if friend["Id"] == conversation_id:
                        member_friends.remove(member_friends[index])

                        # Update member friends
                        cursor.execute("UPDATE users SET friends = %s WHERE account = %s", (json.dumps(member_friends), member))
                        conn.commit()
                    else:
                        index += 1

            return "OK"

        else:
            return "NO_PERMISSION"
    else:   
        return "CONVERSATION_NOT_FOUND"
    
async def add_mobile_notifications_device(push_token: str, account: str):
    """
    ## Add Mobile Notifications Device
    Register a mobile device for Expos push notifications API.

    ### Parameters
    - push_token: The unique identifier needed to send a notification to the device.

    - account: The account the device is being registered to.

    ### Returns
    None
    """
    await connect_to_database()

    cursor = conn.cursor()

    # Ensure registration doesn't already exist
    cursor.execute("SELECT push_token FROM push_notifications WHERE push_token = %s", (push_token,))
    database_push_token = cursor.fetchone()

    if database_push_token:
        # Update expiration date
        cursor.execute("""
            UPDATE push_notifications
            SET expires = DATE_ADD(NOW(), INTERVAL 30 DAY)
            WHERE push_token = %s;
        """, (push_token,))
        conn.commit()
    else:
        cursor.execute("""
            INSERT INTO push_notifications (push_token, account, expires) 
            VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 30 DAY))
        """, (push_token, account,))
        conn.commit()

async def remove_mobile_notifications_device(push_token: str):
    """
    ## Remove Mobile Notifications Device
    Unregister a mobile device for Expos push notifications API.

    ### Parameters
    - push_token: The unique identifier needed to send a notification to the device.

    - account: The account the device is registered to.

    ### Returns
    None
    """
    await connect_to_database()

    cursor = conn.cursor()

    cursor.execute("DELETE FROM push_notifications WHERE push_token = %s", (push_token,))
    conn.commit()

async def get_mobile_push_token(account: str):
    """
    ## Get Mobile Push Token
    Get the expo push token for a mobile device.

    ### Parameters
    - account: The account you want to grab devices for.

    ### Returns
    list: All expo push tokens for an account.
    """
    await connect_to_database()

    cursor = conn.cursor()

    # Get all tokens from database
    cursor.execute("SELECT push_token FROM push_notifications WHERE account = %s", (account,))
    tokens = cursor.fetchall()

    format_tokens = []

    # Format results
    for token in tokens:
        format_tokens.append(token[0])

    return format_tokens

async def mark_message_viewed_bulk(user: str, conversation_id: str, offset: int):
    """
    ## Mark Message Viewed Bulk
    Mark the last 20 messages sent by a user as viewed.

    ### Parameters
    - user: The user that sent the messages.
    - conversation_id: The conversation thats being viewed.
    - offset: The offset in the database

    ### Returns
    None
    """
    await connect_to_database()

    cursor = conn.cursor()

    # Mark messages as viewed
    cursor.execute("""
    UPDATE messages 
    SET viewed = 1 
    WHERE id IN (
        SELECT id 
        FROM (
            SELECT id 
            FROM messages 
            WHERE conversation_id = %s 
            ORDER BY id DESC 
            LIMIT 20 OFFSET %s
        ) AS recent_entries
    ) AND author = %s;
    """, (conversation_id, offset, user))

    # Mark messages for deletion
    cursor.execute("""
        UPDATE messages 
        SET delete_time = DATE_ADD(UTC_TIMESTAMP(), INTERVAL self_destruct MINUTE) 
        WHERE conversation_id = %s 
        AND viewed = 1 
        AND author = %s 
        AND self_destruct IS NOT NULL 
        AND self_destruct != 'False';
    """, (conversation_id, user))
    conn.commit()

async def get_delete_messages():
    """
    ## Get Delete Messages
    Get messages that are due to be deleted.

    ### Parameters
    None

    ### Returns
    - list: list of messages that should be deleted.
    """
    await connect_to_database()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT conversation_id, message_id 
        FROM messages 
        WHERE delete_time <= UTC_TIMESTAMP()
        AND self_destruct IS NOT NULL
        AND self_destruct != 'False'
        AND viewed = 1
        AND viewed IS NOT NULL;
    """)
    messages = cursor.fetchall()

    data = []

    for message in messages:
        data.append({"conversation_id": message[0], "message_id": message[1]})

    return data

async def destruct_messages():
    """
    ## Destruct Messages
    Deletes all messages that are ready to be self-destructed.

    ### Parameters
    None

    ### Returns
    None
    """
    await connect_to_database()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM messages
        WHERE delete_time <= UTC_TIMESTAMP()
        AND self_destruct IS NOT NULL
        AND self_destruct != 'False'
        AND viewed = 1
        AND viewed IS NOT NULL;
    """)
    conn.commit()

async def get_message(message_id: str):
    """
    ## Get Message
    Get a message from the database based on its id.

    ### Parameters
    message_id: the id for the message.

    ### Returns
    - dict: message from the database.
    """
    await connect_to_database()

    cursor = conn.cursor()

    cursor.execute("SElECT * FROM messages WHERE message_id = %s", (message_id,))
    message = cursor.fetchone()

    if message:
        return {
            'author': message[1],
            'content': message[2],
            'message_id': message[3],
            'conversation_id': message[4],
            'self_destruct': message[5],
            'viewed': message[6],
            'delete_time': message[7]
        }
    else:
        return None
    
async def view_message(message_id: str):
    """
    ## View Message
    Marks a message in a conversation as viewed.

    ### Parameters
    message_id: the id for the message.

    ### Returns
    None
    """
    await connect_to_database()

    cursor = conn.cursor()

    cursor.execute("UPDATE messages SET viewed = 1 WHERE message_id = %s", (message_id,))
    conn.commit()

    # Check if messages needs to be self-destructed
    cursor.execute("SELECT self_destruct FROM messages WHERE message_id = %s", (message_id,))
    message = cursor.fetchone()

    if message and message[0] != "False" and message[0]:
        cursor.execute("""
            UPDATE messages
            SET delete_time = DATE_ADD(UTC_TIMESTAMP(), INTERVAL self_destruct MINUTE)
            WHERE message_id = %s
        """, (message_id,))
        conn.commit()

async def fetch_last_messages(conversation_ids: list):
    """
    ## Fetch Last Messages
    Fetches the most recent message for each conversation id.

    ### Parameters
    conversation_id: list of conversation ids to fetch messages from.

    ### Returns
    list: list of messages.
    """
    await connect_to_database()

    cursor = conn.cursor()

    messages = []

    for conversation in conversation_ids:
        cursor.execute("""
            SELECT author, content FROM messages 
            WHERE conversation_id = %s 
            ORDER BY id 
            DESC LIMIT 1""", 
        (conversation,))
        message = cursor.fetchone()

        if message:
            messages.append({"id": conversation, "message": f"{message[0]} - {message[1]}"})
        else:
            messages.append({"id": conversation, "message": "This is a new conversation!"})

    return messages

async def search_users(user: str):
    """
    ## Search Users
    Searches the database for users.

    ### Parameters
    user: user that is being searched.

    ### Returns
    list: list of users.
    """
    await connect_to_database()
    cursor = conn.cursor()

    cursor.execute("SELECT account FROM users WHERE account SOUNDS LIKE %s", (user,))
    database_users = cursor.fetchall()

    return_users = []

    for user_ in database_users:
        return_users.append(user_[0])

    return return_users