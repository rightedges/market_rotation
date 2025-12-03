import sqlite3
import os

DB_FILE = 'instance/portfolio.db'

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found. Skipping migration.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(portfolio)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'analysis_benchmark_weight' not in columns:
        print("Adding 'analysis_benchmark_weight' column to 'portfolio' table...")
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN analysis_benchmark_weight FLOAT")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("Column 'analysis_benchmark_weight' already exists.")

    if 'analysis_benchmark_ticker' not in columns:
        print("Adding 'analysis_benchmark_ticker' column to 'portfolio' table...")
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN analysis_benchmark_ticker VARCHAR(10)")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("Column 'analysis_benchmark_ticker' already exists.")

    if 'analysis_relaxed_mode' not in columns:
        print("Adding 'analysis_relaxed_mode' column to 'portfolio' table...")
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN analysis_relaxed_mode BOOLEAN DEFAULT 0")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("Column 'analysis_relaxed_mode' already exists.")
        
    if 'fixed_analysis_frequency' not in columns:
        print("Adding 'fixed_analysis_frequency' column to 'portfolio' table...")
        try:
            cursor.execute("ALTER TABLE portfolio ADD COLUMN fixed_analysis_frequency VARCHAR(20) DEFAULT 'quarterly'")
            conn.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed: {e}")
    else:
        print("Column 'fixed_analysis_frequency' already exists.")

    conn.close()

if __name__ == "__main__":
    migrate()
