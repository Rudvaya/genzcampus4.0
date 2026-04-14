from app import app, db
from sqlalchemy import text

def add_column():
    with app.app_context():
        try:
            # Check if column already exists
            db.session.execute(text("SELECT max_registrations FROM event LIMIT 1"))
            print("Column 'max_registrations' already exists in 'event' table.")
        except Exception:
            try:
                # Add the column
                db.session.execute(text("ALTER TABLE event ADD COLUMN max_registrations INTEGER DEFAULT 0"))
                db.session.commit()
                print("Successfully added 'max_registrations' column to 'event' table.")
            except Exception as e:
                print(f"Error adding column: {e}")
                db.session.rollback()

if __name__ == "__main__":
    add_column()
