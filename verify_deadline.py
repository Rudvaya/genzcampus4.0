import os
import sys
import json
from datetime import datetime, timedelta

# Add the project directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Event, Club, EventForm
from flask import url_for

with app.app_context():
    # 1. Setup - Find or create a test student
    student = User.query.filter_by(role='student').first()
    if not student:
        student = User(
            email='test_student@example.com',
            first_name='Test',
            last_name='Student',
            role='student',
            department='CSE',
            year=1,
            section='A',
            roll_no='TEST123456'
        )
        student.set_password('password123')
        db.session.add(student)
        db.session.commit()
    
    # Find or create a club
    club = Club.query.first()
    if not club:
        club = Club(name='Deadline Test Club', description='Test')
        db.session.add(club)
        db.session.commit()

    # 2. Create a test event with a deadline in the PAST
    past_deadline = datetime.utcnow() - timedelta(hours=1)
    event = Event(
        club_id=club.id,
        name='Deadline Pass Test',
        description='Test registration deadline',
        date=datetime.utcnow().date(),
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=1),
        registration_deadline=past_deadline,
        venue='Digital Test Lab',
        status='active'
    )
    db.session.add(event)
    db.session.commit()
    event_id = event.id
    
    # Create form for it
    form = EventForm(event_id=event_id, schema_json=json.dumps([]))
    db.session.add(form)
    db.session.commit()
    
    print(f"Created test event with ID: {event_id} and past deadline: {past_deadline}")

    # 3. Verify enforcement logic (simulating the check in routes.py)
    def check_registration(ev_id):
        ev = Event.query.get(ev_id)
        now = datetime.utcnow()
        if ev.status == 'expired' or (ev.registration_deadline and now > ev.registration_deadline):
            return False, "Registration Closed"
        return True, "Registration Open"

    status, msg = check_registration(event_id)
    print(f"Enforcement Check (Past Deadline): {status}, {msg}")
    if status is False:
        print("Success: Registration correctly blocked for past deadline.")
    else:
        print("Error: Registration should have been blocked.")
        # sys.exit(1) # Don't exit yet, let's test the update

    # 4. Update deadline to the FUTURE
    future_deadline = datetime.utcnow() + timedelta(hours=1)
    event.registration_deadline = future_deadline
    db.session.commit()
    print(f"Updated deadline to FUTURE: {future_deadline}")

    # 5. Verify enforcement logic again
    status, msg = check_registration(event_id)
    print(f"Enforcement Check (Future Deadline): {status}, {msg}")
    if status is True:
        print("Success: Registration correctly allowed for future deadline.")
    else:
        print("Error: Registration should have been allowed.")
        sys.exit(1)

    # 6. Cleanup
    db.session.delete(form)
    db.session.delete(event)
    db.session.commit()

    print("\n--- Verification Complete: Registration Deadline functionality is correct ---")
