from app import app, db
from models import College
c = College.query.get(1)
print(c.features)
