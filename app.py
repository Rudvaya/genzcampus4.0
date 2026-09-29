import os
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory, session, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from models import db, User, Club, Event, Permission, Department, SystemConfig, EventResponse, ClassAttendance, TimeTable, ClassHoliday, FinanceTransaction, StudentPerformance
from config import Config
from utils import allowed_file, validate_roll_no
from supabase import create_client, Client

# Blueprint registration moved down
import random
import string
import razorpay

app = Flask(__name__)
app.config.from_object(Config)

# Razorpay Client Initialization
def get_razorpay_client():
    key_id = SystemConfig.query.filter_by(key='razorpay_key_id').first()
    key_secret = SystemConfig.query.filter_by(key='razorpay_key_secret').first()
    if key_id and key_secret:
        return razorpay.Client(auth=(key_id.value, key_secret.value))
    return None

app.jinja_env.globals.update(get_razorpay_client=get_razorpay_client)

# Supabase Client Initialization
supabase: Client = None
if app.config.get('SUPABASE_URL') and app.config.get('SUPABASE_KEY'):
    try:
        supabase = create_client(app.config['SUPABASE_URL'], app.config['SUPABASE_KEY'])
    except Exception as e:
        print(f"Supabase init error: {e}")

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_message_category = 'info'

@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/cc/') or request.path.startswith('/super-admin'):
        return redirect(url_for('super_admin_login'))
    if getattr(g, 'college_slug', None):
        return redirect(url_for('login', college_slug=g.college_slug))
    return redirect(url_for('login_global'))

mail = Mail(app)
migrate = Migrate(app, db)

from club_portal import club_portal
app.register_blueprint(club_portal, url_prefix='/<college_slug>/club')

# Add global functions to Jinja
app.jinja_env.globals.update(getattr=getattr, str=str, int=int)

def get_logo_url(logo):
    if not logo:
        return url_for('static', filename='img/college_placeholder.png')
    if logo.startswith('http'):
        return logo
    return url_for('static', filename=logo)

app.jinja_env.globals.update(get_logo_url=get_logo_url)

@app.context_processor
def inject_branding():
    try:
        # If we have a current college, use its settings
        college = getattr(g, 'current_college', None)
        features = {}
        if college and college.features:
            try:
                features = json.loads(college.features)
            except:
                features = {}
        
        if college:
            # Look for college-specific logo in SystemConfig
            logo_config = SystemConfig.query.filter_by(key='college_logo', college_id=college.id).first()
            logo = logo_config.value if logo_config else college.branding_logo
            
            # Process logo URL/path
            if logo and not logo.startswith('http'):
                logo = url_for('static', filename=logo)
                
            return {
                'college_logo': logo,
                'current_college': college,
                'features': features
            }
        return {'college_logo': None, 'current_college': None, 'features': {}}
    except Exception as e:
        print(f"Context processor error: {e}")
        return {'college_logo': None, 'current_college': None, 'features': {}}

from models import College

@app.url_value_preprocessor
def pull_college_slug(endpoint, values):
    if values and 'college_slug' in values:
        g.college_slug = values.pop('college_slug')
        g.current_college = College.query.filter_by(slug=g.college_slug, is_active=True).first()
        if not g.current_college and g.college_slug != 'super-admin':
            # Handle invalid college slug
            pass

@app.url_defaults
def add_college_slug(endpoint, values):
    if 'college_slug' in values or not hasattr(g, 'college_slug'):
        return
    if app.url_map.is_endpoint_expecting(endpoint, 'college_slug'):
        values.setdefault('college_slug', g.college_slug)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def format_time_range(time_range_str):
    if not time_range_str:
        return ""
    try:
        start_str, end_str = time_range_str.split(' - ')
        start_obj = datetime.strptime(start_str.strip(), '%H:%M')
        end_obj = datetime.strptime(end_str.strip(), '%H:%M')
        return f"{start_obj.strftime('%I:%M %p')} - {end_obj.strftime('%I:%M %p')}"
    except Exception:
        return time_range_str

app.jinja_env.filters['format_time_range'] = format_time_range

# Create uploads directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('instance', exist_ok=True)

# Create tables and admin user
with app.app_context():
    db.create_all()
    # Only create if at least one college exists (to avoid overhead)
    if College.query.with_entities(College.id).first():
         # Logic for sample data if needed, but usually we don't want to auto-create 
         # global data without college_id anymore.
         pass

@app.before_request
def resolve_tenant_isolation():
    # Public routes that don't need tenant context
    if request.endpoint in ['static', 'super_admin_dashboard', 'login_global', 'super_admin_login']:
        return

    college = getattr(g, 'current_college', None)
    if college:
        # Enforce college_id in Postgres session for RLS
        db.session.execute(db.text("SET app.current_college_id = :cid"), {'cid': college.id})
    elif request.endpoint and not request.endpoint.startswith('static'):
        # If no college resolved but route expected one, we might want to redirect
        pass

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Global Entry Point
@app.route('/')
def login_global():
    colleges = College.query.filter_by(is_active=True).all()
    return render_template('tenant_selector.html', colleges=colleges)

@app.route('/cc/dashboard')
@login_required
def super_admin_dashboard():
    if not current_user.is_superadmin:
        flash('Access denied.', 'danger')
        return redirect(url_for('login_global'))
    colleges = College.query.all()
    stats = {
        'total_colleges': len(colleges),
        'total_users': User.query.count(),
        'active_colleges': College.query.filter_by(is_active=True).count()
    }
    return render_template('super_admin/dashboard.html', colleges=colleges, stats=stats)

@app.route('/cc/college/create', methods=['GET', 'POST'])
@login_required
def create_college():
    if not current_user.is_superadmin:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug').lower()
        
        admin_email = request.form.get('admin_email')
        admin_password = request.form.get('admin_password')

        if User.query.filter_by(email=admin_email).first():
            flash('Admin email already exists.', 'danger')
            return redirect(url_for('super_admin_dashboard'))
            
        # Handle Logo Upload
        branding_logo = None
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename != '' and allowed_file(logo_file.filename):
            ext = logo_file.filename.rsplit('.', 1)[1].lower()
            logo_filename = secure_filename(f"{slug}_logo.{ext}")
            upload_path = os.path.join(app.static_folder, 'uploads', 'logos')
            
            # Ensure directory exists
            os.makedirs(upload_path, exist_ok=True)
            
            logo_file.save(os.path.join(upload_path, logo_filename))
            branding_logo = f"uploads/logos/{logo_filename}"
            
        college = College(
            name=name,
            slug=slug,
            branding_logo=branding_logo,
            features=json.dumps({
                'attendance': 'attendance' in request.form,
                'timetable': 'timetable' in request.form,
                'clubs': 'clubs' in request.form,
                'permissions': 'permissions' in request.form,
                'exams': 'exams' in request.form
            })
        )
        db.session.add(college)
        db.session.flush() # Get ID before commit

        # Create the college admin
        admin_user = User(
            email=admin_email,
            role='admin',
            college_id=college.id,
            is_verified=True
        )
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
        
        db.session.commit()
        flash(f'College {name} and admin account created successfully!', 'success')
        return redirect(url_for('super_admin_dashboard'))
    
    return render_template('super_admin/create_college.html')

@app.route('/cc/college/<int:college_id>/toggle-status')
@login_required
def toggle_college_status(college_id):
    if not current_user.is_superadmin:
        return jsonify({'success': False}), 403
    college = College.query.get_or_404(college_id)
    college.is_active = not college.is_active
    db.session.commit()
    return redirect(url_for('super_admin_dashboard'))

@app.route('/cc/college/<int:college_id>/toggle-feature/<feature>')
@login_required
def toggle_college_feature(college_id, feature):
    if not current_user.is_superadmin:
        return jsonify({'success': False}), 403
    college = College.query.get_or_404(college_id)
    features = college.get_features
    features[feature] = not features.get(feature, False)
    college.features = json.dumps(features)
    db.session.commit()
    return redirect(url_for('super_admin_dashboard'))

@app.route('/cc/college/<int:college_id>/update-admin', methods=['POST'])
@login_required
def update_college_admin(college_id):
    if not current_user.is_superadmin:
        return jsonify({'success': False}), 403
    
    college = College.query.get_or_404(college_id)
    new_email = request.form.get('admin_email')
    new_password = request.form.get('admin_password')
    
    # Handle Logo Update
    logo_file = request.files.get('logo')
    if logo_file and logo_file.filename != '' and allowed_file(logo_file.filename):
        ext = logo_file.filename.rsplit('.', 1)[1].lower()
        # Use a timestamp or unique hash to avoid browser caching issues on update
        from time import time
        logo_filename = secure_filename(f"{college.slug}_logo_{int(time())}.{ext}")
        upload_path = os.path.join(app.static_folder, 'uploads', 'logos')
        
        # Ensure directory exists
        os.makedirs(upload_path, exist_ok=True)
        
        # Save new logo
        logo_file.save(os.path.join(upload_path, logo_filename))
        college.branding_logo = f"uploads/logos/{logo_filename}"
        db.session.commit()

    admin = college.admin
    
    # 1. Validate email uniqueness if changing email
    if new_email:
        existing = User.query.filter_by(email=new_email).first()
        # If email exists and either we have no admin yet OR it belongs to a different user
        if existing and (not admin or existing.id != admin.id):
            flash('Email already taken by another user.', 'danger')
            return redirect(url_for('super_admin_dashboard'))

    # 2. Update or Create Admin
    if not admin:
        if not new_email:
            flash('Admin email is required.', 'danger')
            return redirect(url_for('super_admin_dashboard'))
        # Create with the required email
        admin = User(
            email=new_email,
            role='admin',
            college_id=college.id,
            is_verified=True
        )
        db.session.add(admin)
    else:
        if new_email:
            admin.email = new_email
        
    if new_password:
        admin.set_password(new_password)
        
    db.session.commit()
    flash(f'Admin credentials for {college.name} updated successfully.', 'success')
    return redirect(url_for('super_admin_dashboard'))

# Tenant Specific Routes
@app.route('/<college_slug>/')
def index():
    if current_user.is_authenticated:
        if current_user.is_superadmin:
            if getattr(g, 'current_college', None):
                return redirect(url_for('admin_dashboard', college_slug=g.current_college.slug))
            return redirect(url_for('super_admin_dashboard'))
        if current_user.is_admin():
            return redirect(url_for('admin_dashboard'))
        elif current_user.is_student():
            return redirect(url_for('student_dashboard'))
        else:
            return redirect(url_for('faculty_dashboard'))
    return redirect(url_for('login'))

@app.route('/cc/login', methods=['GET', 'POST'])
def super_admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(email=email, is_superadmin=True).first()
        if user and user.check_password(password):
            if user.is_blocked:
                flash('Your account has been blocked.', 'danger')
                return redirect(url_for('login_global'))
            login_user(user)
            return redirect(url_for('super_admin_dashboard'))
        
        flash('Invalid super-admin credentials', 'danger')
    
    return render_template('super_admin/login.html')

