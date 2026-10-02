# 🎓 GenZCampus 4.0 — Next-Gen Multi-Tenant Campus Management System

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://supabase.com)
[![Cloudinary](https://img.shields.io/badge/Cloudinary-Media%20Storage-3448C5?style=for-the-badge&logo=cloudinary&logoColor=white)](https://cloudinary.com)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.1.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com)

**GenZCampus 4.0** is an enterprise-grade, multi-tenant academic and campus management platform designed for modern colleges and universities. Built with a robust Flask and PostgreSQL backend, it features dynamic college slug routing, comprehensive role-based access control (RBAC), real-time attendance management, assignment workflows, performance analytics, timetable scheduling, event permission tracking, notice boards, and a responsive dark/light glassmorphic UI.

---

## 🌟 Key Features & Modules

### 🏢 1. Multi-Tenant Architecture & Branding
- **Dynamic Slug Routing**: Each institution operates under its unique slug namespace (e.g., `/{college_slug}/faculty/dashboard`).
- **Global College Branding**: Custom college logo uploads, institution name, and color theme synchronization.
- **SuperAdmin Console**: Global management of college tenancies, system health, and feature flags.

### 📋 2. Class Attendance System
- **Interactive Grid Interface**: Instant one-tap node toggling for `Present`/`Absent`.
- **Automated Timetable Detection**: Automatically fetches today's schedule for selected department, year, and section.
- **Permission Approved (PA) Integration**: Displays purple PA badges on student nodes with event/club reasons to prevent accidental absent marks.
- **Historical Attendance Logs**: Comprehensive attendance logs with date-filtering and subject breakdowns.

### 👨‍🎓 3. Student Management & Directories
- **Assigned Class Rosters**: Filter students by department, year, and section with live metric calculations.
- **Student Profile Overview**: View cumulative attendance records, enrolled subjects, academic scores, and recent performance logs.
- **Data Privacy & Protection**: Sensitive student contact information is protected and governed by college administration.

### 📊 4. Marks & Evaluation Management
- **Multi-Assessment Support**: Manage Internal marks, Assignment scores, Quiz marks, Lab assessments, Mid-1/Mid-2 exams, and Semester performance.
- **Live Performance Metrics**: Real-time evaluation analytics calculating class average, highest score, pass percentage, and grading completion.
- **Remarks & Feedback**: Record student-specific feedback and remarks stored directly in the database.

### 📝 5. Assignment Workflow & Grading
- **Faculty Assignment Publisher**: Create assignments with file attachments, deadlines, target year/section, and max marks.
- **Student Submission Hub**: Online submission via file upload (PDF, DOCX, ZIP, Images) or textual solution links.
- **Late Submission Tracking**: Automatic detection and labeling for submissions received past deadline.
- **Faculty Review & Grading Modal**: Grade student solutions directly in an interactive modal with instant feedback delivery.

### 📢 6. Circulars & Notice Board System
- **Prioritized Announcements**: Post notices categorized by `URGENT`, `HIGH`, or `NORMAL` priority.
- **Attachment Support**: Upload PDF circulars and document attachments.
- **Unified Role Access**: Both viewing (in-browser modal/viewer) and direct downloading are fully enabled for SuperAdmin, Admin, HOD, Faculty, and Students.
- **Cloudinary Integration**: Cloud storage integration with local file fallback for maximum reliability.

### 📅 7. Timetable & Schedule Management
- **Full Weekly Schedules**: Period-wise timetable management with customizable slot times.
- **Incharge Quick Actions**: Section Incharges can swap period schedules or declare holiday schedules for their classes.
- **Student Daily Timeline**: Visual timeline view of daily subjects on student dashboards.

### 🏆 8. Clubs, Events & Permissions
- **Event Management**: Create and announce club events and extracurricular competitions.
- **Permission Approval Flow**: Students apply for event permissions -> Section Incharge / HOD approves -> Real-time sync with Class Attendance roster.

### 🎨 9. Modern UI/UX Experience
- **Resizable Sidebar**: Draggable splitter allowing users to adjust sidebar width smoothly with local storage persistence.
- **Dark/Light Mode**: Integrated theme toggle across all portals.
- **Mobile Responsive Drawer & Bottom Nav**: Native-app style mobile drawer and quick bottom navigation bar.
- **URL Hash Synchronization**: Seamless client-side tab switching without full-page reloads.

---

## 👥 Role-Based Access Control (RBAC)

| Role | Core Capabilities |
| :--- | :--- |
| **Super Admin** | Manage colleges, register institutions, global configurations, system monitoring |
| **Admin** | Full college management, department directory, faculty/student CRUD, timetable, ledger |
| **Principal / Secretary** | Academic overview, institution-wide performance metrics, financial ledger |
| **Exam Admin** | Exam scheduling, mark sheets, grade records, academic audits |
| **Head of Department (HOD)** | Department faculty management, notice circulation, permission approvals |
| **Section Incharge** | Class schedule adjustments, period swapping, holiday declarations |
| **Faculty** | Attendance marking, student evaluation, marks management, assignment grading |
| **Student** | Daily timeline, attendance analytics, assignment submission, permission applications |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Migrate
- **Database**: PostgreSQL (Supabase / AWS Pooler)
- **Media & File Storage**: Cloudinary, Local File System
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System), JavaScript (ES6+), jQuery
- **UI Framework & Icons**: Bootstrap 5.1.3, FontAwesome 6.x
- **Select / Form UI**: Select2

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- PostgreSQL database (or Supabase account)
- Cloudinary account (for media attachments)

### 2. Clone the Repository
```bash
git clone https://github.com/Rudvaya/genzcampus4.0.git
cd genzcampus4.0
```

### 3. Create a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Configuration
Create a `.env` file in the root directory:
```env
# Database Configuration
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require

# AI & Supabase (Optional/Extended)
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Cloudinary Storage Configuration
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### 6. Run Database Migrations & Start the Server
```bash
python app.py
```
The application will start on `http://127.0.0.1:5000/`.

---

## 📂 Project Structure

```
genzcampus4.0/
├── app.py                      # Main Flask application and API route controllers
├── models.py                   # SQLAlchemy models (User, College, Assignment, etc.)
├── cloudinary_storage.py       # Cloudinary file upload & management utility
├── requirements.txt            # Python dependencies
├── .env                        # Environment configurations
├── static/
│   ├── css/
│   │   └── style.css           # Global modern CSS design system
│   └── js/                     # Custom scripts and interactive logic
├── templates/
│   ├── base.html               # Base layout with resizable sidebar & bottom nav
│   ├── admin/                  # Admin portal templates
│   ├── faculty/                # Faculty portal templates (Dashboard, Timetable, Notices)
│   ├── student/                # Student portal templates (Dashboard, Performance, Notices)
│   └── analytics/              # Performance analytics templates
└── uploads/                    # Local storage fallback directory
```

---

## 🔒 Security & Best Practices
- Passwords securely hashed with `Werkzeug` security algorithms.
- Protected multi-tenant routing verifying college slug affiliation on every request.
- CSRF protection and role validation decorators (`@login_required`, `@role_required`).

---

## 📄 License
This project is proprietary and maintained by the **Rudvaya / GenZCampus** Team. All rights reserved.
