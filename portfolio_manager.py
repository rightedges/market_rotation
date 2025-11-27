import json
import os
from database import get_db

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
    Loads user data (holdings + config) from DB.
    Returns: (holdings, config)
    """
    conn = get_db()
    c = conn.cursor()
    
    # Get User ID
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    user_row = c.fetchone()
    
    if not user_row:
        conn.close()
        return get_default_holdings(), get_default_config()
        
    user_id = user_row['id']
    
    # Get Holdings
    c.execute("SELECT ticker, weight FROM portfolios WHERE user_id = ?", (user_id,))
    rows = c.fetchall()
    
    if rows:
        holdings = {row['ticker']: row['weight'] for row in rows}
    else:
        holdings = get_default_holdings()
        
    # Get Config
    c.execute("SELECT backtest_period FROM user_configs WHERE user_id = ?", (user_id,))
    config_row = c.fetchone()
    
    config = get_default_config()
    if config_row:
        config['backtest_period'] = config_row['backtest_period']
        
    conn.close()
    return holdings, config

def save_user_data(username, holdings, config):
    """Saves user data (holdings + config) to DB."""
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Get User ID
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = c.fetchone()
        
        if not user_row:
            conn.close()
            return False
            
        user_id = user_row['id']
        
        # Save Holdings (Transaction)
        # First, delete existing holdings for this user (simplest way to handle removals)
        # Or better, upsert? Deleting and re-inserting is cleaner for "full replacement" logic
        c.execute("DELETE FROM portfolios WHERE user_id = ?", (user_id,))
        
        for ticker, weight in holdings.items():
            c.execute("INSERT INTO portfolios (user_id, ticker, weight) VALUES (?, ?, ?)",
                      (user_id, ticker, weight))
                      
        # Save Config
        backtest_period = config.get('backtest_period', '5y')
        c.execute("INSERT OR REPLACE INTO user_configs (user_id, backtest_period) VALUES (?, ?)",
                  (user_id, backtest_period))
                  
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving user data: {e}")
        conn.close()
        return False

# Backward compatibility aliases
def load_portfolio(username):
    h, _ = load_user_data(username)
    return h

def save_portfolio(username, weights):
    # We need to load existing config to preserve it
    _, config = load_user_data(username)
    return save_user_data(username, weights, config)
