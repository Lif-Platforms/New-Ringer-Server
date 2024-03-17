import sqlite3
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

# Function to establish a database connection
def connect_to_database():
    # Handle connecting to the database
    def connect():
        global conn

        # Define configurations
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

def get_friends_list(account):
    connect_to_database()

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

    return friends_list

def get_friend_requests(account):
    connect_to_database()

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

def add_new_friend(account, username): 
    connect_to_database()

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

def accept_friend(account, friend): 
    connect_to_database()

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
    friend_friends.append({"Username": friend, "Id": conversation_id})

    # Update database
    cursor.execute("UPDATE users SET friends = %s WHERE account = %s", (json.dumps(friend_friends), friend))
    conn.commit()

    # Create conversation
    cursor.execute("INSERT INTO conversations (conversation_id, members) VALUES (%s, %s)", (conversation_id, json.dumps([account, friend])))
    conn.commit()

    return conversation_id

def deny_friend(username, deny_user): 
    connect_to_database()

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

def send_message(author, conversation_id, message):
    connect_to_database()

    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Check if conversation exists
    if conversation:
        # Generate random message id
        message_id = str(uuid.uuid4())

        # Insert message into database
        cursor.execute("INSERT INTO messages (author, content, message_id, conversation_id) VALUES (%s, %s, %s, %s)", (author, message, message_id, conversation_id))
        conn.commit()
            
def get_messages(conversation_id: str):
    connect_to_database()

    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Used for formatting messages
    messages = []

    # Check if conversation exists
    if conversation:
        # Get all messages
        cursor.execute("""SELECT * FROM (
                            SELECT *
                            FROM messages
                            WHERE conversation_id = %s
                            ORDER BY id DESC
                            LIMIT 20
                        ) AS anyVariableName
                        ORDER BY anyVariableName.id ASC;
                       """, (conversation_id,))
        database_messages = cursor.fetchall()

        # Format messages
        for message in database_messages:
            messages.append({"Author": message[1], "Message": message[2], "Message_Id": message[3]})

    return messages

def get_members(conversation_id: str):
    connect_to_database()

    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Check if conversation exists
    if conversation:
        members = json.loads(conversation[2])

    return members

def remove_conversation(conversation_id: str, username: str):
    connect_to_database()

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