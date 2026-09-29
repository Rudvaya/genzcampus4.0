import re

def fix_app_py():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # manage_students: User query
    content = re.sub(
        r"query = User\.query\.filter_by\(role='student'\)",
        r"query = User.query.filter_by(role='student', college_id=current_user.college_id)",
        content
    )

    # manage_students: Department query
    content = re.sub(
        r"departments = Department\.query\.order_by\(Department\.name\)\.all\(\)",
        r"departments = Department.query.filter_by(college_id=current_user.college_id).order_by(Department.name).all()",
        content
    )

    # add_student: existing roll_no check
    content = re.sub(
        r"if User\.query\.filter_by\(roll_no=roll_no\)\.first\(\):",
        r"if User.query.filter_by(roll_no=roll_no, college_id=current_user.college_id).first():",
        content
    )

    # add_student: User instantiation
    content = re.sub(
        r"(student = User\(\s*roll_no=roll_no,\s*email=email,\s*first_name=first_name,\s*last_name=last_name,\s*role='student',\s*department=department,\s*year=year,\s*section=section,\s*)(is_verified=True\s*#.*)",
        r"\g<1>college_id=current_user.college_id,\n        \g<2>",
        content
    )

    # manage_departments:
    content = re.sub(
        r"departments = Department\.query\.order_by\(Department\.name\)\.all\(\)",
        r"departments = Department.query.filter_by(college_id=current_user.college_id).order_by(Department.name).all()",
        content
    )

    # manage_faculty: HOD
    content = re.sub(
        r"(faculty = User\.query\.filter\(User\.role == 'faculty'\)\.filter\(\s*db\.or_\(\s*User\.department == current_user\.department,\s*User\.handling_departments\.like\(f\"%\{current_user\.department\}%\"\)\s*\)\s*)\)\.all\(\)",
        r"\g<1>, User.college_id == current_user.college_id).all()",
        content
    )

    # manage_faculty: departments HOD
    content = re.sub(
        r"departments = \[Department\.query\.filter_by\(name=current_user\.department\)\.first\(\)\]",
        r"departments = [Department.query.filter_by(name=current_user.department, college_id=current_user.college_id).first()]",
        content
    )

    # manage_faculty: Admin
    content = re.sub(
        r"faculty = User\.query\.filter\(User\.role\.in_\(\['faculty', 'hod'\]\)\)\.all\(\)",
        r"faculty = User.query.filter(User.role.in_(['faculty', 'hod']), User.college_id == current_user.college_id).all()",
        content
    )

    # manage_clubs:
    content = re.sub(
        r"clubs = Club\.query\.all\(\)",
        r"clubs = Club.query.filter_by(college_id=current_user.college_id).all()",
        content
    )

    # edit_faculty: get departments
    content = re.sub(
        r"departments = Department\.query\.all\(\)",
        r"departments = Department.query.filter_by(college_id=current_user.college_id).all()",
        content
    )

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("app.py updated")

if __name__ == '__main__':
    fix_app_py()
