import sqlite3
import os

def update_database_v2():
    # Use absolute path relative to this script
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'pms.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Update Club table (Recreate to support UNIQUE club_login_id)
        print("Updating Club table...")
        cursor.execute("PRAGMA table_info(club)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'club_login_id' not in columns:
            print("Recreating Club table to add new fields...")
            cursor.execute("ALTER TABLE club RENAME TO club_old")
            cursor.execute("""
                CREATE TABLE club (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    coordinator_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    club_login_id VARCHAR(50) UNIQUE,
                    password_hash VARCHAR(256),
                    is_active BOOLEAN DEFAULT 1,
                    balance FLOAT DEFAULT 0.0,
                    FOREIGN KEY(coordinator_id) REFERENCES user(id)
                )
            """)
            cursor.execute("""
                INSERT INTO club (id, name, description, coordinator_id, created_at)
                SELECT id, name, description, coordinator_id, created_at FROM club_old
            """)
            cursor.execute("DROP TABLE club_old")

        # 2. Update Event table (Recreate to add new status and date fields)
        print("Updating Event table...")
        cursor.execute("PRAGMA table_info(event)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'start_date' not in columns:
            print("Recreating Event table to add new fields...")
            cursor.execute("ALTER TABLE event RENAME TO event_old")
            cursor.execute("""
                CREATE TABLE event (
                    id INTEGER PRIMARY KEY,
                    club_id INTEGER NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    date DATE NOT NULL,
                    venue VARCHAR(100),
                    start_date DATETIME,
                    end_date DATETIME,
                    status VARCHAR(20) DEFAULT 'upcoming',
                    allowed_departments TEXT,
                    participation_type VARCHAR(20) DEFAULT 'solo',
                    team_size_min INTEGER DEFAULT 1,
                    team_size_max INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(club_id) REFERENCES club(id)
                )
            """)
            cursor.execute("""
                INSERT INTO event (id, club_id, name, description, date, venue, created_at)
                SELECT id, club_id, name, description, date, venue, created_at FROM event_old
            """)
            cursor.execute("DROP TABLE event_old")

        # 3. Create New Tables
        print("Creating new tables...")
        
        # ClubMember
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS club_member (
                id INTEGER PRIMARY KEY,
                club_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role VARCHAR(20) NOT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(club_id) REFERENCES club(id),
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        """)

        # EventForm
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_form (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                schema_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES event(id)
            )
        """)

        # Team
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                leader_id INTEGER NOT NULL,
                team_name VARCHAR(100),
                team_id_code VARCHAR(10) UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES event(id),
                FOREIGN KEY(leader_id) REFERENCES user(id)
            )
        """)

        # TeamMember
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_member (
                id INTEGER PRIMARY KEY,
                team_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(team_id) REFERENCES team(id),
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        """)

        # EventResponse
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_response (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                team_id INTEGER,
                response_json TEXT NOT NULL,
                ticket_id VARCHAR(50) UNIQUE,
                qr_code_data TEXT,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(event_id) REFERENCES event(id),
                FOREIGN KEY(student_id) REFERENCES user(id),
                FOREIGN KEY(team_id) REFERENCES team(id)
            )
        """)

        # Attendance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY,
                response_id INTEGER NOT NULL,
                session_type VARCHAR(50),
                scanned_by INTEGER,
                scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(response_id) REFERENCES event_response(id),
                FOREIGN KEY(scanned_by) REFERENCES user(id)
            )
        """)

        # FinanceTransaction
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS finance_transaction (
                id INTEGER PRIMARY KEY,
                club_id INTEGER NOT NULL,
                event_id INTEGER,
                amount FLOAT NOT NULL,
                type VARCHAR(10),
                category VARCHAR(50),
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(club_id) REFERENCES club(id),
                FOREIGN KEY(event_id) REFERENCES event(id)
            )
        """)

        conn.commit()
        print("Database updated to v2 successfully!")

    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_database_v2()
