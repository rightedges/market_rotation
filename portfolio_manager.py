import json
import os

DATA_DIR = "data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_portfolio_file(username):
    return os.path.join(DATA_DIR, f"{username}_portfolio.json")

def get_default_holdings():
    """Returns the default base weights."""
    return {
        'VOO': 0.40,
        'BRK-B': 0.20,
        'SPMO': 0.20,
        'QQQM': 0.20
    }

def get_default_config():
    """Returns the default configuration."""
    return {
        'backtest_period': '5y'
    }

def load_user_data(username):
    """
    Loads user data (holdings + config) from file.
    Migrates old format (just holdings) to new format if necessary.
    Returns: (holdings, config)
    """
    filepath = get_portfolio_file(username)
    default_holdings = get_default_holdings()
    default_config = get_default_config()

    if not os.path.exists(filepath):
        return default_holdings, default_config
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Check if it's the new format
        if 'holdings' in data:
            holdings = data['holdings']
            config = data.get('config', default_config)
            # Ensure config has all keys
            for k, v in default_config.items():
                if k not in config:
                    config[k] = v
            return holdings, config
        else:
            # Old format: data is just holdings
            # Migrate to new format
            new_data = {
                'holdings': data,
                'config': default_config
            }
            save_user_data(username, new_data['holdings'], new_data['config'])
            return new_data['holdings'], new_data['config']

    except (json.JSONDecodeError, IOError):
        return default_holdings, default_config

def save_user_data(username, holdings, config):
    """Saves user data (holdings + config) to file."""
    filepath = get_portfolio_file(username)
    data = {
        'holdings': holdings,
        'config': config
    }
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except IOError:
        return False

# Backward compatibility aliases (optional, but good for safety if I miss a spot)
def load_portfolio(username):
    h, _ = load_user_data(username)
    return h

def save_portfolio(username, weights):
    # We need to load existing config to preserve it
    _, config = load_user_data(username)
    return save_user_data(username, weights, config)
