from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

db = SQLAlchemy()

class College(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    features = db.Column(db.Text, default='{"attendance": true, "clubs": true, "permissions": true, "exams": true}') # JSON string
    branding_logo = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='college', lazy=True)
    departments = db.relationship('Department', backref='college', lazy=True)
    clubs = db.relationship('Club', backref='college', lazy=True)
    exams = db.relationship('Exam', backref='college', lazy=True)

    @property
    def admin(self):
        from models import User
        return User.query.filter_by(college_id=self.id, role='admin').first()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), nullable=False)  # admin, hod, faculty, student, principal, secretary, exam_admin
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=True) # Nullable for superadmin
    is_superadmin = db.Column(db.Boolean, default=False)
    department = db.Column(db.String(100))
    handling_departments = db.Column(db.Text, default='') # Comma separated extra departments
    subjects = db.Column(db.Text, default='') # Comma separated subjects taught
    year = db.Column(db.Integer) # 1, 2, 3, 4
    section = db.Column(db.String(10))
    phone = db.Column(db.String(15))
    is_verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)
    is_blocked = db.Column(db.Boolean, default=False)
    
    # Class Incharge Fields
    incharge_department = db.Column(db.String(50)) # e.g., 'CSE'
    incharge_section = db.Column(db.String(10))    # e.g., 'A'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships - specify foreign keys explicitly
    permissions = db.relationship('Permission', backref='student_ref', lazy=True, foreign_keys='Permission.student_id', cascade='all, delete-orphan')
    approved_permissions = db.relationship('Permission', backref='approver_ref', lazy=True, foreign_keys='Permission.approved_by')
    
    # Cascade relationships to prevent IntegrityError on user deletion
    event_responses_rel = db.relationship('EventResponse', backref='student_rel', lazy=True, cascade='all, delete-orphan')
    team_memberships_rel = db.relationship('TeamMember', backref='user_rel', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def validate_roll_no(self):
        if not self.roll_no:
            return False
        pattern = r'^\d{2}[A-Z]\d{2}[A-Z]\d{4}$'
        return re.match(pattern, self.roll_no) is not None
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_hod(self):
        return self.role == 'hod'
    
    def is_faculty(self):
        return self.role in ['faculty', 'hod']

    def is_incharge(self):
        return self.role == 'faculty' and self.incharge_department and self.incharge_section
    
    def is_student(self):
        return self.role == 'student'

    def is_principal(self):
        return self.role == 'principal'

    def is_secretary(self):
        return self.role == 'secretary'

    def is_exam_admin(self):
        return self.role == 'exam_admin'
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Department {self.name}>'

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(255), nullable=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SystemConfig {self.key}: {self.value}>'

class Club(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    description = db.Column(db.Text)
    coordinator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # New Fields for Club Portal
    club_login_id = db.Column(db.String(50), unique=True, nullable=True)
    password_hash = db.Column(db.String(256))
    is_active = db.Column(db.Boolean, default=True)
    balance = db.Column(db.Float, default=0.0)
    pending_settlement = db.Column(db.Float, default=0.0)
    
    coordinator = db.relationship('User', backref='clubs_coordinated')
    events = db.relationship('Event', backref='club', lazy=True)
    members = db.relationship('ClubMember', backref='club', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ClubMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # president, treasurer, coordinator
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='club_memberships')

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False) # Legacy field
    
    # New Fields
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    registration_deadline = db.Column(db.DateTime, nullable=True)
    venue = db.Column(db.String(100))
    status = db.Column(db.String(20), default='upcoming') # upcoming, active, expired
    allowed_departments = db.Column(db.Text) # JSON string of dept names
    participation_type = db.Column(db.String(20), default='solo') # solo, team, both
    team_size_min = db.Column(db.Integer, default=1)
    team_size_max = db.Column(db.Integer, default=1)
    max_registrations = db.Column(db.Integer, default=0) # 0 for unlimited
    is_paid = db.Column(db.Boolean, default=False)
    amount = db.Column(db.Float, default=0.0)
    payment_model = db.Column(db.String(20), default='individual') # individual, leader
    total_collected = db.Column(db.Float, default=0.0)
    total_settled = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    form = db.relationship('EventForm', backref='event', uselist=False)

    @property
    def is_registration_open(self):
        from datetime import datetime, timedelta
        # Use UTC+5:30 to match user's local time (as seen in metadata)
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        if self.status == 'expired':
            return False
        if self.registration_deadline and now > self.registration_deadline:
            return False
        return True

class EventForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    schema_json = db.Column(db.Text, nullable=False) # JSON structure of custom fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EventResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    response_json = db.Column(db.Text, nullable=False) # JSON data of answers
    ticket_id = db.Column(db.String(50), unique=True)
    qr_code_data = db.Column(db.Text) # Base64 or path
    payment_status = db.Column(db.String(20), default='free') # free, pending, completed, failed
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('User', backref=db.backref('event_responses', overlaps="student_rel,event_responses_rel"), overlaps="event_responses_rel,student_rel")
    event = db.relationship('Event', backref='responses')
    
    # Cascade delete attendance when response is deleted
    attendance_records_rel = db.relationship('Attendance', backref='response_rel', lazy=True, cascade='all, delete-orphan')

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team_name = db.Column(db.String(100))
    team_id_code = db.Column(db.String(10), unique=True) # For others to join
    declared_size = db.Column(db.Integer, default=1)
    is_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    leader = db.relationship('User', backref='teams_led')
    members = db.relationship('TeamMember', backref='team', lazy=True)

class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='member') # leader, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('team_memberships', overlaps="user_rel,team_memberships_rel"), overlaps="team_memberships_rel,user_rel")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('event_response.id'), nullable=False)
    session_type = db.Column(db.String(50)) # Morning, Afternoon, etc.
    scanned_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    response = db.relationship('EventResponse', backref=db.backref('attendance_records', overlaps="response_rel,attendance_records_rel"), overlaps="attendance_records_rel,response_rel")

class ClassAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    subject = db.Column(db.String(150), nullable=False, server_default='General')
    department = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    year = db.Column(db.Integer, nullable=False, server_default='1')
    status = db.Column(db.String(20), default='present') # present, absent
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('User', foreign_keys=[student_id], backref=db.backref('class_attendance_records', lazy='dynamic', cascade='all, delete-orphan'))
    faculty = db.relationship('User', foreign_keys=[faculty_id])



class Permission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    custom_event = db.Column(db.String(200))
    description = db.Column(db.Text, nullable=False)
    proof_filename = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Explicit relationships with foreign keys
    club = db.relationship('Club', backref='permissions')
    event = db.relationship('Event', backref='permissions')
    
    # Properties to access student and approver with clear names
    @property
    def student(self):
        return User.query.get(self.student_id)
    
    @property
    def approver(self):
        return User.query.get(self.approved_by) if self.approved_by else None

class TimeTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(10), nullable=False)
    day = db.Column(db.String(15), nullable=False) # Monday, Tuesday, etc.
    
    # Periods 1-7 (Subject names)
    period_1 = db.Column(db.String(150))
    period_1_time = db.Column(db.String(50), server_default='09:30 - 10:20')
    period_2 = db.Column(db.String(150))
    period_2_time = db.Column(db.String(50), server_default='10:20 - 11:10')
    period_3 = db.Column(db.String(150))
    period_3_time = db.Column(db.String(50), server_default='11:10 - 12:00')
    period_4 = db.Column(db.String(150)) # Lunch break usually after 3 or 4
    period_4_time = db.Column(db.String(50), server_default='01:00 - 01:50')
    period_5 = db.Column(db.String(150))
    period_5_time = db.Column(db.String(50), server_default='01:50 - 02:40')
    period_6 = db.Column(db.String(150))
    period_6_time = db.Column(db.String(50), server_default='02:40 - 03:30')
    period_7 = db.Column(db.String(150))
    period_7_time = db.Column(db.String(50), server_default='03:30 - 04:20')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TimeTable {self.day} - {self.department} {self.year}-{self.section}>'

    def get_periods(self):
        return [self.period_1, self.period_2, self.period_3, self.period_4, self.period_5, self.period_6, self.period_7]

class ClassHoliday(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    college_id  = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    department  = db.Column(db.String(100), nullable=False)
    year        = db.Column(db.Integer, nullable=False)
    section     = db.Column(db.String(10), nullable=False)
    date        = db.Column(db.Date, nullable=False)
    reason      = db.Column(db.String(200))
    declared_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class FinanceTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False) # credit or debit
    category = db.Column(db.String(50)) # e.g., registration_fee, settlement
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    club = db.relationship('Club', backref='transactions')
    event = db.relationship('Event', backref='transactions')

# --- Exam Branch Models ---
class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), default='internal') # internal, external
    date = db.Column(db.Date, nullable=False)
    fee = db.Column(db.Float, default=0.0)
    is_supplementary = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='upcoming') # upcoming, active, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    payments = db.relationship('ExamFeePayment', backref='exam', lazy=True)
    results = db.relationship('ExamResult', backref='exam', lazy=True)

class ExamFeePayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, paid, failed
    razorpay_order_id = db.Column(db.String(100))
    razorpay_payment_id = db.Column(db.String(100))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    college_id = db.Column(db.Integer, db.ForeignKey('college.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    marks = db.Column(db.Float)
    grade = db.Column(db.String(10))
    status = db.Column(db.String(20), default='pass') # pass, fail
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
