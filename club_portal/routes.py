
from flask import render_template, redirect, url_for, flash, request, session, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from club_portal import club_portal as bp
from models import db, Club, ClubMember, Event, EventForm, EventResponse, Team, TeamMember, Attendance, FinanceTransaction, User, SystemConfig
from utils import allowed_file
import json
import qrcode
import razorpay
import io
import base64
from datetime import datetime, timedelta
import pandas as pd

# Helper function for Club Portal RBAC
def club_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'club_id' not in session and not current_user.is_authenticated:
            return redirect(url_for('club_portal.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.context_processor
def inject_club():
    if 'club_id' in session:
        club = Club.query.get(session['club_id'])
        return dict(club=club)
    return dict()

def filter_accepted_responses(event, responses, now):
    """
    Filters out participants who are 'Rejected' (Team-only event, past deadline, size < min).
    """
    if event.participation_type != 'team':
        return responses # Solo/Both allow fallback to individual
        
    deadline = event.registration_deadline or event.start_date or datetime.combine(event.date, datetime.min.time())
    if now <= deadline:
        return responses # Only filter AFTER the deadline
        
    # Get all teams for this event
    teams = {t.id: t for t in Team.query.filter_by(event_id=event.id).all()}
    
    accepted = []
    team_member_counts = {}
    
    # Pre-count members for efficiency
    for t_id in teams.keys():
        team_member_counts[t_id] = TeamMember.query.filter_by(team_id=t_id).count()
        
    for r in responses:
        if not r.team_id:
            # Should not happen in 'team-only' but if it does, it's rejected as solo
            continue
            
        count = team_member_counts.get(r.team_id, 0)
        if count >= event.team_size_min:
            accepted.append(r)
            
    return accepted

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form.get('login_id')
        password = request.form.get('password')
        
        club = Club.query.filter_by(club_login_id=login_id).first()
        if club and club.check_password(password):
            if not club.is_active:
                flash('This club portal has been deactivated by the admin.', 'danger')
                return redirect(url_for('club_portal.login'))
            
            # Correct: set session only when login is valid and club is active
            session['club_id'] = club.id
            session['club_name'] = club.name
            session['role'] = 'President'
            flash(f'Welcome to {club.name} Portal!', 'success')
            return redirect(url_for('club_portal.dashboard'))
        
        flash('Invalid Club ID or Password. Please try again.', 'danger')
    return render_template('club/login.html')

@bp.route('/dashboard')
def dashboard():
    club_id = session.get('club_id')
    if not club_id:
        return redirect(url_for('club_portal.login'))
    
    club = Club.query.get(club_id)
    events = Event.query.filter_by(club_id=club_id).order_by(Event.start_date.desc()).all()
    
    # Update event statuses automatically
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    for event in events:
        if event.end_date and now > event.end_date:
            event.status = 'expired'
        elif event.start_date and now >= event.start_date and (not event.end_date or now <= event.end_date):
            event.status = 'active'
        else:
            event.status = 'upcoming'
            
        # Filter accepted responses for counts
        event.accepted_responses = filter_accepted_responses(event, event.responses, now)
        
    db.session.commit()

    return render_template('club/dashboard.html', club=club, events=events, now=now)

@bp.route('/logout')
def logout():
    session.pop('club_id', None)
    session.pop('role', None)
    return redirect(url_for('club_portal.login'))

@bp.route('/events/create', methods=['GET', 'POST'])
def create_event():
    club_id = session.get('club_id')
    if not club_id: return redirect(url_for('club_portal.login'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%dT%H:%M')
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%dT%H:%M')
        venue = request.form.get('venue')
        participation_type = request.form.get('participation_type') # solo, team, both
        team_size_min = int(request.form.get('team_size_min', 1))
        team_size_max = int(request.form.get('team_size_max', 1))
        max_registrations = int(request.form.get('max_registrations', 0))
        allowed_depts = request.form.getlist('departments') # Multi-select
        registration_deadline_str = request.form.get('registration_deadline')
        registration_deadline = datetime.strptime(registration_deadline_str, '%Y-%m-%dT%H:%M') if registration_deadline_str else None
        
        # Validation: Deadline must be on or before start_date
        event_start_cmp = start_date or datetime.combine(start_date.date(), datetime.min.time())
        if registration_deadline and registration_deadline > event_start_cmp:
            flash('Registration deadline cannot be after the event start date.', 'danger')
            return redirect(url_for('club_portal.create_event'))

        is_paid = request.form.get('is_paid') == 'on'
        amount = float(request.form.get('amount', 0.0)) if is_paid else 0.0
        payment_model = request.form.get('payment_model', 'individual')

        event = Event(
            club_id=club_id,
            name=name,
            description=description,
            date=start_date.date(), # Keep legacy field sync
            start_date=start_date,
            end_date=end_date,
            registration_deadline=registration_deadline,
            venue=venue,
            participation_type=participation_type,
            team_size_min=team_size_min,
            team_size_max=team_size_max,
            max_registrations=max_registrations,
            allowed_departments=json.dumps(allowed_depts),
            is_paid=is_paid,
            amount=amount,
            payment_model=payment_model,
            status='upcoming'
        )
        db.session.add(event)
        db.session.commit()
        
        # Initialize empty form schema
        form = EventForm(event_id=event.id, schema_json=json.dumps([]))
        db.session.add(form)
        db.session.commit()
        
        flash('Event created successfully. Now build your application form.', 'success')
        return redirect(url_for('club_portal.build_form', event_id=event.id))

    from models import Department
    departments = Department.query.all()
    return render_template('club/create_event.html', departments=departments)

@bp.route('/events/<int:event_id>/build-form', methods=['GET', 'POST'])
def build_form(event_id):
    event = Event.query.get_or_404(event_id)
    form_obj = EventForm.query.filter_by(event_id=event_id).first()
    
    if request.method == 'POST':
        # Expecting JSON schema from frontend form builder
        schema = request.form.get('schema_json')
        form_obj.schema_json = schema
        db.session.commit()
        flash('Form structure saved!', 'success')
        return redirect(url_for('club_portal.dashboard'))
        
    return render_template('club/build_form.html', event=event, form_obj=form_obj)

@bp.route('/events/<int:event_id>/update-deadline', methods=['POST'])
def update_deadline(event_id):
    club_id = session.get('club_id')
    if not club_id:
        return redirect(url_for('club_portal.login'))

    event = Event.query.get_or_404(event_id)
    if event.club_id != club_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('club_portal.dashboard'))

    new_deadline_str = request.form.get('registration_deadline')
    if new_deadline_str:
        try:
            new_deadline = datetime.strptime(new_deadline_str, '%Y-%m-%dT%H:%M')
            
            # Validation: Deadline must be on or before start_date
            event_start_cmp = event.start_date or (datetime.combine(event.date, datetime.min.time()) if event.date else None)
            if event_start_cmp and new_deadline > event_start_cmp:
                msg = 'Registration deadline cannot be after the event start date.'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'danger')
                return redirect(url_for('club_portal.dashboard'))

            event.registration_deadline = new_deadline
            db.session.commit()
            # AJAX response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                formatted = new_deadline.strftime('%d %b, %H:%M')
                return jsonify({
                    'success': True,
                    'deadline': formatted,
                    'message': f'Registration deadline for "{event.name}" updated successfully!'
                })
            flash(f'Registration deadline for "{event.name}" updated successfully!', 'success')
        except ValueError:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid date format.'}), 400
            flash('Invalid date format.', 'danger')
    # Non-AJAX fallback
    return redirect(url_for('club_portal.dashboard'))

@bp.route('/events/<int:event_id>/delete')
def delete_event(event_id):
    club_id = session.get('club_id')
    if not club_id: return redirect(url_for('club_portal.login'))
    
    event = Event.query.get_or_404(event_id)
    
    # Security check
    if event.club_id != club_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('club_portal.dashboard'))
    
    # Check for linked permissions or responses
    if event.permissions or event.responses:
        flash('Cannot delete event that has registrations or permission requests.', 'danger')
        return redirect(url_for('club_portal.dashboard'))

    # Delete associated form if exists
    if event.form:
        db.session.delete(event.form)
    
    db.session.delete(event)
    db.session.commit()
    
    flash('Event deleted successfully.', 'success')
    return redirect(url_for('club_portal.dashboard'))

# --- Student Facing Routes ---

@bp.route('/available-events')
@login_required
def student_events():
    if not current_user.is_student():
        flash('Only students can access this page', 'danger')
        return redirect(url_for('index'))
    
    # Show ALL events (Active, Upcoming, and Past)
    all_events = Event.query.order_by(Event.start_date.desc()).all()
    
    available_events = []
    user_dept = current_user.department.strip().lower() if current_user.department else ""
    
    for event in all_events:
        allowed = json.loads(event.allowed_departments) if event.allowed_departments else []
        # Case-insensitive, stripped check
        if not allowed or any(d.strip().lower() == user_dept for d in allowed):
            available_events.append(event)
            
    # Check if student already registered
    registered_event_ids = [r.event_id for r in EventResponse.query.filter_by(student_id=current_user.id).all()]
            
    return render_template('club/student_events.html', events=available_events, registered_ids=registered_event_ids)

@bp.route('/events/<int:event_id>/apply', methods=['GET', 'POST'])
@login_required
def apply_event(event_id):
    def get_dept_code(dept_name):
        if not dept_name: return "GEN"
        d = str(dept_name).strip().upper()
        if 'AIML' in d: return 'CSM'
        if 'CSE-CS' in d or 'CS' in d: return 'CS'
        if 'CSE-DS' in d or 'DS' in d: return 'DS'
        if 'CSE' in d: return 'CSE'
        if 'CIVIL' in d: return 'CIV'
        return d[:3] # Fallback to first 3 chars

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

    # Initial check (handled inside POST for teams with extra members)
    if not request.method == 'POST' and event.max_registrations > 0:
        current_reg_count = EventResponse.query.filter_by(event_id=event_id).count()
        if current_reg_count >= event.max_registrations:
            flash(f'Registration limit of {event.max_registrations} has been reached for this event.', 'danger')
            return redirect(url_for('club_portal.student_events'))

    if request.method == 'POST':
        # Logging for debugging
        debug_info = f"{datetime.now()}: POST Submit. Event {event_id}, User {current_user.id}, Form: {dict(request.form)}\n"
        with open('instance/registration_debug.log', 'a') as f:
            import os
            if not os.path.exists('instance'): os.makedirs('instance')
            f.write(debug_info)

        team_id = None
        target_team = None
        extra_members_found = []
        # Get from form
        ptype = request.form.get('participation_choice', 'solo')
        
        # Calculate slots needed (Always 1 now as everyone registers individually)
        reg_slots_needed = 1
        if event.max_registrations > 0:
            current_reg_count = EventResponse.query.filter_by(event_id=event_id).count()
            if (current_reg_count + reg_slots_needed) > event.max_registrations:
                return jsonify({'status': 'error', 'message': 'Limit reached. No more slots left for this event.'})

        payment_mode_selected = request.form.get('payment_mode', 'pay') # pay or hold

        if event.participation_type in ['team', 'both'] and ptype == 'team':
            team_action = request.form.get('team_action') # create or join
            if team_action == 'create':
                t_name = request.form.get('team_name')
                declared_size_str = request.form.get('declared_size')
                if not t_name:
                    return jsonify({'status': 'error', 'message': 'Team name is required.'})
                
                existing_t = Team.query.filter(Team.event_id==event_id, Team.team_name.ilike(t_name)).first()
                if existing_t:
                    return jsonify({'status': 'error', 'message': 'This Team Name is already taken.'})
                    
                import random, string
                t_code = (t_name[:4].upper() + ''.join(random.choices(string.digits, k=4)))[:10]
                
                new_team = Team(event_id=event_id, leader_id=current_user.id, team_name=t_name, team_id_code=t_code, declared_size=int(declared_size_str or 1))
                db.session.add(new_team)
                db.session.flush()
                team_id = new_team.id
                db.session.add(TeamMember(team_id=team_id, user_id=current_user.id, role='leader'))
                target_team = new_team

            elif team_action == 'join':
                t_code_or_name = request.form.get('team_code', '').strip()
                from sqlalchemy import or_, func
                target_team = Team.query.filter(Team.event_id == event_id, or_(func.lower(Team.team_id_code) == t_code_or_name.lower(), func.lower(Team.team_name) == t_code_or_name.lower())).first()
                if not target_team:
                    return jsonify({'status': 'error', 'message': 'Team not found.'})
                
                if TeamMember.query.filter_by(team_id=target_team.id).count() >= target_team.declared_size:
                    return jsonify({'status': 'error', 'message': 'Team is full.'})
                
                team_id = target_team.id
                if not TeamMember.query.filter_by(team_id=team_id, user_id=current_user.id).first():
                    db.session.add(TeamMember(team_id=team_id, user_id=current_user.id, role='member'))
                db.session.flush()

        # Collect custom form data (Mandatory for all now)
        responses = {}
        schema = json.loads(form_obj.schema_json) if form_obj and form_obj.schema_json else []
        for field in schema:
            val = request.form.get(f"field_{field['label']}")
            if field.get('required') and not val:
                return jsonify({'status': 'error', 'message': f"{field['label']} is required"})
            responses[field['label']] = val

        # Calculate Payable Amount
        payable_amount = 0.0
        if event.is_paid:
            if event.payment_model == 'leader':
                if target_team and target_team.leader_id == current_user.id:
                    payable_amount = event.amount * target_team.declared_size
                else:
                    # If leader has already paid, member pays 0. Else member cannot pay share in 'leader pays' model.
                    payable_amount = 0.0 if (target_team and target_team.is_paid) else -1.0 
            else: # individual/split
                payable_amount = event.amount

        if payable_amount == -1.0:
            return jsonify({'status': 'error', 'message': 'This event requires the team leader to pay for the entire team. Please contact your team leader.'})

        # Helper to generate tickets
        def create_ticket_record():
            import qrcode, io, base64
            # Ticket ID generation
            prefix = current_user.roll_no[:2] if current_user.roll_no and len(current_user.roll_no) >= 2 else "00"
            dept_code = get_dept_code(current_user.department)
            serial = EventResponse.query.filter_by(event_id=event_id).count() + 1
            
            # Ensure global uniqueness by including event_id and adding a collision check loop
            while True:
                # Format: [Year][Dept][EventID][Serial]
                # Example: 24CS160001
                ticket_id = f"{prefix}{dept_code}{event_id:02d}{str(serial).zfill(4)}"
                if not EventResponse.query.filter_by(ticket_id=ticket_id).first():
                    break
                serial += 1
            
            qr_text = f"Ticket ID: {ticket_id}\nName: {current_user.get_full_name()}\nEvent: {event.name}"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_text); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = io.BytesIO(); img.save(buffered, format="PNG")
            
            # Status Logic
            final_status = 'pending'
            if not event.is_paid or payable_amount == 0: 
                final_status = 'completed'
            if payment_mode_selected == 'hold':
                final_status = 'on-hold'

            r = EventResponse(
                event_id=event_id, student_id=current_user.id, team_id=team_id,
                response_json=json.dumps(responses), ticket_id=ticket_id,
                qr_code_data=base64.b64encode(buffered.getvalue()).decode(),
                payment_status=final_status
            )
            db.session.add(r); db.session.flush()
            return r

        leader_response = create_ticket_record()
        db.session.commit()
        
        if event.is_paid and payment_mode_selected == 'pay' and payable_amount > 0:
            key_id = SystemConfig.query.filter_by(key='razorpay_key_id').first()
            key_secret = SystemConfig.query.filter_by(key='razorpay_key_secret').first()
            if not key_id or not key_secret:
                return jsonify({'status': 'error', 'message': 'Payment gateway error'})
                
            client = razorpay.Client(auth=(key_id.value, key_secret.value))
            order = client.order.create({
                'amount': int(payable_amount * 100), 'currency': 'INR',
                'receipt': f'reg_{leader_response.id}', 'payment_capture': 1
            })
            leader_response.razorpay_order_id = order['id']
            db.session.commit()
            
            return jsonify({
                'status': 'pay', 'order_id': order['id'], 'key': key_id.value,
                'amount': order['amount'], 'event_name': event.name,
                'user_name': current_user.get_full_name(), 'user_email': current_user.email,
                'response_id': leader_response.id
            })

        flash('Registration successful!', 'success')
        return jsonify({'status': 'success', 'redirect': url_for('club_portal.registration_ticket', response_id=leader_response.id)})

    schema = json.loads(form_obj.schema_json) if form_obj and form_obj.schema_json else []
    return render_template('club/apply_event.html', event=event, schema=schema, now=datetime.utcnow())


