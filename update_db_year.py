import sqlite3
import os

def update_database():
    # Use absolute path relative to this script
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'pms.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Update User table
        print("Checking User table...")
        cursor.execute("PRAGMA table_info(user)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'year' not in columns:
            print("Adding 'year' column to user...")
            cursor.execute("ALTER TABLE user ADD COLUMN year INTEGER")
            print("Column added to user successfully.")
        else:
            print(" 'year' column already exists in user.")

        # 2. Update ClassAttendance table
        print("Checking ClassAttendance table...")
        cursor.execute("PRAGMA table_info(class_attendance)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'year' not in columns:
            print("Adding 'year' column to class_attendance...")
            cursor.execute("ALTER TABLE class_attendance ADD COLUMN year INTEGER NOT NULL DEFAULT 1")
            print("Column added to class_attendance successfully.")
        else:
            print(" 'year' column already exists in class_attendance.")

        conn.commit()
        print("Database updated successfully!")

    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_database()
