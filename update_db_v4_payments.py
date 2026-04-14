from app import app
from models import db, Event, EventResponse, Club, SystemConfig
from sqlalchemy import text

def update_db():
    with app.app_context():
        # Add columns to Club
        try:
            db.session.execute(text("ALTER TABLE club ADD COLUMN pending_settlement FLOAT DEFAULT 0.0"))
            print("Added pending_settlement to Club")
        except Exception as e:
            print(f"Club update: {e}")

        # Add columns to Event
        try:
            db.session.execute(text("ALTER TABLE event ADD COLUMN is_paid BOOLEAN DEFAULT 0"))
            db.session.execute(text("ALTER TABLE event ADD COLUMN amount FLOAT DEFAULT 0.0"))
            print("Added is_paid and amount to Event")
        except Exception as e:
            print(f"Event update: {e}")

        # Add columns to EventResponse
        try:
            db.session.execute(text("ALTER TABLE event_response ADD COLUMN payment_status VARCHAR(20) DEFAULT 'free'"))
            db.session.execute(text("ALTER TABLE event_response ADD COLUMN razorpay_order_id VARCHAR(100)"))
            db.session.execute(text("ALTER TABLE event_response ADD COLUMN razorpay_payment_id VARCHAR(100)"))
            print("Added payment_status, order_id, and payment_id to EventResponse")
        except Exception as e:
            print(f"EventResponse update: {e}")

        # Add Razorpay Config Placeholders to SystemConfig
        configs = [
            ('razorpay_key_id', 'YOUR_KEY_ID'),
            ('razorpay_key_secret', 'YOUR_KEY_SECRET')
        ]
        for key, val in configs:
            if not SystemConfig.query.filter_by(key=key).first():
                config = SystemConfig(key=key, value=val)
                db.session.add(config)
                print(f"Added {key} to SystemConfig")
        
        db.session.commit()
        print("Database update complete.")

if __name__ == '__main__':
    update_db()
