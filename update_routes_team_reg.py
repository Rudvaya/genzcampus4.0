import os

target = r'd:\Sai Kiran\projects\genzcampus\pms\club_portal\routes.py'
with open(target, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if line.startswith("@bp.route('/events/<int:event_id>/apply'"):
        start_idx = i
        
    if start_idx != -1 and line.strip() == "return render_template('club/apply_event.html', event=event, schema=schema, now=datetime.utcnow())":
        end_idx = i + 1
        break

if start_idx != -1 and end_idx != -1:
    new_func = """@bp.route('/events/<int:event_id>/apply', methods=['GET', 'POST'])
@login_required
def apply_event(event_id):
    event = Event.query.get_or_404(event_id)
    form_obj = EventForm.query.filter_by(event_id=event_id).first()
    
    if not event.is_registration_open:
        flash('Registrations for this event are closed.', 'danger')
        return redirect(url_for('club_portal.student_events'))

    # Check department visibility
    allowed = json.loads(event.allowed_departments) if event.allowed_departments else []
    if allowed and current_user.department not in allowed:
        flash('Your department is not eligible for this event.', 'danger')
        return redirect(url_for('club_portal.student_events'))

    # Check if already registered
    existing = EventResponse.query.filter_by(event_id=event_id, student_id=current_user.id).first()
    if existing:
        flash('You have already registered for this event.', 'warning')
        return redirect(url_for('club_portal.registration_ticket', response_id=existing.id))

    if request.method == 'POST':
        team_id = None
        extra_members_found = []
        ptype = request.form.get('participation_choice') if event.participation_type in ['team', 'both'] else 'solo'
        
        if event.participation_type in ['team', 'both'] and ptype == 'team':
            team_action = request.form.get('team_action') # create or join
            if team_action == 'create':
                t_name = request.form.get('team_name')
                declared_size_str = request.form.get('declared_size')
                
                if not t_name:
                    flash('Team name is required to create a team.', 'danger')
                    return redirect(request.url)
                
                existing_t = Team.query.filter_by(event_id=event_id, team_name=t_name).first()
                if existing_t:
                    flash('This Team Name is already taken for this event.', 'danger')
                    return redirect(request.url)
                    
                try:
                    declared_size = int(declared_size_str)
                except (ValueError, TypeError):
                    declared_size = event.team_size_min
                
                if declared_size < event.team_size_min or declared_size > event.team_size_max:
                    flash(f'Team size must be between {event.team_size_min} and {event.team_size_max}', 'danger')
                    return redirect(request.url)
                
                import random, string
                t_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                new_team = Team(event_id=event_id, leader_id=current_user.id, team_name=t_name, team_id_code=t_code, declared_size=declared_size)
                db.session.add(new_team)
                db.session.flush()
                team_id = new_team.id
                
                leader_mem = TeamMember(team_id=team_id, user_id=current_user.id, role='leader')
                db.session.add(leader_mem)
                
                for i in range(1, declared_size):
                    roll_no = request.form.get(f'member_roll_no_{i}')
                    if roll_no:
                        roll_no = roll_no.strip().upper()
                        user_mem = User.query.filter_by(roll_no=roll_no).first()
                        if not user_mem:
                            flash(f'Student with Roll Number {roll_no} not found. They must sign up first.', 'danger')
                            db.session.rollback()
                            return redirect(request.url)
                        
                        existing_mem = EventResponse.query.filter_by(event_id=event_id, student_id=user_mem.id).first()
                        if existing_mem:
                            flash(f'Student {roll_no} is already registered for this event.', 'danger')
                            db.session.rollback()
                            return redirect(request.url)
                            
                        new_mem = TeamMember(team_id=team_id, user_id=user_mem.id, role='member')
                        db.session.add(new_mem)
                        extra_members_found.append(user_mem)

            elif team_action == 'join':
                t_code_or_name = request.form.get('team_code')
                if not t_code_or_name:
                    flash('Team Code or Name is required.', 'danger')
                    return redirect(request.url)
                    
                t_code_or_name = t_code_or_name.strip()
                target_team = Team.query.filter_by(event_id=event_id, team_id_code=t_code_or_name).first()
                if not target_team:
                    target_team = Team.query.filter_by(event_id=event_id, team_name=t_code_or_name).first()
                    
                if not target_team:
                    flash('Invalid Team Code or Exact Name for this event.', 'danger')
                    return redirect(request.url)
                
                if len(target_team.members) >= target_team.declared_size:
                    flash('This team is already full based on the size set by the leader.', 'danger')
                    return redirect(request.url)
                
                team_id = target_team.id
                new_mem = TeamMember(team_id=team_id, user_id=current_user.id, role='member')
                db.session.add(new_mem)

        # Collect custom form data
        schema = json.loads(form_obj.schema_json) if form_obj and form_obj.schema_json else []
        responses = {}
        for field in schema:
            val = request.form.get(f"field_{field['label']}")
            if field.get('required') and not val:
                flash(f"{field['label']} is required", 'danger')
                return redirect(request.url)
            responses[field['label']] = val

        # Helper to generate tickets
        def create_ticket_record(stu_id):
            import uuid, qrcode, io, base64
            ticket_id = f"GRD-TKT-{uuid.uuid4().hex[:8].upper()}"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(ticket_id)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode()

            r = EventResponse(
                event_id=event_id,
                student_id=stu_id,
                team_id=team_id,
                response_json=json.dumps(responses),
                ticket_id=ticket_id,
                qr_code_data=qr_base64
            )
            db.session.add(r)
            return r

        leader_response = create_ticket_record(current_user.id)
        
        for ex_mem in extra_members_found:
            create_ticket_record(ex_mem.id)

        db.session.commit()
        
        flash('Registration successful!', 'success')
        return redirect(url_for('club_portal.registration_ticket', response_id=leader_response.id))

    schema = json.loads(form_obj.schema_json) if form_obj and form_obj.schema_json else []
    return render_template('club/apply_event.html', event=event, schema=schema, now=datetime.utcnow())
"""
    new_lines = lines[:start_idx] + [new_func + "\n"] + lines[end_idx:]
    with open(target, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Replaced route successfully.")
else:
    print(f"Could not find valid indices: start={start_idx}, end={end_idx}")
