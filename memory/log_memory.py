import sqlite3

def log_event(speaker, text, db_path="alice_memory.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (speaker, content) VALUES (?, ?)", (speaker, text))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Log Event Error: {e}]")
