from app import app, db, TimeTable

with app.app_context():
    records = TimeTable.query.all()
    for r in records:
        print(f"ID: {r.id}, Day: {r.day}, Dept: {r.department}, Year: {r.year}, Sec: {r.section}")
        print(f"  P1: {r.period_1} ({r.period_1_time})")
        print(f"  P2: {r.period_2} ({r.period_2_time})")
        print(f"  P3: {r.period_3} ({r.period_3_time})")
        print(f"  P4: {r.period_4} ({r.period_4_time})")
        print(f"  P5: {r.period_5} ({r.period_5_time})")
        print(f"  P6: {r.period_6} ({r.period_6_time})")
        print(f"  P7: {r.period_7} ({r.period_7_time})")
        print("-" * 20)
