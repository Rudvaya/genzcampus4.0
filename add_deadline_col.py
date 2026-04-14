from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Check if column exists
        db.session.execute(text("SELECT registration_deadline FROM event LIMIT 1"))
        print("Column 'registration_deadline' already exists.")
    except Exception:
        db.session.rollback()
        print("Adding 'registration_deadline' column to 'event' table...")
        db.session.execute(text("ALTER TABLE event ADD COLUMN registration_deadline DATETIME"))
        db.session.commit()
        print("Column added successfully.")
