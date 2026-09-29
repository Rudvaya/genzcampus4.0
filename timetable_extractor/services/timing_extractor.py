import re
from datetime import datetime

def extract_timings_from_text(text):
    """
    Extracts time ranges from text.
    """
    if not isinstance(text, str):
        return []
    
    time_pattern = r'(\d{1,2}[:.]\d{2}(?:\s*(?:AM|PM|am|pm))?|\d{1,2}(?:\s*(?:AM|PM|am|pm))?)\s*(?:-|to|–)\s*(\d{1,2}[:.]\d{2}(?:\s*(?:AM|PM|am|pm))?|\d{1,2}(?:\s*(?:AM|PM|am|pm))?)'
    
    matches = re.findall(time_pattern, text)
    return matches

def normalize_time_range(match_tuple):
    """
    Takes a tuple like ('09:30', '10:20') and returns {'start': '09:30', 'end': '10:20'} in 24h format if possible.
    """
    start_str, end_str = match_tuple
    
    def parse_time(t_str):
        t_str = t_str.strip().upper().replace('.', ':')
        if ':' not in t_str:
            if 'AM' in t_str or 'PM' in t_str:
                t_str = t_str.replace('AM', ':00 AM').replace('PM', ':00 PM')
            else:
                t_str += ':00'
                
        formats = ['%I:%M %p', '%I:%M%p', '%H:%M', '%H:%M %p']
        for fmt in formats:
            try:
                dt = datetime.strptime(t_str, fmt)
                return dt.strftime('%H:%M')
            except ValueError:
                continue
        t_str = t_str.replace(' AM', '').replace(' PM', '')
        return t_str

    start_res = parse_time(start_str)
    end_res = parse_time(end_str)
    
    if start_res and end_res:
        start_h = int(start_res.split(':')[0])
        end_h = int(end_res.split(':')[0])
        
        # If start hour is small (e.g. 01, 02, 03, 04, 05), it's likely PM in a college timetable
        if start_h < 7:
            start_h += 12
            start_res = f"{start_h:02d}:{start_res.split(':')[1]}"
            
        # If end hour is less than start hour, it must have wrapped into PM
        if end_h < start_h and end_h < 12:
            end_h += 12
            end_res = f"{end_h:02d}:{end_res.split(':')[1]}"
            
        # If end hour is small and start hour is 12 (e.g. 12:00 - 01:00)
        elif start_h == 12 and end_h < 12:
            end_h += 12
            end_res = f"{end_h:02d}:{end_res.split(':')[1]}"

    return {
        'start': start_res,
        'end': end_res
    }
