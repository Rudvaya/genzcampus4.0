import os
import re
from werkzeug.utils import secure_filename

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_roll_no(roll_no):
    """
    Validates roll number format: 5-20 chars, alphanumeric, at least 1 letter and 1 number
    Examples: 24N81A6261, STUDENT01, 23CS101
    """
    # Pattern: 5-20 chars, alphanumeric, must have at least one letter and one digit
    # Since roll_no is .upper() in app.py, we only check A-Z
    pattern = r'^(?=.*[A-Z])(?=.*\d)[A-Z0-9]{5,20}$'
    return re.match(pattern, roll_no.upper()) is not None
