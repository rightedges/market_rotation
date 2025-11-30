import sqlite3
import os

# Database path
DB_PATH = os.path.join('instance', 'portfolio.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(portfolio)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'analysis_trend_weight' not in columns:
            print("Adding analysis_trend_weight column...")
            cursor.execute("ALTER TABLE portfolio ADD COLUMN analysis_trend_weight FLOAT DEFAULT 0.10")
        else:
            print("analysis_trend_weight column already exists.")

        if 'analysis_relative_strength_weight' not in columns:
            print("Adding analysis_relative_strength_weight column...")
            cursor.execute("ALTER TABLE portfolio ADD COLUMN analysis_relative_strength_weight FLOAT DEFAULT 0.05")
        else:
            print("analysis_relative_strength_weight column already exists.")

        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
