import json
import os
import bcrypt

USERS_FILE = "users.json"

def load_users():
    """Loads users from file."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_users(users):
    """Saves users to file."""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        return True
    except IOError:
        return False

def hash_password(password):
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Checks a password against a hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username, password):
    """Registers a new user. Returns (Success, Message)."""
    users = load_users()
    if username in users:
        return False, "Username already exists."
    
    hashed = hash_password(password)
    users[username] = hashed
    
    if save_users(users):
        return True, "User registered successfully."
    else:
        return False, "Failed to save user database."

def authenticate_user(username, password):
    """Authenticates a user. Returns True if valid."""
    users = load_users()
    if username not in users:
        return False
    
    hashed = users[username]
    return check_password(password, hashed)
