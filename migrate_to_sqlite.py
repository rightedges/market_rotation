import json
import os
import glob
from database import get_db, init_db

def migrate_users():
    print("Migrating users...")
    if not os.path.exists("users.json"):
        print("No users.json found.")
        return

    with open("users.json", 'r') as f:
        try:
            users = json.load(f)
        except json.JSONDecodeError:
            print("users.json is empty or invalid.")
            return

    conn = get_db()
    c = conn.cursor()
    
    for username, password_hash in users.items():
        try:
            c.execute("INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)", 
                      (username, password_hash))
            print(f"Migrated user: {username}")
        except Exception as e:
            print(f"Error migrating user {username}: {e}")
            
    conn.commit()
    conn.close()

def migrate_portfolios():
    print("Migrating portfolios...")
    conn = get_db()
    c = conn.cursor()
    
    # Find all portfolio files
    files = glob.glob("data/*_portfolio.json")
    
    for filepath in files:
        filename = os.path.basename(filepath)
        username = filename.replace("_portfolio.json", "")
        
        # Get user ID
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        user_row = c.fetchone()
        
        if not user_row:
            print(f"Skipping portfolio for unknown user: {username}")
            continue
            
        user_id = user_row['id']
        
        with open(filepath, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Skipping invalid JSON: {filepath}")
                continue
        
        # Handle old vs new format
        holdings = {}
        config = {}
        
        if 'holdings' in data:
            holdings = data['holdings']
            config = data.get('config', {})
        else:
            holdings = data
            
        # Insert holdings
        for ticker, weight in holdings.items():
            try:
                c.execute("INSERT OR REPLACE INTO portfolios (user_id, ticker, weight) VALUES (?, ?, ?)",
                          (user_id, ticker, weight))
            except Exception as e:
                print(f"Error inserting holding {ticker} for {username}: {e}")
                
        # Insert config
        backtest_period = config.get('backtest_period', '5y')
        try:
            c.execute("INSERT OR REPLACE INTO user_configs (user_id, backtest_period) VALUES (?, ?)",
                      (user_id, backtest_period))
        except Exception as e:
            print(f"Error inserting config for {username}: {e}")
            
        print(f"Migrated portfolio for: {username}")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # Ensure DB exists
    init_db()
    
    migrate_users()
    migrate_portfolios()
    print("Migration complete.")
