from database.connections import get_connection
import uuid
import database.exceptions as exceptions

async def send_message(
    author,
    conversation_id,
    message,
    self_destruct,
    message_type = None,
    gif_url = None
):
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Check if conversation exists
    if not conversation:
        conn.close()
        raise exceptions.ConversationNotFound()

    # Generate random message id
    message_id = str(uuid.uuid4())

    # Insert message into database
    cursor.execute("""
        INSERT INTO messages (author, content, message_id, conversation_id, self_destruct, message_type, GIF_URL) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)""", 
        (author, message, message_id, conversation_id, self_destruct, message_type, gif_url)
    )
    conn.commit()
    conn.close()

    return message_id
        
async def get_messages(conversation_id: str, offset: int, account: str) -> tuple[list, str]:
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
    conn = get_connection()
    cursor = conn.cursor()

    # Get conversation
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()

    # Used for formatting messages
    messages = []

    # Check if conversation exists
    if not conversation:
        conn.close()
        raise exceptions.ConversationNotFound()

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
    conn.close()

    return messages, unread_messages[0]

async def mark_message_viewed_bulk(user: str, conversation_id: str, offset: int) -> None:
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
    conn = get_connection()
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
    conn.close()

async def get_delete_messages() -> list:
    """
    ## Get Delete Messages
    Get messages that are due to be deleted.

    ### Parameters
    None

    ### Returns
    - list: list of messages that should be deleted.
    """
    # Create/ensure database connection
    conn = get_connection()
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
    conn.close()

    data = []

    for message in messages:
        data.append({"conversation_id": message[0], "message_id": message[1]})

    return data

async def destruct_messages() -> None:
    """
    ## Destruct Messages
    Deletes all messages that are ready to be self-destructed.

    ### Parameters
    None

    ### Returns
    None
    """
    # Create/ensure database connection
    conn = get_connection()
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
    conn.close()

async def get_message(message_id: str) -> dict:
    """
    ## Get Message
    Get a message from the database based on its id.

    ### Parameters
    message_id: the id for the message.

    ### Returns
    - dict: message from the database.
    """
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SElECT * FROM messages WHERE message_id = %s", (message_id,))
    message = cursor.fetchone()
    conn.close()

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
    
async def view_message(message_id: str) -> None:
    """
    ## View Message
    Marks a message in a conversation as viewed.

    ### Parameters
    message_id: the id for the message.

    ### Returns
    None
    """
    # Create/ensure database connection
    conn = get_connection()
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

    conn.close()

async def get_messages_after(message_id: str, conversation_id: str) -> list:
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
    conn = get_connection()
    cursor = conn.cursor()

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
    conn.close()

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