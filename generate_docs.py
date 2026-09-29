import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def add_heading(doc, text, level=1):
    heading = doc.add_heading(text, level=level)
    run = heading.runs[0]
    run.font.name = 'Arial'
    if level == 1:
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0x2E, 0x5C, 0x8A)
    elif level == 2:
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0x3B, 0x73, 0xAF)
    return heading

def add_paragraph(doc, text, bold=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(11)
    run.bold = bold
    return p

def add_bullet(doc, text):
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.name = 'Calibri'
    run.font.size = Pt(11)
    return p

# Create a new Document
doc = Document()

# Add Title
title = doc.add_heading('GenZCampus Developer Documentation', 0)
title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

doc.add_paragraph('Version 4.0 | Generated Documentation').alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
doc.add_page_break()

# 1. Project Overview
add_heading(doc, '1. Project Overview', 1)

add_heading(doc, 'What is GenZCampus?', 2)
add_paragraph(doc, 'GenZCampus is a comprehensive SaaS-based College Management System designed to streamline academic, administrative, and extracurricular activities for educational institutions.')

add_heading(doc, 'Why was it developed?', 2)
add_paragraph(doc, 'It was developed to replace fragmented systems (like separate applications for attendance, club events, permissions, and exams) with a unified, tenant-isolated platform where everything is interconnected.')

add_heading(doc, 'What problem does it solve?', 2)
add_paragraph(doc, 'It solves the problem of data silos in colleges, automates manual processes (like leave approvals and event registrations), providing a single source of truth for students, faculties, and administrators. By leveraging tenant isolation, it allows multiple colleges to operate independently on the same infrastructure securely.')

# 2. Technology Stack
add_heading(doc, '2. Technology Stack', 1)

table = doc.add_table(rows=1, cols=2)
table.style = 'Table Grid'
hdr_cells = table.rows[0].cells
hdr_cells[0].text = 'Component'
hdr_cells[1].text = 'Technology'

stack_items = [
    ('Frontend', 'HTML5, CSS3, JavaScript (Vanilla), Jinja2 Templates'),
    ('Backend', 'Python (Flask Framework 2.3.3)'),
    ('Database', 'PostgreSQL (Supabase) via SQLAlchemy ORM'),
    ('Authentication', 'Flask-Login (Session-based, Role-based access control)'),
    ('Hosting', 'Gunicorn, WSGI (Configurable for Cloud deployment)'),
    ('Payment Gateway', 'Razorpay API')
]

for component, tech in stack_items:
    row_cells = table.add_row().cells
    row_cells[0].text = component
    row_cells[1].text = tech

doc.add_paragraph('\n')

# 3. Project Structure
add_heading(doc, '3. Project Structure', 1)
add_paragraph(doc, 'The project follows a standard Flask application structure with Blueprints for modularity:')

structure = [
    ('app.py', 'The global entry point of the application. It initializes the Flask app, database, extensions, sets up global/super-admin routes, and defines tenant isolation logic.'),
    ('models.py', 'Defines the SQLAlchemy database schemas and relationships for all entities such as Users, Colleges, Events, and Permissions.'),
    ('config.py', 'Contains configuration variables, database URIs, and environment variable bindings.'),
    ('club_portal/', 'A Flask Blueprint directory containing routes and logic for club management, event creation, and event coordination.'),
    ('timetable_extractor/', 'Module containing the logic for parsing, extracting, and validating timetable data.'),
    ('templates/', 'Contains all Jinja2 HTML templates organized logically by roles (e.g., admin/, student/, faculty/).'),
    ('static/', 'Contains static assets such as CSS stylesheets, JavaScript files, and images.'),
    ('instance/', 'Flask instance folder for local database or instance-specific configurations.')
]

for item, desc in structure:
    p = doc.add_paragraph(style='List Bullet')
    run1 = p.add_run(f'{item}: ')
    run1.bold = True
    p.add_run(desc)

# 4. Database
add_page_break = doc.add_page_break()
add_heading(doc, '4. Database', 1)

add_heading(doc, 'Important Tables & Explanations', 2)

add_bullet(doc, 'College: Represents the tenant institution. It holds global configurations for the institution.')
add_bullet(doc, 'User: The central table for all human entities (Admin, HOD, Faculty, Student). Roles dictate access levels.')
add_bullet(doc, 'Department: Represents academic departments within a college.')
add_bullet(doc, 'Club & Event: Used for extracurricular activities. Events are linked to clubs, and students can register for them.')
add_bullet(doc, 'EventResponse: Tracks student registrations for events and stores payment statuses/tickets.')
add_bullet(doc, 'Attendance & ClassAttendance: Tracks attendance for events and regular academic classes respectively.')
add_bullet(doc, 'TimeTable: Stores the weekly schedule for different departments and sections.')
add_bullet(doc, 'Exam & ExamResult: Manages internal/external exams, fees, and student marks.')
add_bullet(doc, 'Permission: Handles student leave requests, club duty requests, and faculty approvals.')

add_heading(doc, 'Entity Relationship Diagram (ERD)', 2)
# Creating a simple textual ERD using Courier New font for alignment
p = doc.add_paragraph()
run = p.add_run('''College
   │
   ├── Department
   │
   ├── User (Students, Faculties, Admins)
   │     │
   │     ├── Attendance
   │     ├── Permission
   │     ├── ExamResult
   │     ├── ClassAttendance
   │     └── EventResponse
   │
   ├── Club
   │     │
   │     └── Event
   │           │
   │           └── EventResponse
   │
   └── Exam
         │
         ├── ExamFeePayment
         └── ExamResult''')
run.font.name = 'Courier New'
run.font.size = Pt(10)

# 5. Authentication
add_heading(doc, '5. Authentication', 1)
add_paragraph(doc, 'The authentication and authorization flow is primarily handled by Flask-Login with custom role-checking logic.')

flow = doc.add_paragraph()
flow_text = '''Login (Tenant-specific via <college_slug> or Global)
       ↓
Authentication (Validates Email & Password Hash via check_password_hash)
       ↓
Role Identification (Evaluates `user.role`: admin, student, faculty, etc.)
       ↓
Authorization (Custom logic/decorators restrict access to specific Blueprints and endpoints)
       ↓
Portal (Redirects the user to their respective role dashboard)'''
run = flow.add_run(flow_text)
run.font.name = 'Courier New'
run.font.size = Pt(10)

# 6. API Documentation
add_page_break = doc.add_page_break()
add_heading(doc, '6. API Documentation', 1)
add_paragraph(doc, 'GenZCampus is primarily a Server-Side Rendered (SSR) Flask application. Below is the documentation for the core routes functioning as internal APIs.')

apis = [
    {
        'endpoint': 'POST /<college_slug>/login',
        'desc': 'Authenticates a user for a specific college tenant.',
        'req': 'Form Data: email, password',
        'res': '302 Redirect to the appropriate role dashboard or login page on failure.',
        'auth': 'None',
        'params': 'college_slug (URL param)',
        'err': '401 Unauthorized (Invalid credentials)'
    },
    {
        'endpoint': 'GET /<college_slug>/admin/students',
        'desc': 'Retrieves the list of students for the college.',
        'req': 'None',
        'res': 'HTML string (Admin Students template) populated with student data.',
        'auth': 'Required, Role: Admin',
        'params': 'college_slug (URL param)',
        'err': '403 Forbidden (If user is not an admin)'
    },
    {
        'endpoint': 'GET /<college_slug>/student/profile/<int:id>',
        'desc': 'Fetches the detailed profile of a specific student.',
        'req': 'None',
        'res': 'HTML string (Student Profile template) containing user details, attendance, and exam results.',
        'auth': 'Required, Role: Admin/Faculty/Student(self)',
        'params': 'college_slug (URL param), id (Path param)',
        'err': '404 Not Found (If student does not exist)'
    },
    {
        'endpoint': 'POST /<college_slug>/faculty/attendance/mark',
        'desc': 'Submits class attendance for a specific department, year, and section.',
        'req': 'Form Data: date, subject, department, section, year, status array (present/absent)',
        'res': '302 Redirect to the attendance dashboard with a success flash message.',
        'auth': 'Required, Role: Faculty/HOD',
        'params': 'college_slug (URL param)',
        'err': '400 Bad Request (Missing required fields)'
    },
    {
        'endpoint': 'PUT /<college_slug>/faculty/attendance/update/<int:id>',
        'desc': 'Updates an existing attendance record for a specific class.',
        'req': 'JSON or Form Data: updated attendance array',
        'res': '200 OK (JSON response) or 302 Redirect.',
        'auth': 'Required, Role: Faculty/HOD',
        'params': 'college_slug (URL param), id (Path param)',
        'err': '404 Not Found (Record does not exist)'
    },
    {
        'endpoint': 'GET /<college_slug>/student/exam-results',
        'desc': 'Retrieves published exam results for the currently logged-in student.',
        'req': 'None',
        'res': 'HTML string (Results template) with tabulated marks and grades.',
        'auth': 'Required, Role: Student',
        'params': 'college_slug (URL param)',
        'err': '403 Forbidden (If not a student)'
    }
]

for api in apis:
    add_heading(doc, api['endpoint'], 2)
    add_paragraph(doc, api['desc'])
    
    t = doc.add_table(rows=5, cols=2)
    t.style = 'Table Grid'
    
    rows_data = [
        ('Request', api['req']),
        ('Response', api['res']),
        ('Authentication', api['auth']),
        ('Parameters', api['params']),
        ('Errors', api['err'])
    ]
    
    for i, (key, val) in enumerate(rows_data):
        t.rows[i].cells[0].text = key
        t.rows[i].cells[0].paragraphs[0].runs[0].bold = True
        t.rows[i].cells[1].text = val
    
    doc.add_paragraph('\n')

# 7. Portals & Role-Based Access
add_page_break = doc.add_page_break()
add_heading(doc, '7. Portals & Role-Based Access', 1)
add_paragraph(doc, "GenZCampus is divided into several interlinked portals, each serving a specific role. These portals share the same underlying database but expose different features based on the authenticated user's role.")

add_heading(doc, 'Admin Access (Super Admin & College Admin)', 2)
add_paragraph(doc, "Admins have full oversight of the institution's operations on the platform.")
add_bullet(doc, 'User Management: Can create, update, and remove students, faculties, and HODs.')
add_bullet(doc, 'System Configuration: Manage global college settings (branding, enabled features).')
add_bullet(doc, 'Oversight: View college-wide attendance reports, exam results, and club activities.')
add_bullet(doc, 'Financials: Monitor fee collections and event ticket sales.')

add_heading(doc, 'Faculty & HOD Features', 2)
add_paragraph(doc, 'Faculties interact with the academic and administrative aspects of student life.')
add_bullet(doc, 'Attendance Management: Mark daily attendance for their assigned classes and subjects.')
add_bullet(doc, 'Permission Approvals: Review and approve/reject leave requests or club duty requests from students.')
add_bullet(doc, 'Class Incharge Duties: Monitor the performance and attendance of their specific assigned class.')
add_bullet(doc, 'HOD Privileges: HODs can view department-wide analytics, manage timetables, and oversee faculty activities.')

add_heading(doc, 'Student Services & Access', 2)
add_paragraph(doc, 'Students use the portal to manage their academic journey and extracurricular participation.')
add_bullet(doc, 'Dashboard: View real-time attendance percentage, upcoming exams, and announcements.')
add_bullet(doc, 'Academics: Access exam results, timetables, and apply for leaves/permissions.')
add_bullet(doc, 'Club Registrations: Browse upcoming club events, register as solo or team, and pay event fees (via Razorpay).')
add_bullet(doc, 'Tickets & QR Codes: Access event tickets (QR codes) for check-in at club events.')
add_bullet(doc, 'Performance: Upload certificates and track extracurricular achievements.')

add_heading(doc, 'Club Portal Features', 2)
add_paragraph(doc, 'The Club Portal is a dedicated sub-system (Blueprint) for club coordinators and members to manage events.')
add_bullet(doc, 'Event Creation: Create new events, set registration deadlines, and define custom registration forms (dynamic schemas).')
add_bullet(doc, 'Ticketing & Payments: Sell paid event tickets, track Razorpay settlements, and manage team/solo registrations.')
add_bullet(doc, 'Event Check-in: Scan student QR codes to mark attendance for events.')
add_bullet(doc, "Finance Tracking: View the club's wallet balance, pending settlements, and transaction history.")

add_heading(doc, 'Portal Interlinking & Data Flow', 2)
add_paragraph(doc, 'The portals are deeply integrated to provide a seamless experience:')
add_bullet(doc, 'Events -> Permissions -> Attendance: When a student registers for an event via the Student Portal, they can request "Club Duty" (Permission). If the Faculty approves it in the Faculty Portal, the student is marked as "present on duty" in regular Class Attendance while attending the event in the Club Portal.')
add_bullet(doc, 'Clubs -> Finance -> Admin: Payments made by students for club events flow through Razorpay. The Club Portal tracks this balance, while the Admin Portal oversees the global financial settlements.')

# Save Document
doc.save('GenZCampus_Developer_Documentation_v2.docx')
print("Document saved successfully.")
