import mysql.connector
from mysql.connector import ClientFlag
from config import get_config

def get_connection():
    """
    Establish a connection to the MySQL database using the configurations from config.py.
    """

    # Load the configuration
    config = get_config()

    # Get the MySQL connection parameters
    mysql_config = {
        "host": config['mysql-host'],
        "port": config['mysql-port'],
        "user": config['mysql-user'],
        "password": config['mysql-password'],
        "database": config['mysql-database'], 
    }

    # Check if SSL is enabled
    # If so, add it to the config
    if config['mysql-ssl']:
        mysql_config['client_flags'] = [ClientFlag.SSL]
        mysql_config['ssl_ca'] = config['mysql-cert-path']

    # Create a connection to the database
    connection = mysql.connector.connect(**mysql_config)

    return connection