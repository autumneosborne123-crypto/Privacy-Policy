import sqlite3
import os

db_path = 'levels.db'
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT animal_type FROM user_animals")
        types = cursor.fetchall()
        print("Distinct animal types in DB:")
        for t in types:
            print(f" - {t[0]}")
            
        cursor.execute("SELECT COUNT(*) FROM user_animals")
        count = cursor.fetchone()[0]
        print(f"Total animals in DB: {count}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
