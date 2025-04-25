from connections import get_connection
import exceptions
import json

async def get_members(conversation_id: str) -> list:
    # Create/ensure database connection
    conn = get_connection()
    cursor = conn.cursor()

    # Gets all data from the database
    cursor.execute("SELECT * FROM conversations WHERE conversation_id = %s", (conversation_id,))
    conversation = cursor.fetchone()
    conn.close()

    # Check if conversation exists
    if not conversation:
        raise exceptions.ConversationNotFound()

    # Get and return conversation members
    members = json.loads(conversation[2])
    return members

async def remove_conversation(self, conversation_id: str, username: str) -> None:
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
    
    # Get conversation members
    conversation_members = json.loads(conversation[2])

    # Check if user is a member of this conversation
    if not username in conversation_members:
        conn.close()
        raise exceptions.NoPermission()
    
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

    # Close db connection once complete
    conn.close()

async def fetch_last_messages(conversation_ids: list) -> list:
    """
    ## Fetch Last Messages
    Fetches the most recent message for each conversation id.

    ### Parameters
    conversation_id: list of conversation ids to fetch messages from.

    ### Returns
    list: list of messages.
    """
    # Create/ensure database connection
    conn = get_connection()
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

    conn.close()
    return messages