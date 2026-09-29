from app import app, db
from models import College
c = College()
c.features = '{"attendance": true}'
print(c.get_features)
