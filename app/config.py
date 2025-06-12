import os
import yaml

# Define default values for the config
config_template = {
    "mysql-host": "localhost",
    "mysql-port": 3306,
    "mysql-user": "root",
    "mysql-password": "test123",
    "mysql-database": "Lif_Accounts",
    "mysql-ssl": False,
    "mysql-cert-path": "INSERT PATH HERE",
    "auth-server-url": "INSERT URL HERE",
    "safe-browsing-api-key": "INSERT API KEY HERE",
    "giphy-api-key": "INSERT API KEY HERE"
}

def init_config():
    """
    Initialize the config file with default values if it doesn't exist.
    If it does exist, ensure all default values are present.
    """
    # Check if config file exists
    # If not, create it and add default values
    if not os.path.isfile("config.yml"):
        # Create config file with default values
        with open("config.yml", 'x') as config:
            config.write(yaml.safe_dump(config_template))
            config.close()
    else:
        # Load existing config file
        with open("config.yml", "r") as config:
            contents = config.read()
            configurations = yaml.safe_load(contents)
            config.close()

        # Ensure the configurations are not None
        if configurations is None:
            configurations = {}

        # Compare config with default template and add missing options
        for option in config_template:
            if option not in configurations:
                configurations[option] = config_template[option]

        # Write updated config back to file
        with open("config.yml", "w") as config:
            new_config = yaml.safe_dump(configurations)
            config.write(new_config)
            config.close()

def get_config(key: str = None):
    """
    Load the config file and return the configurations.
    Parameters:
        key (str): Optional key to retrieve a specific configuration value.
    Returns:
        dict or any: The configurations dictionary or a specific value if key is provided.
    """
    # Load the config file and return the configurations
    with open("config.yml", "r") as config:
        contents = config.read()
        configurations = yaml.safe_load(contents)
        config.close()

    # If a key is provided, return the specific configuration value
    if key is not None:
        return configurations.get(key, None)
    
    return configurations