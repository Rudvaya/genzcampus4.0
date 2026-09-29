from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE "user" DROP CONSTRAINT IF EXISTS user_roll_no_key'))
        db.session.execute(text('ALTER TABLE "user" ADD CONSTRAINT uq_roll_no_college_id UNIQUE (roll_no, college_id)'))
        db.session.commit()
        print("Constraint updated successfully")
    except Exception as e:
        print("Error:", e)
        db.session.rollback()
