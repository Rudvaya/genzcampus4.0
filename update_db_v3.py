import sqlite3
import os

def update_database_v3():
    # Use absolute path relative to this script
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'pms.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Update TeamMember table to add 'role' column
        print("Updating TeamMember table...")
        cursor.execute("PRAGMA table_info(team_member)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'role' not in columns:
            print("Adding 'role' column to team_member...")
            cursor.execute("ALTER TABLE team_member ADD COLUMN role VARCHAR(20) DEFAULT 'member'")
            print("Column added successfully.")
        else:
            print("'role' column already exists.")

        conn.commit()
        print("Database updated to v3 successfully!")

    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_database_v3()