@bp.route('/my-registrations/<int:response_id>')
@login_required
def registration_ticket(response_id):
    response = EventResponse.query.get_or_404(response_id)
    if response.student_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    
    team = Team.query.get(response.team_id) if response.team_id else None
    
    # Ticket Status Logic
    ticket_status = 'VALID'
    status_msg = ''
    
    # NEW: Check Payment Status FIRST
    if response.event.is_paid and response.payment_status != 'completed':
        ticket_status = 'UNPAID'
        if response.payment_status == 'on-hold':
            status_msg = 'Payment On Hold: Please settle the amount at the event desk to unlock your ticket.'
        else:
            status_msg = 'Payment Pending: Your ticket will be active once payment is verified.'
    
    elif team:
        from models import TeamMember
        members_count = TeamMember.query.filter_by(team_id=team.id).count()
        event = response.event
        
        if members_count < event.team_size_min:
            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            deadline = event.registration_deadline or event.start_date or datetime.combine(event.date, datetime.min.time())
            
            if now > deadline:
                if event.participation_type in ['solo', 'both'] and members_count == 1:
                    ticket_status = 'ACCEPTED_SOLO'
                    status_msg = 'Deadline passed: Automatically accepted as Solo participant.'
                else:
                    ticket_status = 'REJECTED'
                    status_msg = f'Registration Rejected: Minimum team size of {event.team_size_min} was not met by the deadline.'
            else:
                ticket_status = 'PENDING'
                status_msg = f'Pending Members: Your team needs {event.team_size_min - members_count} more member(s) to validate this ticket.'

    return render_template('club/ticket.html', response=response, team=team, ticket_status=ticket_status, status_msg=status_msg)