@app.route('/<college_slug>/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # Logging to file for diagnostics
        with open('instance/login_debug.log', 'a') as f:
            f.write(f"\n--- {datetime.now()} ---\n")
            f.write(f"Attempt: [{email}]\n")
            
            # 1. Check if this is a superadmin attempting to log in here
            user = User.query.filter_by(email=email, is_superadmin=True).first()
            if user:
                flash('Super-admins must log in through the Command Center.', 'warning')
                return redirect(url_for('super_admin_login'))
            
            if g.current_college:
                # 2. Check User Table for college users
                user = User.query.filter_by(email=email, college_id=g.current_college.id).first()
            
            if user:
                p_check = user.check_password(password)
                f.write(f"Found User. Role: {user.role}. Password Match: {p_check}\n")
                if p_check:
                    if user.is_blocked:
                        flash('Your account has been blocked. Please contact admin.', 'danger')
                        return redirect(url_for('index'))
                    if user.role == 'student' and not user.is_verified:
                        flash('Please verify your email first', 'warning')
                        return redirect(url_for('verify_otp', user_id=user.id))
                    login_user(user)
                    next_page = request.args.get('next')
                    return redirect(next_page) if next_page else redirect(url_for('index'))
            
            # 2. Check Club Table
            if g.current_college:
                club = Club.query.filter_by(club_login_id=email, college_id=g.current_college.id).first()
                if club:
                    p_check = club.check_password(password)
                    f.write(f"Found Club: {club.name}. Password Match: {p_check}\n")
                    if p_check:
                        if not club.is_active:
                            flash('This club portal has been deactivated by the admin.', 'danger')
                            return redirect(url_for('index'))
                        session['club_id'] = club.id
                        session['club_name'] = club.name
                        session['role'] = 'President'
                        flash(f'Welcome to {club.name} Portal!', 'success')
                        return redirect(url_for('club_portal.dashboard'))
            else:
                f.write("No college context; skipping club search.\n")
            
            f.write("Result: FAILED\n")
        
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/<college_slug>/student-signup', methods=['GET', 'POST'])
def student_signup():
    # Load college from g (handled by url_value_preprocessor)
    college = getattr(g, 'current_college', None)
    if not college:
        return redirect(url_for('login_global'))
    
    # Check if this service is enabled for the college
    features = json.loads(college.features) if college.features else {}
    if not features.get('attendance') and not features.get('clubs'):
         # Basic validation: if no modules enabled, college might be disabled
         pass

    if request.method == 'POST':
        roll_no = request.form.get('roll_no').upper() # Force Uppercase
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        section = request.form.get('section')
        department = request.form.get('department')
        year = request.form.get('year')
        
        if not validate_roll_no(roll_no):
            flash('Invalid roll number. Must be 5-20 chars, alphanumeric, with at least 1 letter and 1 number (e.g., 24N81A6261).', 'danger')
            # Re-render properly involves passing back data, but for now just validation msg
            departments = Department.query.filter_by(college_id=college.id).all() # Need to re-fetch departments
            return render_template('student_signup.html', departments=departments)
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.role == 'student' and not existing_user.is_verified:
                flash('Email already registered but not verified. Redirecting to OTP verification.', 'info')
                return redirect(url_for('verify_otp', user_id=existing_user.id))
            flash('Email already registered', 'danger')
            departments = Department.query.filter_by(college_id=college.id).all()
            return render_template('student_signup.html', departments=departments)
        
        if User.query.filter_by(roll_no=roll_no, college_id=college.id).first():
            flash('Roll number already registered in this college', 'danger')
            departments = Department.query.filter_by(college_id=college.id).all()
            return render_template('student_signup.html', departments=departments)
        
        student = User(
            college_id=college.id,
            roll_no=roll_no,
            email=email,
            first_name=first_name,
            last_name=last_name,
            section=section,
            department=department,
            year=year,
            role='student',
            is_verified=False
        )
        student.set_password(password)
        
        # Generate OTP
        otp = ''.join(random.choices(string.digits, k=6))
        student.otp = otp
        student.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        
        db.session.add(student)
        db.session.commit()
        
        # Send OTP
        print(f"DEBUG: Generated OTP for {email}: {otp}") # Print to console for local testing
        try:
            # Fetch dynamic SMTP settings
            smtp_config = {}
            configs = SystemConfig.query.all()
            for config in configs:
                smtp_config[config.key] = config.value
            
            # Check if SMTP is configured (basic check)
            if smtp_config.get('MAIL_USERNAME') and smtp_config.get('MAIL_PASSWORD'):
                # Create a new mail connection with dynamic settings
                app.config.update(
                    MAIL_SERVER=smtp_config.get('MAIL_SERVER', 'smtp.gmail.com'),
                    MAIL_PORT=int(smtp_config.get('MAIL_PORT', 587)),
                    MAIL_USERNAME=smtp_config.get('MAIL_USERNAME'),
                    MAIL_PASSWORD=smtp_config.get('MAIL_PASSWORD'),
                    MAIL_USE_TLS=smtp_config.get('MAIL_USE_TLS') == 'True'
                )
                mail = Mail(app) # Re-init mail with new config
                
                msg = Message('Verify your GenZCampus Account',
                            sender=app.config['MAIL_USERNAME'],
                            recipients=[email])
                msg.body = f'Your OTP is: {otp}. It expires in 10 minutes.'
                mail.send(msg)
                flash('Registration successful! Please check your email for OTP.', 'info')
            else:
                flash('Registration successful! OTP printed to console (Dev Mode/SMTP Not Configured).', 'info')
            
            return redirect(url_for('verify_otp', user_id=student.id))
        except Exception as e:
            print(f"Error sending email: {e}")
            flash('Error sending email. Check console for OTP.', 'warning')
            return redirect(url_for('verify_otp', user_id=student.id))
    
    # Fetch departments for the dropdown
    departments = Department.query.filter_by(college_id=college.id).all()
    return render_template('student_signup.html', departments=departments)

@app.route('/<college_slug>/verify-otp/<int:user_id>', methods=['GET', 'POST'])
def verify_otp(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        if user.otp == otp and user.otp_expiry > datetime.utcnow():
            user.is_verified = True
            user.otp = None
            user.otp_expiry = None
            db.session.commit()
            flash('Account verified successfully! Please login.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid or expired OTP', 'danger')
            
    return render_template('verify_otp.html', email=user.email, user_id=user.id)

@app.route('/<college_slug>/resend-otp/<int:user_id>')
def resend_otp(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        flash('Account already verified.', 'info')
        return redirect(url_for('index'))
    
    # Generate new OTP
    otp = ''.join(random.choices(string.digits, k=6))
    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    
    print(f"DEBUG: Resent OTP for {user.email}: {otp}")
    
    try:
        # Fetch dynamic SMTP settings
        smtp_config = {}
        configs = SystemConfig.query.all()
        for config in configs:
            smtp_config[config.key] = config.value
        
        if smtp_config.get('MAIL_USERNAME') and smtp_config.get('MAIL_PASSWORD'):
            app.config.update(
                MAIL_SERVER=smtp_config.get('MAIL_SERVER', 'smtp.gmail.com'),
                MAIL_PORT=int(smtp_config.get('MAIL_PORT', 587)),
                MAIL_USERNAME=smtp_config.get('MAIL_USERNAME'),
                MAIL_PASSWORD=smtp_config.get('MAIL_PASSWORD'),
                MAIL_USE_TLS=smtp_config.get('MAIL_USE_TLS') == 'True'
            )
            mail_new = Mail(app)
            
            msg = Message('Verify your GenZCampus Account - New OTP',
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[user.email])
            msg.body = f'Your new OTP is: {otp}. It expires in 10 minutes.'
            mail_new.send(msg)
            flash('A new OTP has been sent to your email.', 'success')
        else:
            flash('New OTP generated and printed to console (Dev Mode/SMTP Not Configured).', 'info')
    except Exception as e:
        print(f"Error sending email: {e}")
        flash('Error sending email. Check console for OTP.', 'warning')
    
    return redirect(url_for('verify_otp', user_id=user.id))

@app.route('/<college_slug>/change-email-otp/<int:user_id>', methods=['GET', 'POST'])
def change_email_otp(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        flash('Account already verified.', 'info')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_email = request.form.get('email')
        
        # Check if email is already taken
        if User.query.filter_by(email=new_email).first():
            flash('Email already registered', 'danger')
            return render_template('change_email_on_otp.html', user=user)
        
        user.email = new_email
        # Generate new OTP for the new email
        otp = ''.join(random.choices(string.digits, k=6))
        user.otp = otp
        user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        
        print(f"DEBUG: Change Email OTP for {user.email}: {otp}")
        
        try:
            # Send new OTP
            smtp_config = {}
            configs = SystemConfig.query.all()
            for config in configs:
                smtp_config[config.key] = config.value
            
            if smtp_config.get('MAIL_USERNAME') and smtp_config.get('MAIL_PASSWORD'):
                app.config.update(
                    MAIL_SERVER=smtp_config.get('MAIL_SERVER', 'smtp.gmail.com'),
                    MAIL_PORT=int(smtp_config.get('MAIL_PORT', 587)),
                    MAIL_USERNAME=smtp_config.get('MAIL_USERNAME'),
                    MAIL_PASSWORD=smtp_config.get('MAIL_PASSWORD'),
                    MAIL_USE_TLS=smtp_config.get('MAIL_USE_TLS') == 'True'
                )
                mail_new = Mail(app)
                
                msg = Message('Verify your GenZCampus Account - Email Updated',
                            sender=app.config['MAIL_USERNAME'],
                            recipients=[user.email])
                msg.body = f'Your email was updated. Your new OTP is: {otp}. It expires in 10 minutes.'
                mail_new.send(msg)
                flash('Email updated and OTP sent to new address.', 'success')
            else:
                flash('Email updated. New OTP printed to console (Dev Mode/SMTP Not Configured).', 'info')
        except Exception as e:
            print(f"Error sending email: {e}")
            flash('Email updated but error sending email. Check console for OTP.', 'warning')
            
        return redirect(url_for('verify_otp', user_id=user.id))
        
    return render_template('change_email_on_otp.html', user=user)

@app.route('/<college_slug>/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            otp = ''.join(random.choices(string.digits, k=6))
            user.otp = otp
            user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            
            print(f"DEBUG: Password Reset OTP for {email}: {otp}") # Print to console
            try:
                # Fetch dynamic SMTP settings
                smtp_config = {}
                configs = SystemConfig.query.all()
                for config in configs:
                    smtp_config[config.key] = config.value
                
                if smtp_config.get('MAIL_USERNAME') and smtp_config.get('MAIL_PASSWORD'):
                     # Create a new mail connection with dynamic settings
                    app.config.update(
                        MAIL_SERVER=smtp_config.get('MAIL_SERVER', 'smtp.gmail.com'),
                        MAIL_PORT=int(smtp_config.get('MAIL_PORT', 587)),
                        MAIL_USERNAME=smtp_config.get('MAIL_USERNAME'),
                        MAIL_PASSWORD=smtp_config.get('MAIL_PASSWORD'),
                        MAIL_USE_TLS=smtp_config.get('MAIL_USE_TLS') == 'True'
                    )
                    mail = Mail(app) # Re-init mail with new config
                    
                    msg = Message('Reset your GenZCampus Password',
                                sender=app.config['MAIL_USERNAME'],
                                recipients=[email])
                    msg.body = f'Your Password Reset OTP is: {otp}. It expires in 10 minutes.'
                    mail.send(msg)
                else:
                    flash('OTP printed to console (Dev Mode)', 'info')
                
                return redirect(url_for('reset_password', user_id=user.id))
            except Exception as e:
                print(f"Error sending email: {e}")
                flash('Error sending email. Check console for OTP.', 'warning')
                return redirect(url_for('reset_password', user_id=user.id))
        else:
            flash('Email not found', 'danger')
            
    return render_template('forgot_password.html')

@app.route('/<college_slug>/reset-password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if user.otp == otp and user.otp_expiry > datetime.utcnow():
            if new_password == confirm_password:
                user.set_password(new_password)
                user.otp = None
                user.otp_expiry = None
                db.session.commit()
                flash('Password reset successful', 'success')
                return redirect(url_for('index'))
            else:
                flash('Passwords do not match', 'danger')
        else:
            flash('Invalid or expired OTP', 'danger')
            
    return render_template('reset_password.html')

@app.route('/logout')
@app.route('/<college_slug>/logout')
@login_required
def logout(college_slug=None):
    logout_user()
    flash('You have been logged out.', 'info')
    if college_slug:
        return redirect(url_for('index', college_slug=college_slug))
    return redirect(url_for('login_global'))

# PROFILE ROUTE
@app.route('/profile/edit', methods=['GET', 'POST'])
@app.route('/<college_slug>/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile(college_slug=None):
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.email = request.form.get('email')
        current_user.phone = request.form.get('phone')
        
        # Admin can change department, others cannot
        if current_user.is_admin():
            current_user.department = request.form.get('department')
        
        # Handle password change
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password:
            if new_password == confirm_password:
                current_user.set_password(new_password)
                flash('Password updated successfully', 'success')
            else:
                flash('Passwords do not match', 'danger')
                return render_template('edit_profile.html')
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        if college_slug:
            return redirect(url_for('index', college_slug=college_slug))
        return redirect(url_for('super_admin_dashboard'))
    return render_template('edit_profile.html')


 # Serve uploaded files
@app.route('/<college_slug>/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Admin Routes
@app.route('/<college_slug>/admin/dashboard')
@login_required
def admin_dashboard():
    if not (current_user.is_admin() or current_user.is_superadmin):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    college_id = g.current_college.id if getattr(g, 'current_college', None) else current_user.college_id
    
    stats = {
        'total_students': User.query.filter_by(role='student', college_id=college_id).count(),
        'total_faculty': User.query.filter(User.role.in_(['faculty', 'hod']), User.college_id==college_id).count(),
        'pending_permissions': Permission.query.filter_by(status='pending', college_id=college_id).count(),
        'total_clubs': Club.query.filter_by(college_id=college_id).count()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/<college_slug>/admin/students')
@login_required
def manage_students():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get parameters
    year = request.args.get('year')
    dept = request.args.get('dept')
    section = request.args.get('section')
    search = request.args.get('search', '').strip()
    
    show_results = True
    
    query = User.query.filter_by(role='student', college_id=current_user.college_id)
    
    if year:
        query = query.filter_by(year=year)
    
    if dept:
        query = query.filter_by(department=dept)

    if section:
        query = query.filter_by(section=section)
        
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            db.or_(
                User.roll_no.ilike(search_filter),
                User.first_name.ilike(search_filter),
                User.last_name.ilike(search_filter)
            )
        )
        
    students = query.order_by(User.year, User.department, User.section, User.roll_no).all()
        
    departments = Department.query.filter_by(college_id=current_user.college_id).order_by(Department.name).all()
    return render_template('admin/students.html', 
                         students=students, 
                         departments=departments, 
                         current_year=year, 
                         current_dept=dept, 
                         current_section=section,
                         search=search,
                         show_results=show_results)

@app.route('/<college_slug>/admin/students/add', methods=['POST'])
@login_required
def add_student():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_students'))

    roll_no = request.form.get('roll_no').upper() # Force Uppercase
    email = request.form.get('email')
    password = request.form.get('password') or 'student123'
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    department = request.form.get('department')
    year = request.form.get('year')
    section = request.form.get('section')
    
    if User.query.filter_by(roll_no=roll_no, college_id=current_user.college_id).first():
        flash('Roll number already exists', 'danger')
        return redirect(url_for('manage_students'))

    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('manage_students'))

    student = User(
        roll_no=roll_no,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role='student',
        department=department,
        year=year,
        section=section,
        college_id=current_user.college_id,
        is_verified=True # Admin created students are auto-verified
    )
    student.set_password(password)
    
    db.session.add(student)
    db.session.commit()
    
    flash('Student added successfully', 'success')
    return redirect(url_for('manage_students'))

@app.route('/<college_slug>/admin/students/promote', methods=['POST'])
@login_required
def promote_students():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_students'))
    
    department = request.form.get('department')
    year = request.form.get('year')
    
    query = User.query.filter_by(role='student', college_id=g.current_college.id)
    if department:
        query = query.filter_by(department=department)
    if year:
        query = query.filter_by(year=year)
        
    students = query.all()
    promoted_count = 0
    for student in students:
        if student.year and int(student.year) < 4:
            student.year = int(student.year) + 1
            promoted_count += 1
    
    db.session.commit()
    flash(f'Successfully promoted {promoted_count} students.', 'success')
    return redirect(url_for('manage_students'))

@app.route('/<college_slug>/admin/students/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_students'))
    
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Can only edit student accounts', 'danger')
        return redirect(url_for('manage_students'))
        
    if request.method == 'POST':
        student.first_name = request.form.get('first_name')
        student.last_name = request.form.get('last_name')
        student.email = request.form.get('email')
        student.phone = request.form.get('phone')
        student.department = request.form.get('department')
        student.year = request.form.get('year')
        student.section = request.form.get('section')
        
        # Admin can block/unblock
        is_blocked = request.form.get('is_blocked') == 'on'
        student.is_blocked = is_blocked
        
        # Admin can set password
        password = request.form.get('password')
        if password:
            student.set_password(password)
            
        db.session.commit()
        flash('Student profile updated successfully', 'success')
        return redirect(url_for('manage_students'))
        
    # Fetch departments for the dropdown
    departments = Department.query.filter_by(college_id=current_user.college_id).all()
    return render_template('admin/edit_student.html', student=student, departments=departments)


@app.route('/<college_slug>/admin/students/delete/<int:student_id>')
@login_required
def delete_student(student_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_students'))
    
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Can only delete student accounts', 'danger')
        return redirect(url_for('manage_students'))
    
    # Delete associated permissions
    Permission.query.filter_by(student_id=student_id).delete()
    
    db.session.delete(student)
    db.session.commit()
    
    flash('Student deleted successfully', 'success')
    return redirect(url_for('manage_students'))

@app.route('/<college_slug>/admin/students/bulk-upload', methods=['POST'])
@login_required
def bulk_upload_students():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_students'))
    
    if 'file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('manage_students'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('manage_students'))
    
    if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            created_count = 0
            skipped_count = 0
            seen_rolls = set()
            seen_emails = set()
            
            for _, row in df.iterrows():
                roll_no = str(row['roll_no']).upper()
                email = str(row['email']).lower().strip()
                
                # Basic validation
                if pd.isna(email) or not email or not pd.notna(row['roll_no']):
                    skipped_count += 1
                    continue
                    
                if validate_roll_no(roll_no) and roll_no not in seen_rolls and email not in seen_emails:
                    if not User.query.filter_by(roll_no=roll_no, college_id=current_user.college_id).first() and not User.query.filter_by(email=email).first():
                        student = User(
                            roll_no=roll_no,
                            email=email,
                            first_name=row['first_name'],
                            last_name=row['last_name'],
                            section=row['section'],
                            department=row.get('department', 'CSE'),
                            year=row.get('year'),
                            role='student'
                        )
                        student.set_password('default123')
                        db.session.add(student)
                        seen_rolls.add(roll_no)
                        seen_emails.add(email)
                        created_count += 1
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
            
            db.session.commit()
            
            msg = f'Successfully created {created_count} student accounts.'
            if skipped_count > 0:
                msg += f' Skipped {skipped_count} invalid or duplicate entries.'
            flash(msg, 'success')
        
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
    else:
        flash('Invalid file type. Please upload CSV or Excel file.', 'danger')
    
    return redirect(url_for('manage_students'))

# --- TimeTable Management ---

@app.route('/<college_slug>/admin/timetable')
@login_required
def manage_timetable():
    if not current_user.is_admin() and not current_user.is_hod():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        flash('Timetable service is currently disabled for this institution.', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    depts = Department.query.all()
    selected_dept = request.args.get('department')
    selected_year = request.args.get('year')
    selected_section = request.args.get('section')
    
    timetable_data = {}
    active_days = []
    max_periods = 7
    if selected_dept and selected_year and selected_section:
        records = TimeTable.query.filter_by(college_id=current_user.college_id, 
            department=selected_dept, 
            year=selected_year, 
            section=selected_section
        ).all()
        for r in records:
            timetable_data[r.day] = r
            
        if records:
            day_order = {'Monday':1, 'Tuesday':2, 'Wednesday':3, 'Thursday':4, 'Friday':5, 'Saturday':6, 'Sunday':7}
            active_days = sorted([r.day for r in records], key=lambda d: day_order.get(d, 99))
            
            max_p = 0
            for r in records:
                for i in range(10, 0, -1):
                    if getattr(r, f'period_{i}') or getattr(r, f'period_{i}_time'):
                        if i > max_p:
                            max_p = i
                        break
            if max_p > 0:
                max_periods = max_p

    if not active_days:
        active_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        max_periods = 7
            
    return render_template('admin/manage_timetable.html', 
                           departments=depts,
                           selected_dept=selected_dept,
                           selected_year=selected_year,
                           selected_section=selected_section,
                           timetable_data=timetable_data,
                           active_days=active_days,
                           max_periods=max_periods)

@app.route('/<college_slug>/admin/timetable/analyze', methods=['POST'])
@login_required
def analyze_timetable():
    if not current_user.is_admin() and not current_user.is_hod():
        return jsonify({'error': 'Unauthorized'}), 403
        
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        return jsonify({'error': 'Timetable service is disabled for this institution.'}), 403
        
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    dept = request.form.get('department', '').upper()
    year = request.form.get('year', '')
    section = request.form.get('section', '')

    try:
        from google import genai
        import PIL.Image
        from dotenv import load_dotenv

        # Ensure environment variables are loaded for the running process
        load_dotenv(os.path.join(os.path.abspath(os.path.dirname(__file__)), '.env'))

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")

        client = genai.Client(api_key=api_key)
        
        # Save temp file
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_timetable_' + secure_filename(file.filename))
        file.save(temp_path)
        
        img = PIL.Image.open(temp_path)
        
        prompt = f"""
        Analyze this university timetable image.
        Extract the subjects for each period (usually 1 to 7) for Monday to Saturday.
        Also, extract the precise time duration for each of the 7 periods. Provide time strictly in 24-hour format (e.g., '13:00 - 13:50', not '1:00 - 1:50' or '1:00 PM').
        
        Return ONLY a raw JSON mapping with the following exact structure, with no markdown formatting, no backticks, just the JSON string:
        {{
            "parsed_data": {{
                "Monday": ["Sub 1", "Sub 2", "Sub 3", "Sub 4", "Sub 5", "Sub 6", "Sub 7"],
                "Tuesday": ["...", "...", "...", "...", "...", "...", "..."],
                "Wednesday": ["...", "...", "...", "...", "...", "...", "..."],
                "Thursday": ["...", "...", "...", "...", "...", "...", "..."],
                "Friday": ["...", "...", "...", "...", "...", "...", "..."],
                "Saturday": ["...", "...", "...", "...", "...", "...", "..."]
            }},
            "timings": [
                "09:00 - 10:00",
                "10:00 - 10:50",
                "11:00 - 11:50",
                "11:50 - 12:40",
                "13:30 - 14:20",
                "14:20 - 15:10",
                "15:10 - 16:00"
            ]
        }}
        Note: If a period says "Break" or "Lunch" or is empty, use an empty string "" for the subject.
        Make sure to exclude explicit break/lunch columns from the 'parsed_data' array if they are not actual class periods. We only want the 7 class periods.
        """
        
        response = None
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[img, prompt]
            )
        finally:
            # Assure cleanup
            try:
                os.remove(temp_path)
            except:
                pass
                
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_str)
        
        parsed_data = data.get("parsed_data", {})
        # If API failed to provide 7 timings, fallback to defaults
        extracted_timings = data.get("timings", [])
        if not extracted_timings or len(extracted_timings) < 7:
            extracted_timings = ["09:30 - 10:20", "10:20 - 11:10", "11:10 - 12:00", "13:00 - 13:50", "13:50 - 14:40", "14:40 - 15:30", "15:30 - 16:20"]
            
        detected_format = f"{dept} ({year} Year, Section {section}) - AI Extracted"

        return jsonify({
            'success': True,
            'parsed_data': parsed_data,
            'timings': extracted_timings,
            'detected_format': detected_format,
            'message': f'Digital Twin Analysis complete using Gemini for {detected_format}.'
        })

    except Exception as e:
        print(f"Gemini Extraction Error: {e}")
        # Generic fallback for other departments if AI fails
        import random
        subjects_pool = ["DSA", "DBMS", "JAVA", "PYTHON", "DAA", "CAO", "OS", "CN", "WT"]
        parsed_data = {}
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']:
            day_subjects = []
            for p in range(7):
                day_subjects.append(random.choice(subjects_pool) if random.random() > 0.1 else "")
            parsed_data[day] = day_subjects
        detected_format = f"{dept} ({year} Year, Section {section}) - Feedback Simulation"
        timings = ["09:30 - 10:20", "10:20 - 11:10", "11:10 - 12:00", "13:00 - 13:50", "13:50 - 14:40", "14:40 - 15:30", "15:30 - 16:20"]

        return jsonify({
            'success': True,
            'parsed_data': parsed_data,
            'timings': timings,
            'detected_format': detected_format,
            'message': f'Analysis simulation fallback used for {detected_format}.'
        })

@app.route('/<college_slug>/admin/timetable/save', methods=['POST'])
@login_required
def save_timetable():
    if not current_user.is_admin() and not current_user.is_hod():
        return jsonify({'error': 'Unauthorized'}), 403
        
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        return jsonify({'error': 'Timetable service is disabled for this institution.'}), 403
        
    data = request.get_json()
    dept = data.get('department')
    year = data.get('year')
    sec = data.get('section')
    schedule = data.get('schedule') # { 'Monday': ['Sub1', 'Sub2', ...], 'Tuesday': ... }
    timings = data.get('timings')   # ['Time1', 'Time2', ...]
    
    if not all([dept, year, sec, schedule]):
        return jsonify({'error': 'Missing data'}), 400
        
    try:
        # Delete any days not in the new schedule to support row deletion
        if schedule:
            existing_records = TimeTable.query.filter_by(
                college_id=current_user.college_id,
                department=dept, 
                year=year, 
                section=sec
            ).all()
            for r in existing_records:
                if r.day not in schedule:
                    db.session.delete(r)

        for day, periods in schedule.items():
            record = TimeTable.query.filter_by(
                college_id=current_user.college_id,
                department=dept, 
                year=year, 
                section=sec, 
                day=day
            ).first()
            
            if not record:
                record = TimeTable(
                    college_id=current_user.college_id,
                    department=dept, 
                    year=year, 
                    section=sec, 
                    day=day
                )
                db.session.add(record)
            
            # Update periods
            record.period_1 = periods[0] if len(periods) > 0 else None
            record.period_2 = periods[1] if len(periods) > 1 else None
            record.period_3 = periods[2] if len(periods) > 2 else None
            record.period_4 = periods[3] if len(periods) > 3 else None
            record.period_5 = periods[4] if len(periods) > 4 else None
            record.period_6 = periods[5] if len(periods) > 5 else None
            record.period_7 = periods[6] if len(periods) > 6 else None
            record.period_8 = periods[7] if len(periods) > 7 else None
            record.period_9 = periods[8] if len(periods) > 8 else None
            record.period_10 = periods[9] if len(periods) > 9 else None

            # Update timings
            if timings:
                record.period_1_time = timings[0] if len(timings) > 0 else None
                record.period_2_time = timings[1] if len(timings) > 1 else None
                record.period_3_time = timings[2] if len(timings) > 2 else None
                record.period_4_time = timings[3] if len(timings) > 3 else None
                record.period_5_time = timings[4] if len(timings) > 4 else None
                record.period_6_time = timings[5] if len(timings) > 5 else None
                record.period_7_time = timings[6] if len(timings) > 6 else None
                record.period_8_time = timings[7] if len(timings) > 7 else None
                record.period_9_time = timings[8] if len(timings) > 8 else None
                record.period_10_time = timings[9] if len(timings) > 9 else None
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Timetable saved successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/<college_slug>/admin/students/export')
@login_required
def export_students():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    year = request.args.get('year')
    dept = request.args.get('dept')
    
    query = User.query.filter_by(role='student', college_id=current_user.college_id)
    if year:
        query = query.filter_by(year=year)
    if dept:
        query = query.filter_by(department=dept)
        
    students = query.all()
    
    data = []
    for s in students:
        data.append({
            'Roll No': s.roll_no,
            'First Name': s.first_name,
            'Last Name': s.last_name,
            'Email': s.email,
            'Phone': s.phone or '',
            'Year': s.year or '',
            'Department': s.department or '',
            'Section': s.section or '',
            'Registered At': s.created_at.strftime('%Y-%m-%d %H:%M:%S') if s.created_at else ''
        })
        
    df = pd.DataFrame(data)
    
    # Save to a temporary file
    filename = f"students_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df.to_excel(filepath, index=False)
    
    return send_file(filepath, as_attachment=True)

@app.route('/<college_slug>/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # 1. Handle SMTP Settings
        if 'mail_server' in request.form:
            configs = {
                'MAIL_SERVER': request.form.get('mail_server'),
                'MAIL_PORT': request.form.get('mail_port'),
                'MAIL_USERNAME': request.form.get('mail_username'),
                'MAIL_PASSWORD': request.form.get('mail_password'),
                'MAIL_USE_TLS': 'True' if request.form.get('mail_use_tls') else 'False'
            }
            for key, value in configs.items():
                config = SystemConfig.query.filter_by(key=key).first()
                if config: config.value = value
                else: db.session.add(SystemConfig(key=key, value=value))
            flash('SMTP settings updated successfully', 'success')

        # 2. Handle Logo Upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(f"college_{g.current_college.id}_{file.filename}")
                    
                    try:
                        # 1. Upload to Supabase Storage
                        if supabase:
                            # Read file content
                            file_content = file.read()
                            bucket_name = "logos"
                            
                            # Standard upload to Supabase
                            supabase.storage.from_(bucket_name).upload(
                                path=filename,
                                file=file_content,
                                file_options={"content-type": file.content_type, "x-upsert": "true"}
                            )
                            
                            # Get Public URL
                            logo_url = supabase.storage.from_(bucket_name).get_public_url(filename)
                            
                            # 2. Update DB for THIS college specifically
                            config = SystemConfig.query.filter_by(key='college_logo', college_id=g.current_college.id).first()
                            if not config:
                                config = SystemConfig(key='college_logo', value=logo_url, college_id=g.current_college.id)
                                db.session.add(config)
                            else:
                                config.value = logo_url
                            
                            flash('College logo updated to cloud successfully!', 'success')
                        else:
                            flash('Cloud storage not configured.', 'danger')
                    except Exception as e:
                        flash(f'Upload failed: {str(e)}', 'danger')
                else:
                    flash('Invalid file type. Please upload an image.', 'danger')
        
        db.session.commit()
        return redirect(url_for('admin_settings'))
        
    # Data for the template
    logo_config = SystemConfig.query.filter_by(key='college_logo', college_id=g.current_college.id).first()
    smtp_configs = SystemConfig.query.filter(SystemConfig.key.like('MAIL_%')).all()
    
    return render_template('admin/settings.html', 
                         current_logo=logo_config.value if logo_config else None,
                         smtp_configs=smtp_configs)

@app.route('/<college_slug>/admin/departments')
@login_required
def manage_departments():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    departments = Department.query.filter_by(college_id=current_user.college_id).order_by(Department.name).all()
    return render_template('admin/departments.html', departments=departments)

@app.route('/<college_slug>/admin/departments/view/<int:dept_id>')
@login_required
def view_department(dept_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_departments'))
    
    department = Department.query.get_or_404(dept_id)
    
    students = User.query.filter_by(role='student', department=department.name, college_id=current_user.college_id).order_by(User.year, User.section, User.roll_no).all()
    total_students = len(students)
    
    students_by_section = {}
    for s in students:
        sec = f"Year {s.year} - Sec {s.section}"
        if sec not in students_by_section:
            students_by_section[sec] = []
        students_by_section[sec].append(s)
        
    faculty_list = User.query.filter(User.role.in_(['faculty', 'hod']), User.department==department.name, User.college_id==current_user.college_id).all()
    
    hods = [f for f in faculty_list if f.role == 'hod']
    incharges = [f for f in faculty_list if f.incharge_department == department.name]
    
    return render_template('admin/department_details.html',
                           department=department,
                           total_students=total_students,
                           students_by_section=students_by_section,
                           hods=hods,
                           incharges=incharges,
                           faculty_list=faculty_list)

@app.route('/<college_slug>/admin/departments/add', methods=['POST'])
@login_required
def add_department():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_departments'))
    
    name = request.form.get('name').upper()
    
    if Department.query.filter_by(name=name).first():
        flash('Department already exists', 'danger')
        return redirect(url_for('manage_departments'))
    
    department = Department(name=name)
    db.session.add(department)
    db.session.commit()
    
    flash('Department added successfully', 'success')
    return redirect(url_for('manage_departments'))

@app.route('/<college_slug>/admin/departments/delete/<int:dept_id>')
@login_required
def delete_department(dept_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_departments'))
    
    department = Department.query.get_or_404(dept_id)
    
    # Safe delete check: check if any users belong to this department
    linked_users = User.query.filter_by(department=department.name, college_id=current_user.college_id).first()
    if linked_users:
        flash(f'Cannot delete department "{department.name}" because it is linked to existing students or faculty.', 'danger')
        return redirect(url_for('manage_departments'))
    
    # Also check for class incharge assignments just in case
    linked_incharge = User.query.filter_by(incharge_department=department.name, college_id=current_user.college_id).first()
    if linked_incharge:
        flash(f'Cannot delete department "{department.name}" because it is assigned as an incharge department for faculty.', 'danger')
        return redirect(url_for('manage_departments'))
        
    db.session.delete(department)
    db.session.commit()
    
    flash('Department deleted successfully', 'success')
    return redirect(url_for('manage_departments'))

@app.route('/<college_slug>/admin/faculty')
@login_required
def manage_faculty():
    if not (current_user.is_admin() or current_user.is_hod()):
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if current_user.is_hod():
        # HOD can see faculty whose primary department is the HOD's department,
        # OR faculty who specify the HOD's department in their handling_departments.
        faculty = User.query.filter(User.role == 'faculty').filter(
            db.or_(
                User.department == current_user.department,
                User.handling_departments.like(f"%{current_user.department}%")
            )
        , User.college_id == current_user.college_id).all()
        departments = [Department.query.filter_by(name=current_user.department, college_id=current_user.college_id).first()]
    else:
        faculty = User.query.filter(User.role.in_(['faculty', 'hod']), User.college_id == current_user.college_id).all()
        departments = Department.query.filter_by(college_id=current_user.college_id).order_by(Department.name).all()
        
    return render_template('admin/faculty.html', faculty=faculty, departments=departments)

@app.route('/<college_slug>/admin/faculty/edit/<int:faculty_id>', methods=['GET', 'POST'])
@login_required
def edit_faculty(faculty_id):
    if not (current_user.is_admin() or current_user.is_hod()):
        flash('Access denied', 'danger')
        return redirect(url_for('manage_faculty'))
    
    faculty = User.query.get_or_404(faculty_id)
    
    if current_user.is_hod():
        if faculty.department != current_user.department or faculty.role == 'hod':
            flash('Access denied', 'danger')
            return redirect(url_for('manage_faculty'))
    else:
        if not faculty.is_faculty():
            flash('Can only edit faculty accounts', 'danger')
            return redirect(url_for('manage_faculty'))
        
    if request.method == 'POST':
        faculty.first_name = request.form.get('first_name')
        faculty.last_name = request.form.get('last_name')
        faculty.email = request.form.get('email')
        faculty.phone = request.form.get('phone')
        
        if not current_user.is_hod():
            # Only admin can change these base fields
            faculty.role = request.form.get('role')
            faculty.department = request.form.get('department')
        
        # Handling Departments multi-select
        handling_depts = request.form.getlist('handling_departments')
        faculty.handling_departments = ','.join(handling_depts) if handling_depts else ''
        
        # Subjects multi-select (can be typed dynamically)
        subjects_list = request.form.getlist('subjects')
        faculty.subjects = ','.join([s.strip() for s in subjects_list if s.strip()])
        
        # Block/Unblock
        is_blocked = request.form.get('is_blocked') == 'on'
        faculty.is_blocked = is_blocked
        
        # Password Reset
        password = request.form.get('password')
        if password:
            faculty.set_password(password)
            
        # Class Incharge Assignment
        incharge_dept = request.form.get('incharge_department')
        incharge_sec = request.form.get('incharge_section')
        
        if incharge_dept and incharge_sec:
            faculty.incharge_department = incharge_dept
            faculty.incharge_section = incharge_sec
        else:
            # If cleared
            faculty.incharge_department = None
            faculty.incharge_section = None
            
        db.session.commit()
        flash('Faculty profile updated successfully', 'success')
        return redirect(url_for('manage_faculty'))
        
    # Get departments for dropdown
    departments = Department.query.filter_by(college_id=current_user.college_id).all()
    return render_template('admin/edit_faculty.html', faculty=faculty, departments=departments)

@app.route('/<college_slug>/admin/faculty/delete/<int:faculty_id>')
@login_required
def delete_faculty(faculty_id):
    if not (current_user.is_admin() or current_user.is_hod()):
        flash('Access denied', 'danger')
        return redirect(url_for('manage_faculty'))
    
    faculty = User.query.get_or_404(faculty_id)
    
    if current_user.is_hod():
        if faculty.department != current_user.department or faculty.role == 'hod':
            flash('Access denied', 'danger')
            return redirect(url_for('manage_faculty'))
    else:
        if not faculty.is_faculty():
            flash('Can only delete faculty accounts', 'danger')
            return redirect(url_for('manage_faculty'))
        
    db.session.delete(faculty)
    db.session.commit()
    flash('Faculty deleted successfully', 'success')
    return redirect(url_for('manage_faculty'))

@app.route('/<college_slug>/admin/faculty/add', methods=['POST'])
@login_required
def add_faculty():
    if not (current_user.is_admin() or current_user.is_hod()):
        flash('Access denied', 'danger')
        return redirect(url_for('manage_faculty'))
    
    email = request.form.get('email')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    
    if current_user.is_hod():
        role = 'faculty'
        department = current_user.department
    else:
        role = request.form.get('role')
        department = request.form.get('department')
    
    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('manage_faculty'))
    
    handling_depts = request.form.getlist('handling_departments')
    handling_departments_str = ','.join(handling_depts) if handling_depts else ''
    
    subjects_list = request.form.getlist('subjects')
    subjects_str = ','.join([s.strip() for s in subjects_list if s.strip()])
    
    faculty = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role,
        department=department,
        handling_departments=handling_departments_str,
        subjects=subjects_str,
        college_id=current_user.college_id
    )
    
    password = request.form.get('password')
    if password:
        faculty.set_password(password)
    else:
        faculty.set_password('faculty123')
    
    db.session.add(faculty)
    db.session.commit()
    
    flash('Faculty added successfully', 'success')
    return redirect(url_for('manage_faculty'))



@app.route('/<college_slug>/admin/clubs')
@login_required
def manage_clubs():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    clubs = Club.query.filter_by(college_id=current_user.college_id).all()
    
    # Calculate stats for the dashboard
    stats = {
        'total_clubs': len(clubs),
        'active_portals': Club.query.filter_by(is_active=True).count(),
        'upcoming_events': Event.query.filter_by(status='upcoming', college_id=current_user.college_id).count(),
        'active_events': Event.query.filter_by(status='active', college_id=current_user.college_id).count()
    }
    
    return render_template('admin/clubs.html', clubs=clubs, stats=stats)

@app.route('/<college_slug>/admin/clubs/add', methods=['POST'])
@login_required
def add_club():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_clubs'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    login_id = request.form.get('club_login_id')
    password = request.form.get('password')
    
    if Club.query.filter_by(club_login_id=login_id).first():
        flash('Club Login ID already exists', 'danger')
        return redirect(url_for('manage_clubs'))
        
    club = Club(name=name, description=description, club_login_id=login_id)
    club.set_password(password)
    db.session.add(club)
    db.session.commit()
    
    flash('Club added successfully with portal access', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/clubs/edit/<int:club_id>', methods=['POST'])
@login_required
def edit_club(club_id):
    if not current_user.is_admin(): return redirect(url_for('index'))
    club = Club.query.get_or_404(club_id)
    club.name = request.form.get('name')
    club.description = request.form.get('description')
    club.club_login_id = request.form.get('club_login_id')
    
    password = request.form.get('password')
    if password:
        club.set_password(password)
        
    db.session.commit()
    flash('Club updated successfully', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/clubs/toggle/<int:club_id>')
@login_required
def toggle_club(club_id):
    if not current_user.is_admin(): return redirect(url_for('index'))
    club = Club.query.get_or_404(club_id)
    club.is_active = not club.is_active
    db.session.commit()
    status = "enabled" if club.is_active else "disabled"
    flash(f'Club {status} successfully', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/clubs/reset-password/<int:club_id>', methods=['POST'])
@login_required
def reset_club_password(club_id):
    if not current_user.is_admin():
        return redirect(url_for('index'))
    club = Club.query.get_or_404(club_id)
    new_password = request.form.get('new_password')
    if not new_password or len(new_password) < 4:
        flash('Password must be at least 4 characters.', 'danger')
        return redirect(url_for('manage_clubs'))
    club.set_password(new_password)
    db.session.commit()
    flash(f'Password for {club.name} portal reset successfully!', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/clubs/delete/<int:club_id>')
@login_required
def delete_club(club_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_clubs'))
    
    club = Club.query.get_or_404(club_id)
    
    # Check if club has events
    if club.events:
        flash('Cannot delete club that has events. Delete events first.', 'danger')
        return redirect(url_for('manage_clubs'))
    
    db.session.delete(club)
    db.session.commit()
    
    flash('Club deleted successfully', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/events/add', methods=['POST'])
@login_required
def add_event():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_clubs'))
    
    club_id = request.form.get('club_id')
    name = request.form.get('name')
    description = request.form.get('description')
    date = request.form.get('date')
    venue = request.form.get('venue')
    deadline_str = request.form.get('registration_deadline')
    
    event = Event(
        club_id=club_id,
        name=name,
        description=description,
        date=datetime.strptime(date, '%Y-%m-%d'),
        venue=venue,
        registration_deadline=datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M') if deadline_str else None
    )
    db.session.add(event)
    db.session.commit()
    
    flash('Event added successfully', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/events/delete/<int:event_id>')
@login_required
def delete_event(event_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('manage_clubs'))
    
    event = Event.query.get_or_404(event_id)
    
    # Check if event has permissions
    if event.permissions:
        flash('Cannot delete event that has permission requests.', 'danger')
        return redirect(url_for('manage_clubs'))
    
    db.session.delete(event)
    db.session.commit()
    
    flash('Event deleted successfully', 'success')
    return redirect(url_for('manage_clubs'))

@app.route('/<college_slug>/admin/permissions')
@login_required
def admin_permissions():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permissions = Permission.query.filter_by(college_id=current_user.college_id).order_by(Permission.applied_at.desc()).all()
    return render_template('admin/permissions.html', permissions=permissions)

@app.route('/<college_slug>/admin/permission/<int:permission_id>')
@login_required
def admin_view_permission(permission_id):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permission = Permission.query.get_or_404(permission_id)
    return render_template('admin/permission_details.html', permission=permission)

@app.route('/<college_slug>/admin/permission/<int:permission_id>/<action>')
@login_required
def admin_update_permission(permission_id, action):
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permission = Permission.query.get_or_404(permission_id)
    
    if action == 'approve':
        permission.status = 'approved'
        permission.approved_by = current_user.id
        permission.approved_at = datetime.utcnow()
        flash('Permission approved', 'success')
    elif action == 'reject':
        permission.status = 'rejected'
        permission.approved_by = current_user.id
        permission.approved_at = datetime.utcnow()
        flash('Permission rejected', 'warning')
    
    db.session.commit()
    return redirect(url_for('admin_permissions'))

# Faculty Routes
@app.route('/<college_slug>/faculty/view-timetable')
@login_required
def faculty_view_timetable():
    if not current_user.is_faculty():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        flash('Timetable service is currently disabled by administrator.', 'warning')
        return redirect(url_for('faculty_dashboard'))
    
    departments = Department.query.filter_by(college_id=current_user.college_id).order_by(Department.name).all()
    
    selected_dept = request.args.get('department')
    selected_year = request.args.get('year')
    selected_section = request.args.get('section')
    
    timetable_data = {}
    active_days = []
    max_periods = 7
    if selected_dept and selected_year and selected_section:
        records = TimeTable.query.filter_by(college_id=current_user.college_id, 
            department=selected_dept, 
            year=selected_year, 
            section=selected_section
        ).all()
        for r in records:
            timetable_data[r.day] = r
            
        if records:
            day_order = {'Monday':1, 'Tuesday':2, 'Wednesday':3, 'Thursday':4, 'Friday':5, 'Saturday':6, 'Sunday':7}
            active_days = sorted([r.day for r in records], key=lambda d: day_order.get(d, 99))
            
            max_p = 0
            for r in records:
                for i in range(10, 0, -1):
                    if getattr(r, f'period_{i}') or getattr(r, f'period_{i}_time'):
                        if i > max_p:
                            max_p = i
                        break
            if max_p > 0:
                max_periods = max_p

    if not active_days:
        active_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        max_periods = 7
            
    return render_template('faculty/view_timetable.html', 
                           departments=departments,
                           selected_dept=selected_dept,
                           selected_year=selected_year,
                           selected_section=selected_section,
                           timetable_data=timetable_data,
                           active_days=active_days,
                           max_periods=max_periods)

@app.route('/<college_slug>/faculty/dashboard')
@login_required
def faculty_dashboard():
    if not current_user.is_faculty():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Helper to group permissions
    from itertools import groupby
    
    def group_permissions(permissions):
        # Sort by Date (desc) then Section (asc)
        permissions.sort(key=lambda x: (x.date, x.student.section), reverse=True)
        
        grouped = {}
        # Group by Date
        for date, date_group in groupby(permissions, key=lambda x: x.date):
            date_str = date.strftime('%Y-%m-%d')
            grouped[date_str] = {}
            # Group by Section
            # We need to convert iterator to list to use it multiple times if needed, 
            # but here we just iterate again.
            # However, groupby returns an iterator that consumes the original.
            # We need to collect the date_group first.
            date_perms = list(date_group)
            
            # Now Sort by Section for the inner groupby
            date_perms.sort(key=lambda x: x.student.section)
            
            for section, section_group in groupby(date_perms, key=lambda x: x.student.section):
                grouped[date_str][section] = list(section_group)
        return grouped

    is_incharge = current_user.is_incharge()
    # To keep dashboards clean, hide permissions applied more than 15 days ago
    visibility_cutoff = datetime.utcnow() - timedelta(days=15)
    
    if current_user.is_hod():
        # HOD sees pending permissions from their department
        pending_permissions_query = Permission.query.join(
            User, Permission.student_id == User.id
        ).filter(
            User.department == current_user.department,
            Permission.status == 'pending',
            Permission.applied_at >= visibility_cutoff
        ).all()
        
        pending_grouped = group_permissions(pending_permissions_query)
        
        # HOD can also see approved permissions for their department
        # (Using the same base query)
        approved_permissions_query = Permission.query.join(
            User, Permission.student_id == User.id
        ).filter(
            User.department == current_user.department,
            Permission.status == 'approved',
            Permission.applied_at >= visibility_cutoff
        ).all()
        
        approved_grouped = group_permissions(approved_permissions_query)
        approved_list = approved_permissions_query
        
    elif is_incharge:
        # Class Incharge sees pending permissions from their assigned section
        pending_permissions_query = Permission.query.join(
            User, Permission.student_id == User.id
        ).filter(
            User.department == current_user.incharge_department,
            User.section == current_user.incharge_section,
            Permission.status == 'pending',
            Permission.applied_at >= visibility_cutoff
        ).all()
        
        pending_grouped = group_permissions(pending_permissions_query)
        
        # Standard faculty view: approved permissions for primary OR handled departments
        handling_depts = current_user.handling_departments.split(',') if current_user.handling_departments else []
        visible_depts = [current_user.department] + [d.strip() for d in handling_depts if d.strip()]
        
        approved_permissions_query = Permission.query.join(
            User, Permission.student_id == User.id
        ).filter(
            User.department.in_(visible_depts),
            Permission.status == 'approved',
            Permission.applied_at >= visibility_cutoff
        ).all()
        
        approved_grouped = group_permissions(approved_permissions_query)
        approved_list = approved_permissions_query

    else:
        # Regular faculty sees only approved permissions
        pending_grouped = {}
        # Standard faculty view: approved permissions for primary OR handled departments
        handling_depts = current_user.handling_departments.split(',') if current_user.handling_departments else []
        visible_depts = [current_user.department] + [d.strip() for d in handling_depts if d.strip()]
        
        approved_permissions_query = Permission.query.join(
            User, Permission.student_id == User.id
        ).filter(
            User.department.in_(visible_depts),
            Permission.status == 'approved',
            Permission.applied_at >= visibility_cutoff
        ).all()
        
        approved_grouped = group_permissions(approved_permissions_query)
        approved_list = approved_permissions_query
    
    return render_template('faculty/dashboard.html', 
                         pending_grouped=pending_grouped,
                         approved_grouped=approved_grouped,
                         approved_list=approved_list,
                         is_hod=current_user.is_hod(),
                         is_incharge=is_incharge)

@app.route('/<college_slug>/faculty/permission/<int:permission_id>')
@login_required
def view_permission(permission_id):
    if not current_user.is_faculty():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permission = Permission.query.get_or_404(permission_id)
    return render_template('faculty/permission_details.html', permission=permission)

@app.route('/<college_slug>/faculty/permission/<int:permission_id>/<action>')
@login_required
def update_permission_status(permission_id, action):
    if not current_user.is_faculty():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permission = Permission.query.get_or_404(permission_id)
    student = permission.student
    
    # Check authorization
    is_authorized = False
    if current_user.is_hod() and current_user.department == student.department:
        is_authorized = True
    elif current_user.is_incharge() and \
         current_user.incharge_department == student.department and \
         current_user.incharge_section == student.section:
        is_authorized = True
        
    if not is_authorized:
        flash('You are not authorized to manage this permission', 'danger')
        return redirect(url_for('faculty_dashboard'))
    
    if action == 'approve':
        permission.status = 'approved'
        permission.approved_by = current_user.id
        permission.approved_at = datetime.utcnow()
        flash('Permission approved', 'success')
    elif action == 'reject':
        permission.status = 'rejected'
        permission.approved_by = current_user.id
        permission.approved_at = datetime.utcnow()
        flash('Permission rejected', 'warning')
    
    db.session.commit()
    return redirect(url_for('faculty_dashboard'))

# --- Faculty Class Attendance APIs ---
@app.route('/<college_slug>/api/faculty/students')
@login_required
def get_faculty_students():
    if not current_user.is_faculty():
        return jsonify({'error': 'Unauthorized'}), 403
        
    department = request.args.get('department')
    section = request.args.get('section')
    year = request.args.get('year')
    date_str = request.args.get('date')
    
    # Default to IST today if no date provided
    if not date_str:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        query_date = ist_now.date()
    else:
        try:
            query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            query_date = (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()
    
    if not department or not section or not year:
        return jsonify({'error': 'Missing department, section or year'}), 400
        
    students = User.query.filter_by(role='student', department=department, section=section, year=year).order_by(User.roll_no).all()
    
    # Fetch approved permissions for these students on this date
    student_ids = [s.id for s in students]
    permissions = Permission.query.filter(
        Permission.student_id.in_(student_ids),
        Permission.date == query_date,
        Permission.status == 'approved'
    ).all()
    
    # Map for easy lookup
    od_map = {p.student_id: (p.event.name if p.event else p.custom_event or p.club.name) for p in permissions}
    
    return jsonify([{
        'id': s.id,
        'roll_no': s.roll_no,
        'name': s.get_full_name(),
        'has_pa': s.id in od_map,
        'pa_reason': od_map.get(s.id)
    } for s in students])

@app.route('/<college_slug>/api/timetable/today')
@login_required
def get_today_timetable():
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        return jsonify({'error': 'Timetable service is disabled for this institution.', 'subjects': []}), 403
        
    dept = request.args.get('department')
    year = request.args.get('year')
    sec = request.args.get('section')
    
    if not all([dept, year, sec]):
        return jsonify({'error': 'Missing parameters'}), 400
        
    # User's local time is UTC+5:30.
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    day = ist_now.strftime('%A')
    
    record = TimeTable.query.filter_by(
        college_id=college.id if college else current_user.college_id,
        department=dept, 
        year=year, 
        section=sec, 
        day=day
    ).first()
    if not record:
        return jsonify({'subjects': []})
        
    subjects = [s for s in record.get_periods() if s and s.strip()]
    return jsonify({'subjects': list(set(subjects))}) # Return unique scheduled subjects

@app.route('/<college_slug>/faculty/attendance/save', methods=['POST'])
@login_required
def save_class_attendance():
    if not current_user.is_faculty():
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.json
    if not data or not data.get('department') or not data.get('section') or not data.get('attendance') or not data.get('subject'):
        return jsonify({'error': 'Invalid data format'}), 400
        
    department = data['department']
    section = data['section']
    subject = data['subject']
    year = data.get('year')
    attendance_data = data['attendance'] # {"student_id": "present"|"absent"}
    
    date_str = data.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = datetime.utcnow().date()
    else:
        target_date = datetime.utcnow().date()
    
    # Optional: Delete existing records for this class/faculty today to avoid duplicates
    existing_records = ClassAttendance.query.filter_by(
        faculty_id=current_user.id,
        date=target_date,
        department=department,
        section=section,
        subject=subject
    ).all()
    # If the user selects the same class but year is different, we should probably only delete if year matches
    # but ClassAttendance model doesn't have a year column currently (it has student_id).
    # We should probably add 'year' to ClassAttendance model too for easier reporting.
    for record in existing_records:
        db.session.delete(record)
        
    for student_id_str, status in attendance_data.items():
        try:
            student_id = int(student_id_str)
            student = User.query.get(student_id)
            if student and student.role == 'student' and student.department == department and student.section == section:
                record = ClassAttendance(
                    student_id=student_id,
                    faculty_id=current_user.id,
                    date=target_date,
                    department=department,
                    year=year,
                    section=section,
                    subject=subject,
                    status=status
                )
                db.session.add(record)
        except ValueError:
            continue
            
    db.session.commit()
    return jsonify({'success': True, 'message': 'Attendance saved effectively'})

@app.route('/<college_slug>/faculty/attendance/history')
@login_required
def faculty_attendance_history():
    if not current_user.is_faculty():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Query grouped sessions
    sessions = db.session.query(
        ClassAttendance.date, 
        ClassAttendance.department, 
        ClassAttendance.year, 
        ClassAttendance.section, 
        ClassAttendance.subject,
        db.func.count(ClassAttendance.id).label('total'),
        db.func.sum(db.case((ClassAttendance.status == 'present', 1), else_=0)).label('present')
    ).filter_by(faculty_id=current_user.id).group_by(
        ClassAttendance.date, 
        ClassAttendance.department, 
        ClassAttendance.year, 
        ClassAttendance.section, 
        ClassAttendance.subject
    ).order_by(ClassAttendance.date.desc()).all()
    
    from itertools import groupby
    grouped_sessions = []
    for date, group in groupby(sessions, key=lambda x: x.date):
        grouped_sessions.append({
            'date': date,
            'records': list(group)
        })
    
    return render_template('faculty/attendance_history.html', grouped_sessions=grouped_sessions)

@app.route('/<college_slug>/faculty/attendance/edit')
@login_required
def edit_attendance_view():
    if not current_user.is_faculty():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    date = request.args.get('date')
    dept = request.args.get('dept')
    year = request.args.get('year')
    sec = request.args.get('sec')
    sub = request.args.get('sub')
    
    if not all([date, dept, year, sec, sub]):
        flash('Missing parameters for editing attendance', 'danger')
        return redirect(url_for('faculty_attendance_history'))
        
    return render_template('faculty/edit_attendance.html', 
                          date=date, dept=dept, year=year, sec=sec, sub=sub)

@app.route('/<college_slug>/api/faculty/attendance/load')
@login_required
def load_attendance_data():
    if not current_user.is_faculty():
        return jsonify({'error': 'Unauthorized'}), 403
        
    date_str = request.args.get('date')
    dept = request.args.get('dept')
    year = request.args.get('year')
    sec = request.args.get('sec')
    sub = request.args.get('sub')
    
    if not all([date_str, dept, year, sec, sub]):
        return jsonify({'error': 'Missing parameters'}), 400
        
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
        
    records = ClassAttendance.query.filter_by(
        faculty_id=current_user.id,
        date=date,
        department=dept,
        year=year,
        section=sec,
        subject=sub
    ).all()
    
    attendance_map = {str(r.student_id): r.status for r in records}
    return jsonify({'attendance': attendance_map})

# --- Class Incharge Management ---
@app.route('/<college_slug>/faculty/incharge/timetable')
@login_required
def incharge_timetable():
    if not (current_user.is_faculty() and current_user.is_incharge()):
        flash('Access denied. Only Class Incharges can access this page.', 'danger')
        return redirect(url_for('faculty_dashboard'))
    
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        flash('Timetable service is currently disabled for this institution.', 'warning')
        return redirect(url_for('faculty_dashboard'))
    
    dept = current_user.incharge_department
    sec = current_user.incharge_section
    
    # We need to find the year for this incharge's section. 
    # Usually, the faculty might handle one specific year or it's mapped.
    # Let's assume we can find it from a student in that section or it's a field we should have.
    # For now, let's try to get it from the first student found in that section.
    student = User.query.filter_by(department=dept, section=sec, role='student').first()
    year = student.year if student else 1
    
    timetable_records = TimeTable.query.filter_by(college_id=current_user.college_id, department=dept, year=year, section=sec).all()
    timetable_data = {r.day: r for r in timetable_records}
    
    return render_template('faculty/incharge_timetable.html', 
                           dept=dept, sec=sec, year=year,
                           timetable_data=timetable_data)

@app.route('/<college_slug>/api/incharge/timetable/swap', methods=['POST'])
@login_required
def swap_periods():
    if not (current_user.is_faculty() and current_user.is_incharge()):
        return jsonify({'error': 'Unauthorized'}), 403
        
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        return jsonify({'error': 'Timetable service is disabled for this institution.'}), 403
        
    data = request.json
    day = data.get('day')
    p1_idx = data.get('p1') # 1-7
    p2_idx = data.get('p2') # 1-7
    dept = current_user.incharge_department
    sec = current_user.incharge_section
    
    # Year lookup again
    student = User.query.filter_by(department=dept, section=sec, role='student').first()
    year = student.year if student else 1
    
    record = TimeTable.query.filter_by(
        college_id=college.id if college else current_user.college_id,
        department=dept, 
        year=year, 
        section=sec, 
        day=day
    ).first()
    if not record:
        return jsonify({'error': 'Timetable not found for this day'}), 404
        
    # Swap subjects
    attr1 = f'period_{p1_idx}'
    attr2 = f'period_{p2_idx}'
    
    val1 = getattr(record, attr1)
    val2 = getattr(record, attr2)
    
    setattr(record, attr1, val2)
    setattr(record, attr2, val1)
    
    db.session.commit()
    return jsonify({'success': True, 'message': f'Swapped Period {p1_idx} and Period {p2_idx} successfully!'})

@app.route('/<college_slug>/api/incharge/holiday/declare', methods=['POST'])
@login_required
def declare_holiday():
    if not (current_user.is_faculty() and current_user.is_incharge()):
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.json
    date_str = data.get('date')
    reason = data.get('reason', 'Holiday declared by class incharge')
    
    if not date_str:
        return jsonify({'error': 'Date is required'}), 400
        
    try:
        holiday_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
        
    dept = current_user.incharge_department
    sec = current_user.incharge_section
    student = User.query.filter_by(department=dept, section=sec, role='student').first()
    year = student.year if student else 1
    
    # Check if already exists
    existing = ClassHoliday.query.filter_by(department=dept, year=year, section=sec, date=holiday_date).first()
    if existing:
        return jsonify({'error': 'A holiday is already declared for this date'}), 400
        
    holiday = ClassHoliday(
        department=dept,
        year=year,
        section=sec,
        date=holiday_date,
        reason=reason,
        declared_by=current_user.id
    )
    db.session.add(holiday)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Holiday declared successfully!'})

@app.route('/<college_slug>/api/incharge/holidays')
@login_required
def get_incharge_holidays():
    if not (current_user.is_faculty() and current_user.is_incharge()):
        return jsonify({'error': 'Unauthorized'}), 403
        
    dept = current_user.incharge_department
    sec = current_user.incharge_section
    student = User.query.filter_by(department=dept, section=sec, role='student').first()
    year = student.year if student else 1
    
    holidays = ClassHoliday.query.filter_by(department=dept, year=year, section=sec).order_by(ClassHoliday.date.desc()).all()
    
    return jsonify([{
        'id': h.id,
        'date': h.date.strftime('%Y-%m-%d'),
        'reason': h.reason
    } for h in holidays])

@app.route('/<college_slug>/api/incharge/holiday/<int:holiday_id>', methods=['DELETE'])
@login_required
def delete_holiday(holiday_id):
    if not (current_user.is_faculty() and current_user.is_incharge()):
        return jsonify({'error': 'Unauthorized'}), 403
        
    holiday = ClassHoliday.query.get_or_404(holiday_id)
    
    # Verify ownership/authority
    if holiday.department != current_user.incharge_department or holiday.section != current_user.incharge_section:
        return jsonify({'error': 'Unauthorized'}), 403
        
    db.session.delete(holiday)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Holiday removed.'})

# Student Routes
@app.route('/<college_slug>/student/dashboard')
@login_required
def student_dashboard():
    if not current_user.is_student():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Update event statuses automatically
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    potential_expired = Event.query.filter(Event.status.in_(['upcoming', 'active'])).all()
    changed = False
    for event in potential_expired:
        new_status = event.status
        if event.end_date and now > event.end_date:
            new_status = 'expired'
        elif event.start_date and now >= event.start_date and (not event.end_date or now <= event.end_date):
            new_status = 'active'
        else:
            new_status = 'upcoming'
            
        if event.status != new_status:
            event.status = new_status
            changed = True
    if changed:
        db.session.commit()

    # Show ALL events (Active, Upcoming, and Past) for the dashboard list
    all_events = Event.query.filter_by(college_id=g.current_college.id).order_by(Event.start_date.desc()).limit(20).all()
    
    student_events = []
    user_dept = current_user.department.strip().lower() if current_user.department else ""
    
    for event in all_events:
        allowed = json.loads(event.allowed_departments) if event.allowed_departments else []
        # Case-insensitive, stripped check
        if not allowed or any(d.strip().lower() == user_dept for d in allowed):
            student_events.append(event)
            
    # Only show permissions applied within the last 15 days
    visibility_cutoff = datetime.utcnow() - timedelta(days=15)
    permissions = Permission.query.filter_by(student_id=current_user.id).filter(
        Permission.applied_at >= visibility_cutoff
    ).order_by(Permission.applied_at.desc()).all()
    
    registrations = EventResponse.query.filter_by(student_id=current_user.id).order_by(EventResponse.submitted_at.desc()).all()
    registered_ids = [r.event_id for r in registrations]
    
    # --- Timetable Logic ---
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict):
        features = {}

    today_timetable = None
    timetable_subjects = {}
    
    if features.get('timetable'):
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        day = ist_now.strftime('%A')
        
        timetable_rows = TimeTable.query.filter_by(
            college_id=college.id if college else current_user.college_id,
            department=current_user.department,
            year=current_user.year,
            section=current_user.section
        ).all()
        
        today_timetable = next((row for row in timetable_rows if row.day == day), None)
        
        for row in timetable_rows:
            for p in row.get_periods():
                if p and p.strip() and p.strip().upper() not in ['BREAK', 'LUNCH', 'LUNCH BREAK']:
                    timetable_subjects[p.strip().lower()] = p.strip()
    else:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    
    # --- Attendance Statistics ---
    attendance_records = ClassAttendance.query.filter_by(student_id=current_user.id).all()
    
    overall_stats = {'present': 0, 'total': 0, 'percentage': 0}
    this_week_stats = {'present': 0, 'total': 0, 'percentage': 0}
    subject_stats = {} # { 'Subject Name': {'present': 0, 'total': 0, 'percentage': 0} }
    
    today_date = datetime.utcnow().date()
    start_of_week = today_date - timedelta(days=today_date.weekday())
    today_attendance = []
    today_subject_stats = {}
    
    for record in attendance_records:
        overall_stats['total'] += 1
        if record.status == 'present':
            overall_stats['present'] += 1
            
        if record.date >= start_of_week and record.date <= today_date:
            this_week_stats['total'] += 1
            if record.status == 'present':
                this_week_stats['present'] += 1
            
        if record.subject not in subject_stats:
            subject_stats[record.subject] = {'present': 0, 'total': 0, 'percentage': 0}
        
        subject_stats[record.subject]['total'] += 1
        if record.status == 'present':
            subject_stats[record.subject]['present'] += 1
            
        if record.date == today_date:
            if record.subject not in today_subject_stats:
                today_subject_stats[record.subject] = {'present': 0, 'total': 0, 'percentage': 0}
            today_subject_stats[record.subject]['total'] += 1
            if record.status == 'present':
                today_subject_stats[record.subject]['present'] += 1
                
            category = 'Class'
            sub_name = record.subject.upper()
            if 'LAB' in sub_name or 'WORKSHOP' in sub_name or 'SEMINAR' in sub_name:
                category = 'Others'
                
            today_attendance.append({
                'subject': record.subject,
                'status': record.status,
                'marked_at': record.marked_at,
                'category': category
            })
            
    # Calculate percentages
    if overall_stats['total'] > 0:
        overall_stats['percentage'] = round((overall_stats['present'] / overall_stats['total']) * 100, 1)
        
    if this_week_stats['total'] > 0:
        this_week_stats['percentage'] = round((this_week_stats['present'] / this_week_stats['total']) * 100, 1)
        
    for sub, stats in subject_stats.items():
        if stats['total'] > 0:
            stats['percentage'] = round((stats['present'] / stats['total']) * 100, 1)
            
    for sub, stats in today_subject_stats.items():
        if stats['total'] > 0:
            stats['percentage'] = round((stats['present'] / stats['total']) * 100, 1)
            
    if timetable_subjects:
        new_subject_stats = {}
        for sub, stats in subject_stats.items():
            if sub.strip().lower() in timetable_subjects:
                new_subject_stats[sub] = stats
                
        existing_lower = {k.strip().lower() for k in new_subject_stats.keys()}
        for sub_lower, sub_original in timetable_subjects.items():
            if sub_lower not in existing_lower:
                new_subject_stats[sub_original] = {'present': 0, 'total': 0, 'percentage': 0}
                
        subject_stats = new_subject_stats
        
    from models import ExamResult
    exam_results = ExamResult.query.filter_by(student_id=current_user.id).all()
    total_marks = sum(r.marks for r in exam_results if r.marks)
    avg_marks = round(total_marks / len(exam_results), 1) if exam_results else 0

    # Mock data for UI removed to avoid confusion
    attendance_rank = "Top 18%"
        
    return render_template('student/dashboard.html', 
                          events=student_events[:4],
        permissions=permissions[:5],
        registrations=registrations[:5],
        registered_ids=registered_ids, # Keep this from original
        overall_stats=overall_stats,
        this_week_stats=this_week_stats,
        subject_stats=subject_stats,
        today_subject_stats=today_subject_stats,
        today_attendance=today_attendance,
        today_timetable=today_timetable,
        attendance_rank=attendance_rank,
        ist_now=ist_now,
        avg_marks=avg_marks,
        exam_results=exam_results
    )

@app.route('/<college_slug>/api/student/attendance/history')
@login_required
def get_attendance_history():
    if not current_user.is_student():
        return jsonify({'error': 'Unauthorized'}), 403
    
    date_str = request.args.get('date')
    if not date_str:
        return jsonify([])
        
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format'}), 400
        
    records = ClassAttendance.query.filter_by(
        student_id=current_user.id,
        date=query_date
    ).all()
    
    result = []
    for r in records:
        category = 'Class'
        sub_name = r.subject.upper()
        if 'LAB' in sub_name or 'WORKSHOP' in sub_name or 'SEMINAR' in sub_name:
            category = 'Others'
            
        result.append({
            'subject': r.subject,
            'status': r.status,
            'marked_at': r.marked_at.strftime('%I:%M %p'),
            'category': category
        })
        
    return jsonify(result)

@app.route('/<college_slug>/api/student/attendance_by_date')
@login_required
def get_attendance_by_date():
    if not current_user.is_student():
        return jsonify({'error': 'Unauthorized'}), 403
    
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date is required'}), 400
        
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format'}), 400
        
    attendance_records = ClassAttendance.query.filter_by(
        student_id=current_user.id,
        date=query_date
    ).all()
    
    # Fetch timetable subjects to filter out non-timetable subjects
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    timetable_subjects = set()
    if isinstance(features, dict) and features.get('timetable'):
        timetable_rows = TimeTable.query.filter_by(
            college_id=college.id if college else current_user.college_id,
            department=current_user.department,
            year=current_user.year,
            section=current_user.section
        ).all()
        for row in timetable_rows:
            for p in row.get_periods():
                if p and p.strip() and p.strip().upper() not in ['BREAK', 'LUNCH', 'LUNCH BREAK']:
                    timetable_subjects.add(p.strip().lower())
    
    date_subject_stats = {}
    for record in attendance_records:
        # Only include subjects present in the current timetable
        if timetable_subjects and record.subject.strip().lower() not in timetable_subjects:
            continue
            
        if record.subject not in date_subject_stats:
            date_subject_stats[record.subject] = {'present': 0, 'total': 0, 'percentage': 0}
        
        date_subject_stats[record.subject]['total'] += 1
        if record.status == 'present':
            date_subject_stats[record.subject]['present'] += 1
            
    for sub, stats in date_subject_stats.items():
        if stats['total'] > 0:
            stats['percentage'] = round((stats['present'] / stats['total']) * 100, 1)
            
    return jsonify(date_subject_stats)

@app.route('/<college_slug>/student/performance', methods=['GET', 'POST'])
@login_required
def student_performance():
    if not current_user.is_student():
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        perf_type = request.form.get('type')
        title = request.form.get('title')
        description = request.form.get('description')
        certificate_id = request.form.get('certificate_id')
        
        proof_filename = None
        if 'proof' in request.files:
            file = request.files['proof']
            if file and file.filename != '':
                filename = secure_filename(f"{current_user.id}_{int(datetime.now().timestamp())}_{file.filename}")
                upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'performance')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                proof_filename = filename
                
        perf = StudentPerformance(
            student_id=current_user.id,
            college_id=current_user.college_id,
            type=perf_type,
            title=title,
            description=description,
            certificate_id=certificate_id,
            proof_filename=proof_filename
        )
        db.session.add(perf)
        db.session.commit()
        flash('Performance record added successfully!', 'success')
        return redirect(url_for('student_performance'))
        
    records = StudentPerformance.query.filter_by(student_id=current_user.id).order_by(StudentPerformance.created_at.desc()).all()
    skills = [r for r in records if r.type == 'skill']
    certificates = [r for r in records if r.type == 'certificate']
    internships = [r for r in records if r.type == 'internship']
    achievements = [r for r in records if r.type == 'achievement']
    
    return render_template('student/performance.html', 
                          skills=skills, 
                          certificates=certificates, 
                          internships=internships, 
                          achievements=achievements)

@app.route('/<college_slug>/analytics/performance')
@login_required
def performance_analytics():
    if not (current_user.role in ['admin', 'superadmin'] or (current_user.is_faculty() and current_user.is_incharge())):
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
        
    search_roll = request.args.get('roll_no', '').strip().upper()
    
    # Base query for students in their purview
    students_query = User.query.filter_by(college_id=current_user.college_id, role='student')
    
    if current_user.is_faculty() and current_user.is_incharge():
        students_query = students_query.filter_by(
            department=current_user.incharge_department,
            section=current_user.incharge_section
        )
        
    student = None
    records = []
    
    if search_roll:
        student = students_query.filter_by(roll_no=search_roll).first()
        if student:
            records = StudentPerformance.query.filter_by(student_id=student.id).order_by(StudentPerformance.created_at.desc()).all()
        else:
            flash(f'Student with Roll Number {search_roll} not found in your purview.', 'warning')
            
    # Fetch recent updates grouped by student
    from sqlalchemy import func
    
    subq = db.session.query(
        StudentPerformance.student_id,
        func.max(StudentPerformance.created_at).label('last_updated'),
        func.count(StudentPerformance.id).label('total_updates')
    ).group_by(StudentPerformance.student_id).subquery()
    
    recent_updates = db.session.query(User, subq.c.last_updated, subq.c.total_updates).join(
        subq, User.id == subq.c.student_id
    ).filter(
        User.college_id == current_user.college_id,
        User.role == 'student'
    )
    
    if current_user.is_faculty() and current_user.is_incharge():
        recent_updates = recent_updates.filter(
            User.department == current_user.incharge_department,
            User.section == current_user.incharge_section
        )
        
    recent_updates = recent_updates.order_by(subq.c.last_updated.desc()).limit(20).all()
    
    # Process to handle string parsing (SQLite func.max behavior) and IST conversion
    processed_updates = []
    for row in recent_updates:
        stu, last_upd, total_upd = row
        if isinstance(last_upd, str):
            try:
                # SQLite datetime strings format: 'YYYY-MM-DD HH:MM:SS.mmmmmm'
                last_upd = datetime.strptime(last_upd.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        
        # Convert UTC to IST (+5:30)
        if isinstance(last_upd, datetime):
            last_upd = last_upd + timedelta(hours=5, minutes=30)
            
        processed_updates.append((stu, last_upd, total_upd))
    
    return render_template('analytics/performance.html', 
                          student=student, 
                          records=records, 
                          recent_updates=processed_updates,
                          search_roll=search_roll)

@app.route('/<college_slug>/api/student/timetable/full')
@login_required
def get_full_timetable():
    if not current_user.is_student():
        return jsonify({'error': 'Unauthorized'}), 403
        
    college = g.current_college or current_user.college
    features = college.get_features if college else {}
    if not isinstance(features, dict) or not features.get('timetable'):
        return jsonify({'error': 'Timetable service is disabled for your institution.', 'times': [], 'schedule': []}), 403
        
    timetable_rows = TimeTable.query.filter_by(
        college_id=college.id if college else current_user.college_id,
        department=current_user.department,
        year=current_user.year,
        section=current_user.section
    ).all()
    
    # Sort days conventionally
    day_order = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6, 'Sunday': 7}
    timetable_rows.sort(key=lambda x: day_order.get(x.day, 99))
    
    # Get standard period times from the first available row, or defaults
    times = []
    if timetable_rows:
        first = timetable_rows[0]
        times = [
            first.period_1_time or '09:30 - 10:20',
            first.period_2_time or '10:20 - 11:10',
            first.period_3_time or '11:10 - 12:00',
            first.period_4_time or '01:00 - 01:50',
            first.period_5_time or '01:50 - 02:40',
            first.period_6_time or '02:40 - 03:30',
            first.period_7_time or '03:30 - 04:20'
        ]
    else:
        times = [
            '09:30 - 10:20', '10:20 - 11:10', '11:10 - 12:00',
            '01:00 - 01:50', '01:50 - 02:40', '02:40 - 03:30', '03:30 - 04:20'
        ]
        
    schedule = []
    for row in timetable_rows:
        schedule.append({
            'day': row.day,
            'periods': row.get_periods()
        })
        
    return jsonify({
        'times': times,
        'schedule': schedule,
        'department': current_user.department,
        'year': current_user.year,
        'section': current_user.section
    })

@app.route('/<college_slug>/api/student/timeline/history')
@login_required
def get_timeline_history():
    if not current_user.is_student():
        return jsonify({'error': 'Unauthorized'}), 403
    
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Date is required'}), 400
        
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date format'}), 400
        
    day_of_week = query_date.strftime('%A')
    
    # 1. Check for Holiday
    holiday = ClassHoliday.query.filter_by(
        department=current_user.department,
        year=current_user.year,
        section=current_user.section,
        date=query_date
    ).first()

    if holiday:
        return jsonify({
            'date': query_date.strftime('%A, %d %B %Y'),
            'is_holiday': True,
            'holiday_reason': holiday.reason,
            'timeline': []
        })

    # 2. Fetch Timetable for this day of week
    timetable = TimeTable.query.filter_by(
        department=current_user.department,
        year=current_user.year,
        section=current_user.section,
        day=day_of_week
    ).first()
    
    # 3. Fetch Attendance for this specific date
    attendance_records = ClassAttendance.query.filter_by(
        student_id=current_user.id,
        date=query_date
    ).all()
    
    # Map attendance by subject for easy lookup
    attendance_map = {}
    for r in attendance_records:
        attendance_map[r.subject.strip().lower()] = r.status
        
    # Helper for formatting times
    def format_t(t_str, default):
        target = t_str if t_str else default
        parts = target.split(' - ')
        if len(parts) == 2:
            return {
                'display': format_time_range(target),
                'start': parts[0],
                'end': parts[1]
            }
        return {'display': target, 'start': '00:00', 'end': '00:00'}

    periods = []
    
    # Structure the periods exactly like the frontend Jinja loop
    periods.append({
        'num': 'P1', 
        'sub': timetable.period_1 if timetable else None,
        'time': format_t(timetable.period_1_time if timetable else None, '09:30 AM - 10:20 AM')
    })
    periods.append({
        'num': 'P2', 
        'sub': timetable.period_2 if timetable else None,
        'time': format_t(timetable.period_2_time if timetable else None, '10:20 AM - 11:10 AM')
    })
    periods.append({
        'num': 'P3', 
        'sub': timetable.period_3 if timetable else None,
        'time': format_t(timetable.period_3_time if timetable else None, '11:10 AM - 12:00 PM')
    })
    periods.append({
        'num': '--', 
        'sub': 'BREAK',
        'time': {'display': '12:00 PM - 01:00 PM', 'start': '12:00', 'end': '13:00'}
    })
    periods.append({
        'num': 'P4', 
        'sub': timetable.period_4 if timetable else None,
        'time': format_t(timetable.period_4_time if timetable else None, '01:00 PM - 01:50 PM')
    })
    periods.append({
        'num': 'P5', 
        'sub': timetable.period_5 if timetable else None,
        'time': format_t(timetable.period_5_time if timetable else None, '01:50 PM - 02:40 PM')
    })
    periods.append({
        'num': 'P6', 
        'sub': timetable.period_6 if timetable else None,
        'time': format_t(timetable.period_6_time if timetable else None, '02:40 PM - 03:30 PM')
    })
    periods.append({
        'num': 'P7', 
        'sub': timetable.period_7 if timetable else None,
        'time': format_t(timetable.period_7_time if timetable else None, '03:30 PM - 04:20 PM')
    })
    
    # Inject attendance status into periods
    timeline_data = []
    for p in periods:
        status = None
        if p['sub'] and p['sub'] != 'BREAK':
            sub_key = p['sub'].strip().lower()
            status = attendance_map.get(sub_key)
            
        timeline_data.append({
            'num': p['num'],
            'subject': p['sub'],
            'status': status,
            'timeDisplay': p['time']['display'],
            'start': p['time']['start'],
            'end': p['time']['end']
        })
        
    return jsonify({
        'date': query_date.strftime('%A, %d %B %Y'),
        'has_classes': timetable is not None,
        'is_sunday': day_of_week == 'Sunday',
        'is_holiday': False,
        'timeline': timeline_data
    })

@app.route('/<college_slug>/api/student/timetable/week')
@login_required
def get_student_week_timetable():
    if not current_user.is_student():
        return jsonify({'error': 'Unauthorized'}), 403
    
    timetable_records = TimeTable.query.filter_by(college_id=current_user.college_id, 
        department=current_user.department,
        year=current_user.year,
        section=current_user.section
    ).all()
    
    # Return days that have a timetable entry
    return jsonify({r.day: True for r in timetable_records})


@app.route('/<college_slug>/student/apply-permission', methods=['GET', 'POST'])
@login_required
def apply_permission():
    if not current_user.is_student():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        date = request.form.get('date')
        club_id = request.form.get('club_id')
        event_id = request.form.get('event_id')
        custom_event = request.form.get('custom_event')
        description = request.form.get('description')
        
        # Handle file upload
        proof_file = request.files.get('proof_file')
        proof_filename = None
        
        if proof_file and allowed_file(proof_file.filename):
            filename = secure_filename(proof_file.filename)
            proof_filename = f"proof_{current_user.roll_no}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
            proof_file.save(os.path.join(app.config['UPLOAD_FOLDER'], proof_filename))
        
        permission = Permission(
            student_id=current_user.id,
            date=datetime.strptime(date, '%Y-%m-%d').date(),
            club_id=club_id,
            event_id=event_id if event_id else None,
            custom_event=custom_event if not event_id else None,
            description=description,
            proof_filename=proof_filename
        )
        
        db.session.add(permission)
        db.session.commit()
        
        flash('Permission application submitted successfully', 'success')
        return redirect(url_for('student_dashboard'))
    
    # Pre-sync event statuses
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    potential_events = Event.query.filter(Event.status.in_(['active', 'upcoming'])).all()
    changed = False
    for e in potential_events:
        new_status = e.status
        if e.end_date and now > e.end_date: new_status = 'expired'
        elif e.start_date and now >= e.start_date and (not e.end_date or now <= e.end_date): new_status = 'active'
        else: new_status = 'upcoming'
        
        if e.status != new_status:
            e.status = new_status
            changed = True
    if changed:
        db.session.commit()

    # Only show clubs that have active or upcoming events for THIS student's department
    all_active_event_clubs = Club.query.join(Event).filter(Event.status.in_(['active', 'upcoming'])).all()
    
    eligible_clubs = []
    for club in all_active_event_clubs:
        # Check if at least one event in this club is eligible for the student
        is_eligible = False
        for event in club.events:
            if event.status not in ['active', 'upcoming']:
                continue
            try:
                allowed = json.loads(event.allowed_departments) if event.allowed_departments else []
            except (ValueError, TypeError):
                allowed = []
            
            if not allowed or current_user.department in allowed:
                is_eligible = True
                break
        
        if is_eligible and club not in eligible_clubs:
            eligible_clubs.append(club)
            
    return render_template('student/apply_permission.html', clubs=eligible_clubs)

@app.route('/<college_slug>/student/permissions')
@login_required
def student_permissions():
    if not current_user.is_student():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    visibility_cutoff = datetime.utcnow() - timedelta(days=15)
    permissions = Permission.query.filter_by(student_id=current_user.id).filter(
        Permission.applied_at >= visibility_cutoff
    ).order_by(Permission.applied_at.desc()).all()
    return render_template('student/permissions.html', permissions=permissions)

@app.route('/<college_slug>/student/permission/<int:permission_id>')
@login_required
def student_view_permission(permission_id):
    if not current_user.is_student():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permission = Permission.query.get_or_404(permission_id)
    # Ensure student can only view their own permissions
    if permission.student_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('student_dashboard'))
    
    return render_template('student/permission_details.html', permission=permission)

@app.route('/<college_slug>/student/permission/withdraw/<int:permission_id>')
@login_required
def withdraw_permission(permission_id):
    if not current_user.is_student():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    permission = Permission.query.get_or_404(permission_id)
    
    # Ensure student can only withdraw their own permissions
    if permission.student_id != current_user.id:
        flash('Access denied', 'danger')
        return redirect(url_for('student_dashboard'))
    
    # Optional: only allow withdrawing if it's not already processed?
    # For now, let's allow withdrawing anytime if it's the student's own permission.
    
    db.session.delete(permission)
    db.session.commit()
    
    flash('Permission request withdrawn successfully.', 'success')
    return redirect(url_for('student_dashboard'))

# API Routes
@app.route('/<college_slug>/api/events/<int:club_id>')
@login_required
def get_events(club_id):
    # Update event statuses automatically for this club
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    all_club_events = Event.query.filter_by(club_id=club_id).all()
    for event in all_club_events:
        if event.end_date and now > event.end_date:
            event.status = 'expired'
        elif event.start_date and now >= event.start_date and (not event.end_date or now <= event.end_date):
            event.status = 'active'
        else:
            event.status = 'upcoming'
    db.session.commit()

    # Filter by club and status (only active/upcoming)
    query = Event.query.filter_by(club_id=club_id).filter(Event.status.in_(['active', 'upcoming']))
    events = query.all()
    
    # Further filter by department if the current user is a student
    if current_user.is_student():
        filtered_events = []
        for event in events:
            # Handle possible JSON parsing issues
            try:
                allowed = json.loads(event.allowed_departments) if event.allowed_departments else []
            except (ValueError, TypeError):
                allowed = []
                
            if not allowed or current_user.department in allowed:
                filtered_events.append(event)
        events = filtered_events
        
    return jsonify([{'id': event.id, 'name': event.name} for event in events])

@app.route('/<college_slug>/download-template')
@login_required
def download_template():
    # Fetch actual departments from DB for the template
    depts = Department.query.order_by(Department.name).all()
    dept_list = [d.name for d in depts] if depts else ['CSE', 'ECE', 'EEE', 'MECH', 'CIVIL']
    
    # Create sample template data
    import io
    data = {
        'roll_no': ['24N81A6261', '24N81A6262', '24N81A6263'],
        'email': ['student1@college.edu', 'student2@college.edu', 'student3@college.edu'],
        'first_name': ['John', 'Jane', 'Mike'],
        'last_name': ['Doe', 'Smith', 'Johnson'],
        'year': [1, 2, 3],
        'section': ['A', 'B', 'A'],
        'department': [dept_list[0], dept_list[0], dept_list[min(1, len(dept_list)-1)]]
    }
    df = pd.DataFrame(data)
    
    # Create in-memory file
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Students', index=False)
        output.seek(0)
        return send_file(output, download_name='student_template.xlsx', as_attachment=True)
    except Exception as e:
        flash(f'Error generating template: {str(e)}', 'danger')
        return redirect(url_for('manage_students'))

@app.route('/<college_slug>/admin/ledger')
@login_required
def admin_ledger():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get all clubs
    clubs = Club.query.filter_by(college_id=current_user.college_id).all()
    
    # Get events that have collected funds but not fully settled
    from sqlalchemy import and_
    events_with_funds = Event.query.filter(Event.total_collected > Event.total_settled).all()
    
    # Filters
    club_filter = request.args.get('club_id', type=int)
    cat_filter = request.args.get('category')
    
    query = FinanceTransaction.query
    if club_filter:
        query = query.filter_by(club_id=club_filter)
    if cat_filter:
        query = query.filter_by(category=cat_filter)
        
    transactions = query.order_by(FinanceTransaction.created_at.desc()).limit(200).all()
    
    return render_template('admin/ledger.html', 
                          clubs=clubs, 
                          events_with_funds=events_with_funds, 
                          transactions=transactions,
                          club_filter=club_filter,
                          cat_filter=cat_filter)

@app.route('/<college_slug>/admin/settle', methods=['POST'])
@login_required
def admin_settle():
    if not current_user.is_admin():
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    club_id = request.form.get('club_id', type=int)
    event_id = request.form.get('event_id', type=int)
    amount = float(request.form.get('amount', 0))
    ref = request.form.get('reference', '') or 'Manual Settlement'
    
    if amount <= 0:
        flash('Invalid amount', 'danger')
        return redirect(url_for('admin_ledger'))
    
    club = Club.query.get_or_404(club_id)
    event = Event.query.get(event_id) if event_id else None
    
    # Update balances
    if event:
        # Settle specific event
        if amount > (event.total_collected - event.total_settled):
            flash('Amount exceeds event balance', 'danger')
            return redirect(url_for('admin_ledger'))
        event.total_settled += amount
    else:
        # Settle general club balance
        if amount > club.pending_settlement:
            flash('Amount exceeds club pending balance', 'danger')
            return redirect(url_for('admin_ledger'))
        club.pending_settlement -= amount
    
    club.balance += amount
    
    # Record transaction
    transaction = FinanceTransaction(
        club_id=club.id,
        event_id=event.id if event else None,
        amount=amount,
        type='debit',
        category='settlement',
        description=f"Settlement to club. Ref: {ref}" + (f" (Event: {event.name})" if event else "")
    )
    db.session.add(transaction)
    db.session.commit()
    
    flash(f'Settlement of ₹{amount} recorded for {club.name}', 'success')
    return redirect(url_for('admin_ledger'))

@app.route('/<college_slug>/admin/ledger/export')
@login_required
def admin_export_ledger():
    if not current_user.is_admin(): return "Unauthorized", 403
    
    import csv
    from io import StringIO
    from flask import Response
    
    txs = FinanceTransaction.query.order_by(FinanceTransaction.created_at.desc()).all()
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['Date', 'Club', 'Event', 'Amount', 'Type', 'Category', 'Description'])
        yield data.getvalue()
        data.seek(0); data.truncate(0)
        
        for tx in txs:
            writer.writerow([
                tx.created_at.strftime('%Y-%m-%d %H:%M'),
                tx.club.name if tx.club else 'N/A',
                tx.event.name if tx.event else 'General',
                tx.amount,
                tx.type,
                tx.category,
                tx.description
            ])
            yield data.getvalue()
            data.seek(0); data.truncate(0)

    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=financial_ledger.csv"})

# --- PRINCIPAL & SECRETARY DASHBOARDS ---

@app.route('/<college_slug>/principal/dashboard')
@login_required
def principal_dashboard():
    if current_user.role != 'principal':
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    
    college_id = g.current_college.id
    stats = {
        'total_students': User.query.filter_by(college_id=college_id, role='student').count(),
        'total_faculty': User.query.filter_by(college_id=college_id, role='faculty').count(),
        'total_events': Event.query.filter_by(college_id=college_id).count(),
        'total_departments': Department.query.filter_by(college_id=college_id).count()
    }
    return render_template('principal/dashboard.html', stats=stats)

@app.route('/<college_slug>/secretary/dashboard')
@login_required
def secretary_dashboard():
    if current_user.role != 'secretary':
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    
    college_id = g.current_college.id
    finance_stats = {
        'total_revenue': db.session.query(db.func.sum(FinanceTransaction.amount)).filter_by(college_id=college_id, type='credit').scalar() or 0,
        'total_expense': db.session.query(db.func.sum(FinanceTransaction.amount)).filter_by(college_id=college_id, type='debit').scalar() or 0,
    }
    return render_template('secretary/dashboard.html', stats=finance_stats)

# --- EXAM BRANCH MODULE ---

from models import Exam, ExamFeePayment, ExamResult

@app.route('/<college_slug>/exams/dashboard')
@login_required
def exam_dashboard():
    if current_user.role not in ['exam_admin', 'admin', 'principal']:
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))
    
    exams = Exam.query.filter_by(college_id=g.current_college.id).order_by(Exam.date.desc()).all()
    return render_template('exam/dashboard.html', exams=exams)

@app.route('/<college_slug>/exams/create', methods=['GET', 'POST'])
@login_required
def create_exam():
    if current_user.role not in ['exam_admin', 'admin']:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        exam = Exam(
            college_id=g.current_college.id,
            name=request.form.get('name'),
            type=request.form.get('type'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%d').date(),
            fee=float(request.form.get('fee', 0)),
            is_supplementary=request.form.get('is_supplementary') == 'on'
        )
        db.session.add(exam)
        db.session.commit()
        flash('Exam created successfully', 'success')
        return redirect(url_for('exam_dashboard'))
        
    return render_template('exam/create.html')

@app.route('/<college_slug>/exams/<int:exam_id>/results/upload', methods=['POST'])
@login_required
def upload_results(exam_id):
    if current_user.role not in ['exam_admin', 'admin']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    file = request.files.get('file')
    if not file or not file.filename.endswith(('.xlsx', '.csv')):
        return jsonify({'success': False, 'message': 'Invalid file format'}), 400
        
    try:
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)
            
        # Expected columns: roll_no, subject, marks, grade, status
        results_added = 0
        for _, row in df.iterrows():
            student = User.query.filter_by(roll_no=str(row['roll_no']).strip().upper(), college_id=g.current_college.id).first()
            if student:
                res = ExamResult(
                    college_id=g.current_college.id,
                    exam_id=exam_id,
                    student_id=student.id,
                    subject=row['subject'],
                    marks=row.get('marks', 0),
                    grade=row.get('grade', 'F'),
                    status=row.get('status', 'fail')
                )
                db.session.add(res)
                results_added += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Uploaded {results_added} results.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/<college_slug>/exams/<int:exam_id>/results/manual', methods=['POST'])
@login_required
def manual_result(exam_id):
    if current_user.role not in ['exam_admin', 'admin']:
        return redirect(url_for('index'))
    
    roll_no = request.form.get('roll_no').strip().upper()
    student = User.query.filter_by(roll_no=roll_no, college_id=g.current_college.id).first()
    
    if student:
        res = ExamResult(
            college_id=g.current_college.id,
            exam_id=exam_id,
            student_id=student.id,
            subject=request.form.get('subject'),
            marks=float(request.form.get('marks', 0)),
            grade=request.form.get('grade'),
            status=request.form.get('status', 'pass')
        )
        db.session.add(res)
        db.session.commit()
        flash('Result added successfully', 'success')
    else:
        flash(f'Student with roll number {roll_no} not found', 'danger')
        
    return redirect(url_for('exam_dashboard'))

if __name__ == '__main__':
    with app.app_context():
        # db.create_all() # Schema already migrated
        pass
    app.run(debug=True, host='0.0.0.0')