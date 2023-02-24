# -----------------------
# package info: this package is for hashing passwords before comparing them to the database 
# author: Superior126
#------------------------
import hashlib

def get_initial_hash(password):
    salt = "5gz"
  
    # Adding salt at the last of the password
    dataBase_password = password+salt
    # Encoding the password
    hashed = hashlib.sha256(dataBase_password.encode())
  
    return hashed.hexdigest()