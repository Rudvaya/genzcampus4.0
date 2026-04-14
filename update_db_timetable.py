import sqlite3
import os

def update_timetable_db():
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'pms.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Updating TimeTable table...")
        cursor.execute("PRAGMA table_info(time_table)")
        columns = [info[1] for info in cursor.fetchall()]
        
        new_columns = [
            ('period_1_time', "09:30 - 10:20"),
            ('period_2_time', "10:20 - 11:10"),
            ('period_3_time', "11:10 - 12:00"),
            ('period_4_time', "01:00 - 01:50"),
            ('period_5_time', "01:50 - 02:40"),
            ('period_6_time', "02:40 - 03:30"),
            ('period_7_time', "03:30 - 04:20")
        ]

        for col_name, default_val in new_columns:
            if col_name not in columns:
                print(f"Adding column {col_name}...")
                cursor.execute(f"ALTER TABLE time_table ADD COLUMN {col_name} TEXT DEFAULT '{default_val}'")

        conn.commit()
        print("TimeTable table updated successfully!")

    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_timetable_db()
