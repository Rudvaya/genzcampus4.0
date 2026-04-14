from app import app, db
from models import Club

with app.app_context():
    c = Club.query.filter_by(club_login_id='aifusion@gmail.com').first()
    if c:
        c.set_password('club@123')
        db.session.commit()
        print('Password for AI Fusion Club reset to: club@123')
    else:
        print('AI Fusion Club not found')
