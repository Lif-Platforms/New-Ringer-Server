import sqlite3
import yaml
import json
import uuid

# Loads Config
with open("src/config.yml", "r") as config:
    configuration = yaml.safe_load(config)

def get_friends_list(account):
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM accounts")
    items = c.fetchall()

    conn.close()

    friends_list = False

    # Searches for account
    for db_account in items: 
        database_account = db_account[0]

        if account == database_account:
            friends_list = db_account[2]

    return friends_list

def get_friend_requests(account):
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM accounts")
    items = c.fetchall()

    conn.close()

    requests_list = False

    # Searches for account
    for db_account in items: 
        database_account = db_account[0]

        if account == database_account:
            requests_list = db_account[1]

    return requests_list

def add_new_friend(account, username): 
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM accounts")
    items = c.fetchall()

    for item in items:
        database_account = item[0]

        if account == database_account:
            requests = json.loads(item[1])

            requests.append({'name': username})

            conn.execute(f"""UPDATE accounts SET FreindRequests = '{json.dumps(requests)}'
                                        WHERE Account = '{account}'""")
            
    conn.commit()
    conn.close()

def accept_friend(account, friend): 
    print("accepting friend request")
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM accounts")
    items = c.fetchall()

    # Generates a conversation id
    conversation_id = str(uuid.uuid4())

    # Removes friend from pending requests
    for item in items:
        database_account = item[0]

        if database_account == account:
            requests = json.loads(item[1])
            new_requests_list = list(filter(lambda item: item["name"] != friend, requests))

            conn.execute(f"""UPDATE accounts SET FreindRequests = '{json.dumps(new_requests_list)}'
                                        WHERE Account = '{account}'""")
            
            # Adds user to current friends
            friends = json.loads(item[2])
            friends.append({"Username": friend, "Id": conversation_id})

            # Updates in database
            conn.execute(f"""UPDATE accounts SET Friends = '{json.dumps(friends)}'
                                        WHERE Account = '{account}'""")
            
            # Creates a new conversation for the two users
            conn.execute("INSERT INTO conversations (Id, Members, Messages) VALUES (?, ?, ?)", (conversation_id, json.dumps([account, friend]), "[]"))

    # Adds request to senders friends list
    for item in items:
        database_account = item[0]

        if database_account == friend:
             # Adds user to current friends
            friends = json.loads(item[2])
            friends.append({"Username": account, "Id": conversation_id})

            # Updates in database
            conn.execute(f"""UPDATE accounts SET Friends = '{json.dumps(friends)}'
                                        WHERE Account = '{friend}'""")

    conn.commit()
    conn.close()

def send_message(author, conversation_id, message):
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM conversations")
    items = c.fetchall()

    for item in items:
        database_conversation = item[0]

        if database_conversation == conversation_id:
            data = json.loads(item[2])

            append_data = {"Author": author, "Message": message}

            data.append(append_data)

            # Updates in database
            conn.execute(f"""UPDATE conversations SET Messages = '{json.dumps(data)}'
                                        WHERE Id = '{conversation_id}'""")
    conn.commit()
    conn.close()
            
def get_messages(conversation_id: str):
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM conversations")
    items = c.fetchall()

    messages = False

    # Find conversation
    for item in items:
        database_conversation_id = item[0]

        if conversation_id == database_conversation_id:
            messages = json.loads(item[2])

    return messages

def get_members(conversation_id: str):
    # Connects to database
    conn = sqlite3.connect(configuration['Path-To-Database'])
    c = conn.cursor()

    # Gets all data from the database
    c.execute("SELECT * FROM conversations")
    items = c.fetchall()

    members = False

    # Find conversation
    for item in items:
        database_conversation_id = item[0]

        if conversation_id == database_conversation_id:
            members = json.loads(item[1])

    return members