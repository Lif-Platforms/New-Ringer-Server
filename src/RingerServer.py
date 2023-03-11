import asyncio
import websockets
import json
import sqlite3
# Import Packages
import Packages.passwordHasher as PasswordHasher

# Global Variables 

global conn
global c
conn = sqlite3.connect('account.db')
c = conn.cursor()

async def handle(websocket, path):
    global requestedCredentials
    try:
        async for message in websocket:
            # Handle incoming messages
            print(f"Received message: {message}")
            
            # Checks if the user has requested a login
            if message == "USER_LOGIN":
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
                else:
                    # Tells the client the login was not successful 
                    await websocket.send("INVALID_CREDENTIALS")
                    # Closes the connection with the client
                    await websocket.close()

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
                        websocket.send('ERROR_ACCOUNT_EXISTING')
                        continueCreation = False  
                        break
                
                # If the account does not already exist then it will continue the creation
                if continueCreation == True:
                    # Inserts credentials into the database
                    data = (username, password, email, '{"contacts":[]}')
                    c.execute(f"INSERT INTO accounts VALUES (?,?,?,?)", data)
                    conn.commit()

                    # Tells the client the account has been created
                    await websocket.send("ACCOUNT_CREATED")

                    # Closes the connection
                    await websocket.close()

    except websockets.exceptions.ConnectionClosedError:
        # Handle the case where the connection is closed unexpectedly
        print("Connection closed unexpectedly")

async def start_server():
    async with websockets.serve(handle, "localhost", 8000):
        print("WebSocket server started")
        await asyncio.Future()  # Keep the server running indefinitely

asyncio.run(start_server())
