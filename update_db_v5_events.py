import sqlite3
import os

db_path = 'instance/pms.db'

if not os.path.exists(db_path):
    print("Database not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Updating database schema...")

# Update Event table
try:
    cursor.execute("ALTER TABLE event ADD COLUMN payment_model VARCHAR(20) DEFAULT 'individual'")
    print("Added payment_model to event")
except sqlite3.OperationalError as e:
    print(f"payment_model likely exists: {e}")

try:
    cursor.execute("ALTER TABLE event ADD COLUMN total_collected FLOAT DEFAULT 0.0")
    print("Added total_collected to event")
except sqlite3.OperationalError as e:
    print(f"total_collected likely exists: {e}")

try:
    cursor.execute("ALTER TABLE event ADD COLUMN total_settled FLOAT DEFAULT 0.0")
    print("Added total_settled to event")
except sqlite3.OperationalError as e:
    print(f"total_settled likely exists: {e}")

# Update Team table
try:
    cursor.execute("ALTER TABLE team ADD COLUMN is_paid BOOLEAN DEFAULT 0")
    print("Added is_paid to team")
except sqlite3.OperationalError as e:
    print(f"is_paid likely exists: {e}")

conn.commit()
conn.close()
print("Database update complete.")
