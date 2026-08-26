
import asyncio
import sqlite3
import os

async def check_settings():
    db_file = 'levels.db'
    if not os.path.exists(db_file):
        print(f"{db_file} not found")
        return
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    print("--- Guild Settings ---")
    cursor.execute("SELECT * FROM guild_settings")
    rows = cursor.fetchall()
    cols = [description[0] for description in cursor.description]
    for row in rows:
        print(dict(zip(cols, row)))
    
    print("\n--- Mute Roles ---")
    try:
        cursor.execute("SELECT * FROM mute_roles")
        rows = cursor.fetchall()
        for row in rows:
            print(row)
    except Exception as e:
        print(f"Error checking mute_roles table: {e}")
        
    conn.close()

if __name__ == "__main__":
    asyncio.run(check_settings())
