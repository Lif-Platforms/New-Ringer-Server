import mysql.connector
from mysql.connector.constants import ClientFlag
import json
import uuid
import datetime
from contextlib import contextmanager

class Database:
    def __init__(
            self,
            host: str,
            port: int,
            user: str,
            password: str,
            database: str,
            ssl: bool,
            cert_file: str = None
    ):
        # Define mysql config
        self.mysql_config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database, 
        }

        # Check if SSL is enabled
        # If so, add it to the config
        if ssl:
            self.mysql_config['client_flags'] = [ClientFlag.SSL]
            self.mysql_config['ssl_ca'] = cert_file

    def connect(self):
        """
        Creates MySQL Connection.
        Args:
            None
        Returns:
            conn: The MySQL connection.
        """
        if self.conn is None or not self.conn.is_connected():
            self.conn = mysql.connector.connect(**self.mysql_config)

    def close(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()
            self.conn = None

    @contextmanager
    def get_connection(self):
        try:
            self.connect()
            yield self.conn
        finally:
            self.close()

    async def get_friends_list(self, account: str) -> list:
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
        self.connect()
        cursor = self.conn.cursor()

        friends_list = None

        # Gets all data from the database
        cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
        item = cursor.fetchone()

        # Check if friends list is present
        # If not, then it will be created
        if not item:
            cursor.execute("INSERT INTO users (account, friend_requests, friends) VALUES (%s, %s, %s)", (account, "[]", "[]"))
            self.conn.commit()

            return "[]"

        # Get friends list from the data
        friends_list = json.loads(item[3])

        # Go through each conversation and get number of unread messages
        for friend in friends_list:
            cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = %s AND (viewed = 0 OR viewed IS NULL) AND author != %s", (friend["Id"], account))
            unread_messages = cursor.fetchone()

            # Add unread messages to friend
            friend["Unread_Messages"] = unread_messages[0]

        return friends_list

    async def get_friend_requests(self, account: str):
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
        self.connect()
        cursor = self.conn.cursor()

        # Gets all data from the database
        cursor.execute("SELECT * FROM users WHERE account = %s", (account,))
        item = cursor.fetchone()

        # Check if friend requests list is present
        # If not, then it will be created
        if not item:
            cursor.execute("INSERT INTO users (account, friend_requests, friends) VALUES (%s, %s, %s)", (account, "[]", "[]"))
            self.conn.commit()

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

            return friend_requests

    async def add_new_friend(self, sender: str, recipient: str) -> str:
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
        self.connect()
        cursor = self.conn.cursor()

        # Gets all data from the database
        cursor.execute("SELECT * FROM users WHERE account = %s", (recipient,))
        database_account = cursor.fetchone()

        # Check if account exists
        if not database_account:
            raise self.Exceptions.AccountNotFound()

        # Check if a request is already outgoing to this user
        cursor.execute("SELECT * FROM friend_requests WHERE sender = %s AND recipient = %s", (sender, recipient,))
        request = cursor.fetchone()

        # If request exists then throw an error
        if request:
            raise self.Exceptions.RequestAlreadyOutgoing()
        
        # Generate request info
        request_id = str(uuid.uuid4())
        request_date = datetime.datetime.now(datetime.timezone.utc)

        # Add request to database
        cursor.execute("""INSERT INTO friend_requests (sender, recipient, create_time, request_id)
                    VALUES (%s, %s, %s, %s)""", (sender, recipient, request_date, request_id,))
        self.conn.commit()

        return request_id

    async def accept_friend(self, request_id: str, account: str) -> str:
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
        self.connect()
        cursor = self.conn.cursor()

        # Fetch request from database
        cursor.execute("SELECT * FROM friend_requests WHERE request_id = %s", (request_id,))
        request = cursor.fetchone()

        # Check if request exists
        if not request:
            raise self.Exceptions.NotFound()
        
        # Check if user has permission to accept this request
        if request[2] != account:
            raise self.Exceptions.NoPermission()
        
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
                    (json.dumps(sender_friends), request[2]))
        
        # Create conversation
        cursor.execute("INSERT INTO conversations (conversation_id, members) VALUES (%s, %s)",
                    (conversation_id, json.dumps([request[1], request[2]])))
        
        # Remove request from database
        cursor.execute("DELETE FROM friend_requests WHERE request_id = %s", (request_id,))
        
        self.conn.commit()

        return conversation_id, request[1]

    async def deny_friend(self, request_id: str, account: str) -> None:
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
        self.connect()
        cursor = self.conn.cursor()

        # Get request from database
        cursor.execute("SELECT * from friend_requests WHERE request_id = %s", (request_id,))
        request = cursor.fetchone()

        # Check if request exists
        if not request:
            raise self.Exceptions.NotFound()
        
        # Check if user has permission to deny the request
        if request[2] != account:
            raise self.Exceptions.NoPermission()
        
        # Remove request from database
        cursor.execute("DELETE FROM friend_requests WHERE request_id = %s", (request_id,))
        self.conn.commit()

    async def get_outgoing_friend_requests(self, account: str) -> list:
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
        self.connect()
        cursor = self.conn.cursor()

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

        return friend_requests

    async def send_message(self, author, conversation_id, message, self_destruct, message_type = None, gif_url = None):
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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
            self.conn.commit()

            return message_id
        else:
            raise self.Exceptions.ConversationNotFound()
        
    async def get_messages(self, conversation_id: str, offset: int, account: str) -> tuple[list, str]:
        """
        Gets messages from a conversation.
        Args:
            conversation_id (str): The identifier for the conversation.
            offset (int): The offset for fetching messages in the database.
            account (str): The account requesting the messages.
        Raises:
            Exception: Conversation not found.
        Returns:
            messages (list): List of messages.
            unread_messages (int): Number of unread messages.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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
                    "GIF_URL": message[9],
                    "Send_Time": message[10],
                    "Viewed": bool(message[6])
                })

            # Get number of unread messages
            cursor.execute(
                "SELECT COUNT(*) FROM messages "
                "WHERE conversation_id = %s "
                "AND (viewed = 0 OR viewed IS NULL) "
                "AND author != %s", 
                (conversation_id, account)
            )
            unread_messages = cursor.fetchone()

            return messages, unread_messages[0]
        else:
            raise Exception("Conversation Not Found")

    async def get_members(self, conversation_id: str):
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        # Gets all data from the database
        cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
        conversation = cursor.fetchone()

        # Check if conversation exists
        if conversation:
            members = json.loads(conversation[2])

            return members
        else:
            raise self.Exceptions.ConversationNotFound()

    async def remove_conversation(self, conversation_id: str, username: str):
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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
                self.conn.commit()

                # Delete conversation messages
                cursor.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
                self.conn.commit()

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
                            self.conn.commit()
                        else:
                            index += 1

                return "OK"

            else:
                return "NO_PERMISSION"
        else:   
            return "CONVERSATION_NOT_FOUND"
        
    async def add_mobile_notifications_device(self, push_token: str, account: str):
        """
        ## Add Mobile Notifications Device
        Register a mobile device for Expos push notifications API.

        ### Parameters
        - push_token: The unique identifier needed to send a notification to the device.

        - account: The account the device is being registered to.

        ### Returns
        None
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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
            self.conn.commit()
        else:
            cursor.execute("""
                INSERT INTO push_notifications (push_token, account, expires) 
                VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 30 DAY))
            """, (push_token, account,))
            self.conn.commit()

    async def remove_mobile_notifications_device(self, push_token: str):
        """
        ## Remove Mobile Notifications Device
        Unregister a mobile device for Expos push notifications API.

        ### Parameters
        - push_token: The unique identifier needed to send a notification to the device.

        - account: The account the device is registered to.

        ### Returns
        None
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        cursor.execute("DELETE FROM push_notifications WHERE push_token = %s", (push_token,))
        self.conn.commit()

    async def get_mobile_push_token(self, account: str):
        """
        ## Get Mobile Push Token
        Get the expo push token for a mobile device.

        ### Parameters
        - account: The account you want to grab devices for.

        ### Returns
        list: All expo push tokens for an account.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        # Get all tokens from database
        cursor.execute("SELECT push_token FROM push_notifications WHERE account = %s", (account,))
        tokens = cursor.fetchall()

        format_tokens = []

        # Format results
        for token in tokens:
            format_tokens.append(token[0])

        return format_tokens

    async def mark_message_viewed_bulk(self, user: str, conversation_id: str, offset: int):
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
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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
        self.conn.commit()

    async def get_delete_messages(self):
        """
        ## Get Delete Messages
        Get messages that are due to be deleted.

        ### Parameters
        None

        ### Returns
        - list: list of messages that should be deleted.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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

    async def destruct_messages(self):
        """
        ## Destruct Messages
        Deletes all messages that are ready to be self-destructed.

        ### Parameters
        None

        ### Returns
        None
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        cursor.execute("""
            DELETE FROM messages
            WHERE delete_time <= UTC_TIMESTAMP()
            AND self_destruct IS NOT NULL
            AND self_destruct != 'False'
            AND viewed = 1
            AND viewed IS NOT NULL;
        """)
        self.conn.commit()

    async def get_message(self, message_id: str):
        """
        ## Get Message
        Get a message from the database based on its id.

        ### Parameters
        message_id: the id for the message.

        ### Returns
        - dict: message from the database.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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
        
    async def view_message(self, message_id: str):
        """
        ## View Message
        Marks a message in a conversation as viewed.

        ### Parameters
        message_id: the id for the message.

        ### Returns
        None
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        cursor.execute("UPDATE messages SET viewed = 1 WHERE message_id = %s", (message_id,))
        self.conn.commit()

        # Check if messages needs to be self-destructed
        cursor.execute("SELECT self_destruct FROM messages WHERE message_id = %s", (message_id,))
        message = cursor.fetchone()

        if message and message[0] != "False" and message[0]:
            cursor.execute("""
                UPDATE messages
                SET delete_time = DATE_ADD(UTC_TIMESTAMP(), INTERVAL self_destruct MINUTE)
                WHERE message_id = %s
            """, (message_id,))
            self.conn.commit()

    async def fetch_last_messages(self, conversation_ids: list):
        """
        ## Fetch Last Messages
        Fetches the most recent message for each conversation id.

        ### Parameters
        conversation_id: list of conversation ids to fetch messages from.

        ### Returns
        list: list of messages.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

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

    async def search_users(self, user: str):
        """
        ## Search Users
        Searches the database for users.

        ### Parameters
        user: user that is being searched.

        ### Returns
        list: list of users.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        cursor.execute("SELECT account FROM users WHERE account SOUNDS LIKE %s", (user,))
        database_users = cursor.fetchall()

        return_users = []

        for user_ in database_users:
            return_users.append(user_[0])

        return return_users

    async def get_messages_after(self, message_id: str, conversation_id: str):
        """
        ## Get Messages After
        Gets all messages in a conversation after a certain message

        ### Parameters
        message_id: the message to get messages after.
        conversation_id: the conversation where the messages lie.

        ### Returns
        list: List of messages.
        """
        # Create/ensure database connection
        self.connect()
        cursor = self.conn.cursor()

        query = f"""
            SELECT * FROM messages
            WHERE conversation_id = %s
            AND id > (
                SELECT id FROM messages
                WHERE message_id = %s
                ORDER BY id LIMIT 1
            )
        """

        cursor.execute(query, (conversation_id, message_id))
        results = cursor.fetchall()

        data = []

        for message in results:
            data.append({
                'author': message[1],
                'content': message[2],
                'message_id': message[3],
                'conversation_id': message[4],
                'self_destruct': message[5],
                'viewed': message[6],
                'delete_time': message[7]
            })

        return data
    
    class Exceptions:
        """"Class for database exceptions"""

        # Define database errors
        class ConversationNotFound(Exception):
            """Error for when the conversation supplied could not be found in the database."""
            pass

        class AccountNotFound(Exception):
                pass

        class RequestAlreadyOutgoing(Exception):
            pass

        class NotFound(Exception):
            pass

        class NoPermission(Exception):
            pass

# Create a global database instance
database = Database()