# -----------------------
# package info: this package is for formatting logs sent to the console 
# author: Superior126
#------------------------

#Imports libraries 
import datetime
import time
from termcolor import colored
import uuid 
import yaml

# Generates a session id
sessionId = uuid.uuid4()

# using now() to get current time
current_time = datetime.datetime.now()

# Defines date variables
month = current_time.month
day = current_time.day
year = current_time.year

# Formats the date
date = f"{month}-{day}-{year}"

# Loads config
with open("src/config.yml", "r") as config:
    configuration = yaml.safe_load(config)

# Checks if save logs is enabled
if configuration['Save-Logs']:
    # Creates new log file 
    logFile = open(f"{configuration['Path-To-Logs']}/{date}={sessionId}", "a")
    logFile.close()

# Function for getting the prefix for the logs
def getPrefix(type):
    # using now() to get current time
    current_time = datetime.datetime.now()

    # Defines date variables
    month = current_time.month
    day = current_time.day
    year = current_time.year

    # Formats the date
    date = f"{month}-{day}-{year}"

    # Defines time variable
    curr_time = time.strftime("%H:%M:%S", time.localtime())

    # Defines the prefix for the logs
    prefix = f"[{date} {curr_time}][{type}]: "

    # Returns the prefix
    return prefix

# Defines function for showing info in the console
def showInfo(message):
    # Gets the prefix for logging messages 
    prefix = getPrefix("LOG")

    # Formats the message
    log = prefix + message
    
    # Displays the prefix 
    print(colored(log, "white"))

    # Checks if saved logs is enabled in the config
    if configuration['Save-Logs'] == True: 
        # Saves the log
        logFile = open(f"{configuration['Path-To-Logs']}/{date}={sessionId}", "a")
        logFile.write(log + "\n")
        logFile.close()

# Function for showing a warning
def showWarning(message):
    # Gets the prefix for logging messages 
    prefix = getPrefix("WARN")

    # Formats the message
    log = prefix + message

    # Displays the prefix 
    print(colored(log, "yellow"))

    # Checks if saved logs is enabled in the config
    if configuration['Save-Logs'] == True: 
        # Saves the log
        logFile = open(f"{configuration['Path-To-Logs']}/{date}={sessionId}", "a")
        logFile.write(log + "\n")
        logFile.close()

# Function for showing a warning
def showError(message):
    # Gets the prefix for logging messages 
    prefix = getPrefix("ERR")

    # Formats the message
    log = prefix + message

    # Displays the prefix 
    print(colored(log, "red"))

    # Checks if saved logs is enabled in the config
    if configuration['Save-Logs'] == True: 
        # Saves the log
        logFile = open(f"{configuration['Path-To-Logs']}/{date}={sessionId}", "a")
        logFile.write(log + "\n")
        logFile.close()