import re

def fix_app_py_part2():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Admin dashboard counts
    content = re.sub(
        r"'total_students': User\.query\.filter_by\(role='student'\)\.count\(\),",
        r"'total_students': User.query.filter_by(role='student', college_id=current_user.college_id).count(),",
        content
    )
    content = re.sub(
        r"'total_faculty': User\.query\.filter\(User\.role\.in_\(\['faculty', 'hod'\]\)\)\.count\(\),",
        r"'total_faculty': User.query.filter(User.role.in_(['faculty', 'hod']), User.college_id==current_user.college_id).count(),",
        content
    )
    content = re.sub(
        r"'pending_permissions': Permission\.query\.filter_by\(status='pending'\)\.count\(\),",
        r"'pending_permissions': Permission.query.filter_by(status='pending', college_id=current_user.college_id).count(),",
        content
    )
    content = re.sub(
        r"'total_clubs': Club\.query\.count\(\)",
        r"'total_clubs': Club.query.filter_by(college_id=current_user.college_id).count()",
        content
    )

    # Manage permissions
    content = re.sub(
        r"permissions = Permission\.query\.order_by\(Permission\.applied_at\.desc\(\)\)\.all\(\)",
        r"permissions = Permission.query.filter_by(college_id=current_user.college_id).order_by(Permission.applied_at.desc()).all()",
        content
    )

    # Manage timetable
    content = re.sub(
        r"records = TimeTable\.query\.filter_by\(",
        r"records = TimeTable.query.filter_by(college_id=current_user.college_id, ",
        content
    )
    
    # Manage events? wait, clubs/events
    content = re.sub(
        r"'upcoming_events': Event\.query\.filter_by\(status='upcoming'\)\.count\(\),",
        r"'upcoming_events': Event.query.filter_by(status='upcoming', college_id=current_user.college_id).count(),",
        content
    )
    content = re.sub(
        r"'active_events': Event\.query\.filter_by\(status='active'\)\.count\(\)",
        r"'active_events': Event.query.filter_by(status='active', college_id=current_user.college_id).count()",
        content
    )

    # Events queries (where missing) - we might not find exact ones without seeing them, 
    # but club portal has `g.current_college.id` probably.

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("app.py updated part 2")

if __name__ == '__main__':
    fix_app_py_part2()
