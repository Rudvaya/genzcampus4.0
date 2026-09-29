import re

def fix_app_py_part3():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # bulk upload students (line 1007)
    content = re.sub(
        r"if not User\.query\.filter_by\(roll_no=roll_no\)\.first\(\) and not User\.query\.filter_by\(email=email\)\.first\(\):",
        r"if not User.query.filter_by(roll_no=roll_no, college_id=current_user.college_id).first() and not User.query.filter_by(email=email).first():",
        content
    )

    # bulk upload students create
    content = re.sub(
        r"(student = User\(\s*roll_no=roll_no,\s*email=email,\s*first_name=first_name,\s*last_name=last_name,\s*role='student',\s*department=department,\s*year=year,\s*section=section,\s*)(is_verified=True\s*#.*)",
        r"\g<1>college_id=current_user.college_id,\n                            \g<2>",
        content
    )

    # delete department checks (lines 1396, 1402)
    content = re.sub(
        r"linked_users = User\.query\.filter_by\(department=department\.name\)\.first\(\)",
        r"linked_users = User.query.filter_by(department=department.name, college_id=current_user.college_id).first()",
        content
    )
    content = re.sub(
        r"linked_incharge = User\.query\.filter_by\(incharge_department=department\.name\)\.first\(\)",
        r"linked_incharge = User.query.filter_by(incharge_department=department.name, college_id=current_user.college_id).first()",
        content
    )

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("app.py updated part 3")

if __name__ == '__main__':
    fix_app_py_part3()
