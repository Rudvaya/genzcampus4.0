import sqlite3
import json
import os

DB_PATH = 'timetable.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT,
            year TEXT,
            section TEXT,
            academic_year TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER,
            period_id_label TEXT,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (timetable_id) REFERENCES timetables(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timetable_id INTEGER,
            day TEXT,
            period_id_label TEXT,
            subject TEXT,
            type TEXT,
            merged_group TEXT,
            confidence REAL,
            FOREIGN KEY (timetable_id) REFERENCES timetables(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_timetable_to_db(data):
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Insert timetable
        c.execute('''
            INSERT INTO timetables (department, year, section)
            VALUES (?, ?, ?)
        ''', (data.get('department'), data.get('year'), data.get('section')))
        
        timetable_id = c.lastrowid
        
        # Insert periods
        for period in data.get('periods', []):
            c.execute('''
                INSERT INTO periods (timetable_id, period_id_label, start_time, end_time)
                VALUES (?, ?, ?, ?)
            ''', (timetable_id, period.get('id'), period.get('start'), period.get('end')))
        
        # Insert schedule
        timetable_days = data.get('timetable', {})
        for day, periods in timetable_days.items():
            for period_id_label, details in periods.items():
                subject = details.get('subject')
                item_type = details.get('type')
                merged_group = details.get('merged_group')
                if 'periods' in details:
                    for p in details['periods']:
                        c.execute('''
                            INSERT INTO schedule (timetable_id, day, period_id_label, subject, type, merged_group)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (timetable_id, day, p, subject, item_type, str(details['periods'])))
                else:
                    c.execute('''
                        INSERT INTO schedule (timetable_id, day, period_id_label, subject, type)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (timetable_id, day, period_id_label, subject, item_type))

        conn.commit()
        return timetable_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
