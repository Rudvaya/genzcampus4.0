from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import uuid
from services.excel_parser import extract_from_excel
from services.pdf_parser import extract_from_pdf
from services.image_parser import extract_from_image
from models.database import save_timetable_to_db

timetable_bp = Blueprint('timetable', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls', 'xlx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@timetable_bp.route('/extract', methods=['POST'])
def extract_timetable():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    department = request.form.get('department', '')
    year = request.form.get('year', '')
    section = request.form.get('section', '')
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join('uploads', unique_filename)
        file.save(filepath)
        
        ext = filename.rsplit('.', 1)[1].lower()
        
        try:
            extracted_data = None
            if ext in ['xlsx', 'xls', 'xlx']:
                extracted_data = extract_from_excel(filepath)
            elif ext == 'pdf':
                extracted_data = extract_from_pdf(filepath)
            elif ext in ['jpg', 'jpeg', 'png']:
                extracted_data = extract_from_image(filepath)
                
            if extracted_data is None:
                return jsonify({
                    'success': False,
                    'error': 'Extraction failed or unsupported format.',
                    'needs_manual_review': True
                })
            
            extracted_data['department'] = department
            extracted_data['year'] = year
            extracted_data['section'] = section
            
            return jsonify({
                'success': True,
                'data': extracted_data
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'needs_manual_review': True
            })

@timetable_bp.route('/save', methods=['POST'])
def save_timetable():
    data = request.json
    try:
        timetable_id = save_timetable_to_db(data)
        return jsonify({'success': True, 'timetable_id': timetable_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
