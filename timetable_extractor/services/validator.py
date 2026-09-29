def validate_timetable_structure(data):
    """
    Validates the parsed JSON structure to ensure logic consistency.
    """
    errors = []
    
    periods = data.get('periods', [])
    if not periods:
        errors.append("No periods detected.")
        
    days = data.get('days', [])
    if not days:
        errors.append("No days detected.")
        
    if errors:
        return {'valid': False, 'errors': errors}
        
    return {'valid': True, 'errors': []}
