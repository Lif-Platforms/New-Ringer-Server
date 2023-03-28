import asyncio
import websockets
import json
import sqlite3
import secrets
# Import Packages
import Packages.passwordHasher as PasswordHasher

async def handle(websocket, path):
    global requestedCredentials
    try:
        async for message in websocket:
            # Handle incoming messages
            print(f"Received message: {message}")
            
            # Checks if the user has requested a login
            if message == "USER_LOGIN":
                # Connects to the database
                conn = sqlite3.connect('account.db')
                c = conn.cursor()

                # Requests login credentials from the client
                await websocket.send("SEND_CREDENTIALS")
                
                # Waits for the client to send the login credentials
                credentials = await websocket.recv()

                # Converts the string sent from the client into a python dictionary
                loadCredentials = json.loads(credentials)

                print(loadCredentials)

                # Gets all accounts from database
                c.execute("SELECT * FROM accounts")
                items = c.fetchall()
                conn.commit()

                # Cycles through the accounts to check the credentials given by the user
                for item in items:
                    # Defines the username and password from the database
                    databaseUser = item[0]
                    databasePass = item[1]

                    # Defines the username and password given by the user
                    username = loadCredentials['Username']
                    # Hashes the password given by the user
                    password = PasswordHasher.get_initial_hash(loadCredentials['Password'])

                    # Sets "foundAccount" to false. If the account is found it will be set to true
                    foundAccount = False

                    # Checks if the username and password match the database
                    if username == databaseUser and password == databasePass:
                        # Sets "foundAccount" to true if the user credentials match the database and breaks the loop
                        foundAccount = True
                        break

                # Checks if the account was found in the database and tells the client that information
                if foundAccount == True:
                    # Tells the client that the login was successful 
                    await websocket.send("LOGIN_GOOD")

                    # Waits for the client to request a login token
                    tokenRequest = await websocket.recv()

                    # Checks if the client requested a login token
                    if tokenRequest == "TOKEN":
                        # Generates and sends the token
                        token = str(secrets.token_hex(16 // 2))
                        await websocket.send("TOKEN:" + token)

                        # Updates the token in the database
                        conn.execute(f"""UPDATE accounts SET Token = '{token}'
                            WHERE Username = '{username}'""")
                        
                        print("Executing query")

                        conn.commit()
                        conn.close()
                else:
                    # Tells the client the login was not successful 
                    await websocket.send("INVALID_CREDENTIALS")
                    # Closes the connection with the client
                    await websocket.close()

            # Checks if the client has requested to add a friend
            if message == "SEND_FRIEND_REQUEST":
                # Connects to the database
                conn = sqlite3.connect('account.db')
                c = conn.cursor()

                # Requests the user from the client
                await websocket.send("USER?")

                # Waits for the client to send the user
                user = await websocket.recv()

                # Loads the data sent from the client
                loadUser = json.loads(user)

                # Defines who the request is to and from
                fromUser = loadUser['From']
                toUser = loadUser['To']

                # Defines the token from the user
                userToken = loadUser['Token']

                # Gets all data from the database
                c.execute("SELECT * FROM accounts")
                items = c.fetchall()
                print("item")

                # Tells the server whether or not the user exists
                foundUser = False

                # Checks if the user the request is to exists
                for user in items:
                    findUser = user[0]
                    if findUser == toUser:
                        foundUser = True
                        recipient_data = user  # store the recipient's data
                        break

                # Checks if the user was found
                if foundUser:
                    # Tells the server whether or not the token was correct
                    foundToken = False

                    # Checks the sender's token
                    for token in items:
                        findToken = token[4]
                        checkUser = token[0]
                        if findToken == userToken and checkUser == fromUser:
                            print("found token")
                            foundToken = True
                            break

                    # Checks if the token was correct
                    if foundToken:
                        # Defines the request inbox
                        # Will be reassigned once it is found
                        friendRequestInbox = False

                        # Get the recipient's friend request inbox
                        findUser = recipient_data[0]
                        friendRequestInbox = json.loads(recipient_data[3])

                        # Gets the list of friend requests
                        requestsList = friendRequestInbox["Requests"]

                        # Adds the friend request to the list
                        requestsList.append(fromUser)

                        # Defines new requests list
                        newRequestsList = {"Requests": requestsList}

                        # Updates the database
                        conn.execute(f"""UPDATE accounts SET FreindRequests = '{json.dumps(newRequestsList)}'
                                        WHERE Username = '{toUser}'""")
                        conn.commit()

                        # Tells the client the request was sent
                        await websocket.send("REQUEST_SENT!")

                        conn.close()
                    else:
                        await websocket.send("INVALID_TOKEN")
                        conn.close()
                else:
                    # Tells the client the user does not exist
                    await websocket.send("USER_NO_EXIST")
                    conn.close()

            # Checks if the user has requested to create an account
            if message == "CREATE_ACCOUNT":
                # Requests credentials from client
                await websocket.send("CREDENTIALS?")

                # Waits for the client to send the credentials
                credentials = await websocket.recv()

                # Converts the string sent from the client into a python dictionary
                loadCredentials = json.loads(credentials)

                # Defines username sent by the client
                username = loadCredentials['Username']    

                # Defines email given by the client 
                email = loadCredentials['Email']

                # Defines and hashes password given by the client
                password = PasswordHasher.get_initial_hash(loadCredentials['Password'])

                # Gets all data from the database
                c.execute("SELECT * FROM accounts")
                items = c.fetchall()

                # Tells the server wether or not to continue the account creation after the account has been checked 
                continueCreation = True

                # Checks to make sure the account doesn't already exist.
                for item in items:
                    findUser = item[0]
                    if findUser == username:
                        await websocket.send('ERROR_ACCOUNT_EXISTING')
                        continueCreation = False  
                        break
                
                # If the account does not already exist then it will continue the creation
                if continueCreation == True:
                    # Inserts credentials into the database
                    data = (username, password, email, '{"Requests":[]}', "")
                    c.execute(f"INSERT INTO accounts VALUES (?,?,?,?,?)", data)
                    conn.commit()

                    # Tells the client the account has been created
                    await websocket.send("ACCOUNT_CREATED")

                    # Closes the connection
                    await websocket.close()

            # Checks if the client has requested a list of incoming friend requests
            if message == "LIST_FRIEND_REQUESTS":
                # Asks the client for their username and token
                await websocket.send("VERIFY?")

                # Waits for clients response
                request = await websocket.recv()

                # Loads the request
                loadRequest = json.loads(request)

                # Extracts information from loaded request
                username = loadRequest['Username']
                token = loadRequest['Token']

                # Connects to the database
                conn = sqlite3.connect('account.db')
                c = conn.cursor()

                # Gets all data from the database
                c.execute("SELECT * FROM accounts")
                items = c.fetchall()

                foundToken = False

                 # Checks the sender's token
                for token in items:
                    findToken = token[4]
                    checkUser = token[0]
                    if findToken == token and checkUser == username:
                        print("found token")
                        foundToken = True
                        break

                # Checks if the token was found
                if findToken: 
                    # Grabs the incoming friend requests from the database
                    for user in items:
                        databaseUser = user[0]
                        if databaseUser == username:
                            friendRequestsList = user[3]
                            break

                    # Sends the data to the client
                    await websocket.send(friendRequestsList)

                else:
                    # Tells the client that their token is invalid
                    await websocket.send("INVALID_TOKEN")

    except websockets.exceptions.ConnectionClosedError:
        # Handle the case where the connection is closed unexpectedly
        print("Connection closed unexpectedly")

async def start_server():
    async with websockets.serve(handle, "localhost", 8000):
        print("WebSocket server started")
        await asyncio.Future()  # Keep the server running indefinitely

asyncio.run(start_server())
