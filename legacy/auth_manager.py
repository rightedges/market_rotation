import bcrypt
from database import get_db
import sqlite3

def hash_password(password):
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Checks a password against a hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username, password):
    """Registers a new user. Returns (Success, Message)."""
    conn = get_db()
    c = conn.cursor()
    
    hashed = hash_password(password)
    
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed))
        conn.commit()
        conn.close()
        return True, "User registered successfully."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists."
    except Exception as e:
        conn.close()
        return False, f"Registration failed: {str(e)}"

def authenticate_user(username, password):
    """Authenticates a user. Returns True if valid."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    
    if row is None:
        return False
    
    hashed = row['password_hash']
    return check_password(password, hashed)
