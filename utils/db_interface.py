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

    # Removes friend from pending requests
    for item in items:
        database_account = item[0]

        if database_account == account:
            requests = json.loads(item[1])
            new_requests_list = list(filter(lambda item: item["name"] != friend, requests))

            conn.execute(f"""UPDATE accounts SET FreindRequests = '{json.dumps(new_requests_list)}'
                                        WHERE Account = '{account}'""")
            
            # Generates a conversation id
            conversation_id = str(uuid.uuid4())

            # Adds user to current friends
            friends = json.loads(item[2])
            friends.append({"Username": friend, "Id": conversation_id})

            # Updates in database
            conn.execute(f"""UPDATE accounts SET Friends = '{json.dumps(friends)}'
                                        WHERE Account = '{account}'""")
            
            # Creates a new conversation for the two users
            conn.execute("INSERT INTO conversations (Id, Members, Messages) VALUES (?, ?, ?)", (conversation_id, json.dumps([account, friend]), "[]"))

    conn.commit()
    conn.close()