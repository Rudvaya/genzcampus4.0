from app import app, db
from sqlalchemy import text

def add_column():
    with app.app_context():
        try:
            # Check if column already exists
            db.session.execute(text("SELECT declared_size FROM team LIMIT 1"))
            print("Column 'declared_size' already exists in 'team' table.")
        except Exception:
            try:
                # Add the column
                db.session.execute(text("ALTER TABLE team ADD COLUMN declared_size INTEGER DEFAULT 1"))
                db.session.commit()
                print("Successfully added 'declared_size' column to 'team' table.")
            except Exception as e:
                print(f"Error adding column: {e}")
                db.session.rollback()

if __name__ == "__main__":
    add_column()