@bp.route('/pay-existing/<int:response_id>', methods=['POST'])
@login_required
def initiate_payment(response_id):
    response = EventResponse.query.get_or_404(response_id)
    if response.student_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    if response.payment_status == 'completed':
        return jsonify({'status': 'error', 'message': 'Payment already completed'})
    
    event = response.event
    if not event.is_paid:
        return jsonify({'status': 'error', 'message': 'This is a free event'})

    # Calculate Payable Amount (Similar to apply_event logic)
    payable_amount = 0.0
    if event.payment_model == 'leader':
        team = Team.query.get(response.team_id) if response.team_id else None
        if team and team.leader_id == current_user.id:
            payable_amount = event.amount * team.declared_size
        else:
            if team and team.is_paid:
                return jsonify({'status': 'error', 'message': 'Team already paid by leader'})
            return jsonify({'status': 'error', 'message': 'This event requires the team leader to pay.'})
    else:
        payable_amount = event.amount

    if payable_amount <= 0:
         return jsonify({'status': 'error', 'message': 'Invalid payment amount'})

    # Razorpay Logic
    key_id = SystemConfig.query.filter_by(key='razorpay_key_id').first()
    key_secret = SystemConfig.query.filter_by(key='razorpay_key_secret').first()
    if not key_id or not key_secret:
        return jsonify({'status': 'error', 'message': 'Payment gateway error'})
        
    client = razorpay.Client(auth=(key_id.value, key_secret.value))
    try:
        order = client.order.create({
            'amount': int(payable_amount * 100), 'currency': 'INR',
            'receipt': f'reg_{response.id}', 'payment_capture': 1
        })
        response.razorpay_order_id = order['id']
        db.session.commit()
        
        return jsonify({
            'status': 'pay', 'order_id': order['id'], 'key': key_id.value,
            'amount': order['amount'], 'event_name': event.name,
            'user_name': current_user.get_full_name(), 'user_email': current_user.email,
            'response_id': response.id
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@bp.route('/verify-payment', methods=['POST'])
def verify_payment():
    import razorpay
    data = request.get_json()
    resp_id = data.get('response_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    key_id = SystemConfig.query.filter_by(key='razorpay_key_id').first()
    key_secret = SystemConfig.query.filter_by(key='razorpay_key_secret').first()
    
    client = razorpay.Client(auth=(key_id.value, key_secret.value))
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        client.utility.verify_payment_signature(params_dict)
        response = EventResponse.query.get(resp_id)
        if response:
            response.payment_status = 'completed'
            response.razorpay_payment_id = razorpay_payment_id
            
            # Financial Tracking
            event = response.event
            payment_info = client.payment.fetch(razorpay_payment_id)
            amount_paid = float(payment_info['amount']) / 100.0
            
            event.total_collected += amount_paid
            
            # If leader paid in 'leader' model, mark team as paid
            if response.team_id and event.payment_model == 'leader':
                team = Team.query.get(response.team_id)
                if team and team.leader_id == response.student_id:
                    team.is_paid = True
            
            # Log Transaction (Category: registration_fee)
            new_tx = FinanceTransaction(
                club_id=event.club_id,
                event_id=event.id,
                amount=amount_paid,
                type='credit',
                category='registration_fee',
                description=f"Registration Fee: {response.student.get_full_name()} ({response.ticket_id})"
            )
            db.session.add(new_tx)
            db.session.commit()
            return jsonify({'success': True, 'redirect': url_for('club_portal.registration_ticket', response_id=response.id)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@bp.route('/events/<int:event_id>/scanner')
def scanner(event_id):
    club_id = session.get('club_id')
    if not club_id: return redirect(url_for('club_portal.login'))
    
    event = Event.query.get_or_404(event_id)
    if event.club_id != club_id: return "Unauthorized", 403
    
    return render_template('club/scanner.html', event=event)

@bp.route('/mark-attendance', methods=['POST'])
def mark_attendance():
    club_id = session.get('club_id')
    if not club_id: return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    raw_scan = data.get('ticket_id', '')
    event_id = data.get('event_id')
    session_type = data.get('session_type', 'Default')
    
    if not event_id:
        return jsonify({'success': False, 'message': 'Event ID missing'}), 400

    event = Event.query.get(event_id)
    if not event or event.club_id != club_id:
        return jsonify({'success': False, 'message': 'Invalid Event'}), 404

    # Date check: Only allow scanning on the day of the event
    today = datetime.now().date()
    event_start = event.start_date.date() if event.start_date else event.date
    event_end = event.end_date.date() if event.end_date else event_start
    
    if today < event_start or today > event_end:
        return jsonify({
            'success': False, 
            'message': f'Attendance scanning is only allowed on the day of the event ({event_start.strftime("%d %b %Y")})'
        }), 403

    # Extract Ticket ID if it's the full multi-line QR text
    ticket_id = raw_scan
    if "Ticket ID:" in raw_scan:
        try:
            # Format is "Ticket ID: ABCD0001\n..."
            ticket_id = raw_scan.split('\n')[0].replace('Ticket ID:', '').strip()
        except:
            ticket_id = raw_scan.strip()
    else:
        ticket_id = raw_scan.strip()
    
    response = EventResponse.query.filter_by(ticket_id=ticket_id, event_id=event_id).first()
    if not response:
        # Check if they exist for a DIFFERENT event of this club
        any_response = EventResponse.query.filter_by(ticket_id=ticket_id).first()
        if any_response:
             return jsonify({'success': False, 'message': f'Student is registered for "{any_response.event.name}", not this event.'}), 400
        return jsonify({'success': False, 'message': 'Invalid Ticket or Student not registered for this event.'}), 404
        
    # Check if this student belongs to an event of this club
    if response.event.club_id != club_id:
        return jsonify({'success': False, 'message': 'Ticket does not belong to this club'}), 403
        
    # Validate Team Completeness
    if response.team_id:
        from models import TeamMember
        members_count = TeamMember.query.filter_by(team_id=response.team_id).count()
        if members_count < event.team_size_min:
            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            deadline = event.registration_deadline or event.start_date or datetime.combine(event.date, datetime.min.time())
            
            if now > deadline:
                if event.participation_type in ['solo', 'both'] and members_count == 1:
                    # Validated as fallback solo
                    pass
                else:
                    return jsonify({'success': False, 'message': f'Registration Rejected: Minimum team size of {event.team_size_min} was not met by the deadline.'}), 400
            else:
                return jsonify({'success': False, 'message': f'Team is incomplete. Requires {event.team_size_min - members_count} more member(s).'}), 400
        
    # Check if already marked for this session
    existing = Attendance.query.filter_by(response_id=response.id, session_type=session_type).first()
    if existing:
        return jsonify({'success': False, 'message': f'Attendance already marked for {session_type}'}), 400
        
    # Mark attendance
    attendance = Attendance(
        response_id=response.id,
        session_type=session_type,
        scanned_by=session.get('user_id') # If individual login is used
    )
    db.session.add(attendance)
    db.session.commit()
    
    student = response.student
    return jsonify({
        'success': True, 
        'message': f'Attendance marked for {student.first_name} {student.last_name}',
        'student_info': {
            'name': student.get_full_name(),
            'roll_no': student.roll_no,
            'dept': student.department
        }
    })

@bp.route('/finances', methods=['GET', 'POST'])
def finances():
    club_id = session.get('club_id')
    if not club_id: return redirect(url_for('club_portal.login'))
    
    club = Club.query.get(club_id)
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        trans_type = request.form.get('type') # credit, debit
        category = request.form.get('category')
        description = request.form.get('description')
        
        # Update club balance
        if trans_type == 'credit':
            club.balance += amount
        else:
            club.balance -= amount
            
        transaction = FinanceTransaction(
            club_id=club_id,
            amount=amount,
            type=trans_type,
            category=category,
            description=description
        )
        db.session.add(transaction)
        db.session.commit()
        flash('Transaction recorded successfully', 'success')
        return redirect(url_for('club_portal.finances'))
        
    transactions = FinanceTransaction.query.filter_by(club_id=club_id).order_by(FinanceTransaction.created_at.desc()).all()
    return render_template('club/finances.html', club=club, transactions=transactions)

@bp.route('/events/<int:event_id>/export')
def export_participants(event_id):
    club_id = session.get('club_id')
    if not club_id: return redirect(url_for('club_portal.login'))
    
    event = Event.query.get_or_404(event_id)
    if event.club_id != club_id: return "Unauthorized", 403
    
    raw_responses = EventResponse.query.filter_by(event_id=event_id).all()
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    responses = filter_accepted_responses(event, raw_responses, now)
    
    data = []
    for r in responses:
        row = {
            'Ticket ID': r.ticket_id,
            'Roll No': r.student.roll_no,
            'Name': r.student.get_full_name(),
            'Department': r.student.department,
            'Section': r.student.section,
            'Registration Date': r.submitted_at.strftime('%Y-%m-%d %H:%M') if r.submitted_at else 'N/A'
        }
        # Add custom form fields
        if r.response_json:
            custom_data = json.loads(r.response_json)
            row.update(custom_data)
        data.append(row)
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Participants')
    output.seek(0)
    
    return send_file(output, download_name=f"{event.name}_participants.xlsx", as_attachment=True)

@bp.route('/events/<int:event_id>/participants')
def view_participants(event_id):
    club_id = session.get('club_id')
    if not club_id: return redirect(url_for('club_portal.login'))
    
    event = Event.query.get_or_404(event_id)
    if event.club_id != club_id: return "Unauthorized", 403
    
    raw_responses = EventResponse.query.filter_by(event_id=event_id).all()
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    responses = filter_accepted_responses(event, raw_responses, now)
    
    teams = {t.id: t for t in Team.query.filter_by(event_id=event_id).all()}
    
    grouped_teams = {}
    solo_responses = []
    
    # Pre-parse JSON for template and group
    for r in responses:
        r.custom_data = json.loads(r.response_json) if r.response_json else {}
        
        team_name = None
        is_lead = False
        if r.team_id and r.team_id in teams:
            t_obj = teams[r.team_id]
            team_name = t_obj.team_name
            if t_obj.leader_id == r.student_id:
                is_lead = True
        else:
            for k, v in r.custom_data.items():
                if k.lower() in ['team name', 'teamname', 'name of team', 'name of the team']:
                    team_name = v
                    break
        
        r.is_leader = is_lead
                    
        if team_name:
            if team_name not in grouped_teams:
                grouped_teams[team_name] = []
            grouped_teams[team_name].append(r)
        else:
            solo_responses.append(r)
        
    return render_template('club/participants.html', event=event, responses=responses, grouped_teams=grouped_teams, solo_responses=solo_responses)
