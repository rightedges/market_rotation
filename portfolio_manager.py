import json
import os

DATA_DIR = "data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_portfolio_file(username):
    return os.path.join(DATA_DIR, f"{username}_portfolio.json")

def get_default_portfolio():
    """Returns the default base weights."""
    return {
        'VOO': 0.40,
        'BRK-B': 0.20,
        'SPMO': 0.20,
        'QQQM': 0.20
    }

def load_portfolio(username):
    """Loads portfolio from file or returns default if file doesn't exist."""
    filepath = get_portfolio_file(username)
    if not os.path.exists(filepath):
        return get_default_portfolio()
    
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Fallback to default if file is corrupted
        return get_default_portfolio()

def save_portfolio(username, weights):
    """Saves portfolio weights to file."""
    filepath = get_portfolio_file(username)
    try:
        with open(filepath, 'w') as f:
            json.dump(weights, f, indent=4)
        return True
    except IOError:
        return False
