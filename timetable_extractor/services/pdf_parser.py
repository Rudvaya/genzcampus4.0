import pdfplumber
from services.timing_extractor import extract_timings_from_text, normalize_time_range

def extract_from_pdf(filepath):
    """
    Extracts timetable from a digital PDF using pdfplumber.
    """
    with pdfplumber.open(filepath) as pdf:
        if not pdf.pages:
            raise ValueError("Empty PDF")
            
        page = pdf.pages[0]
        tables = page.extract_tables()
        
        if not tables or not tables[0]:
            raise ValueError("No extractable tables found in PDF. Needs OCR.")
            
        matrix = tables[0]
        
        timing_row_idx = None
        days_col_idx = None
        days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        days_abbrev = [d[:3] for d in days_of_week]
        
        periods = []
        period_cols = {}
        
        for r_idx, row in enumerate(matrix):
            time_matches = 0
            temp_periods = []
            for c_idx, cell in enumerate(row):
                if cell:
                    cell_text = cell.replace('\n', ' ')
                    extracted = extract_timings_from_text(cell_text)
                    if extracted:
                        time_matches += 1
                        norm = normalize_time_range(extracted[0])
                        if norm:
                            temp_periods.append({
                                'col_idx': c_idx,
                                'id': f"P{time_matches}",
                                'start': norm['start'],
                                'end': norm['end']
                            })
            if time_matches >= 3:
                timing_row_idx = r_idx
                for tp in temp_periods:
                    periods.append({
                        'id': tp['id'],
                        'start': tp['start'],
                        'end': tp['end']
                    })
                    period_cols[tp['col_idx']] = tp['id']
                break
                
        for r_idx, row in enumerate(matrix):
            for c_idx, cell in enumerate(row):
                if cell:
                    c_lower = str(cell).strip().lower()
                    if c_lower in days_of_week or c_lower in days_abbrev:
                        days_col_idx = c_idx
                        break
            if days_col_idx is not None:
                break
                
        if timing_row_idx is None or days_col_idx is None:
            raise ValueError("Could not reliably detect the timetable timing row or days column.")
            
        extracted_days = []
        timetable_data = {}
        
        for r_idx in range(timing_row_idx + 1, len(matrix)):
            row = matrix[r_idx]
            if len(row) <= days_col_idx: continue
            day_cell = row[days_col_idx]
            if not day_cell:
                continue
                
            day_str = str(day_cell).strip().capitalize()
            if day_str.lower() in days_of_week or day_str.lower()[:3] in [d[:3] for d in days_of_week]:
                day_full = next((d.capitalize() for d in days_of_week if d.startswith(day_str.lower()[:3])), day_str)
                extracted_days.append(day_full)
                timetable_data[day_full] = {}
                
                for c_idx, p_id in period_cols.items():
                    if len(row) > c_idx:
                        cell_val = row[c_idx]
                        if cell_val:
                            cell_str = str(cell_val).strip().replace('\n', ' ')
                            
                            cell_type = 'lecture'
                            
                            cell_str_clean = cell_str.replace(' ', '')
                            if 'lab' in cell_str.lower():
                                cell_type = 'lab'
                            elif 'break' in cell_str_clean.lower() or 'lunch' in cell_str_clean.lower():
                                cell_type = 'break'
                                
                            timetable_data[day_full][p_id] = {
                                'subject': cell_str,
                                'type': cell_type
                            }
                            
        return {
            'periods': periods,
            'days': extracted_days,
            'timetable': timetable_data
        }
