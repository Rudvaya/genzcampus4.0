import os
import re

target = r'd:\Sai Kiran\projects\genzcampus\pms\club_portal\routes.py'
with open(target, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace validation block in create
old_create = "existing_t = Team.query.filter_by(event_id=event_id, team_name=t_name).first()"
new_create = "existing_t = Team.query.filter(Team.event_id==event_id, db.func.lower(Team.team_name)==t_name.lower()).first()"
content = content.replace(old_create, new_create)

# Replace validation block in join
old_join = """                target_team = Team.query.filter_by(event_id=event_id, team_id_code=t_code_or_name).first()
                if not target_team:
                    target_team = Team.query.filter_by(event_id=event_id, team_name=t_code_or_name).first()"""
                    
new_join = """                # Check code or team name case-insensitive
                target_team = Team.query.filter(Team.event_id==event_id, db.func.lower(Team.team_id_code)==t_code_or_name.lower()).first()
                if not target_team:
                    target_team = Team.query.filter(Team.event_id==event_id, db.func.lower(Team.team_name)==t_code_or_name.lower()).first()"""

content = content.replace(old_join, new_join)

with open(target, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated successfully")
