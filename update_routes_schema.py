import os

target = r'd:\Sai Kiran\projects\genzcampus\pms\club_portal\routes.py'
with open(target, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.strip() == "for field in schema:":
        # We replace the for loop body
        end_idx = i + 1
        for j in range(i+1, len(lines)):
            if lines[j].strip().startswith("# Helper to generate tickets"):
                end_idx = j
                break
                
        new_logic = """        for field in schema:
            f_lower = field['label'].lower()
            if f_lower in ['team name', 'teamname', 'name of team', 'name of the team'] and event.participation_type in ['team', 'both'] and ptype == 'team':
                responses[field['label']] = target_team.team_name if team_action == 'join' else t_name
            else:
                val = request.form.get(f"field_{field['label']}")
                if field.get('required') and not val:
                    flash(f"{field['label']} is required", 'danger')
                    return redirect(request.url)
                responses[field['label']] = val

"""
        new_lines = lines[:i] + [new_logic] + lines[end_idx:]
        with open(target, 'w', encoding='utf-8') as out:
            out.writelines(new_lines)
        print("Updated backend schema logic")
        break
