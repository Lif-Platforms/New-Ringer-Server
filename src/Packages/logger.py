# -----------------------
# package info: this package is for formatting logs sent to the console 
# author: Superior126
#------------------------

#Imports libraries 
import datetime
import time
from termcolor import colored

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

# Function for showing a warning
def showWarning(message):
    # Gets the prefix for logging messages 
    prefix = getPrefix("WARN")

    # Formats the message
    log = prefix + message

    # Displays the prefix 
    print(colored(log, "yellow"))

# Function for showing a warning
def showError(message):
    # Gets the prefix for logging messages 
    prefix = getPrefix("ERR")

    # Formats the message
    log = prefix + message

    # Displays the prefix 
    print(colored(log, "red"))