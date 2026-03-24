import sqlite3

DB_FILE = "academic_notes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Notes (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            Category TEXT,
            Content TEXT,
            Source TEXT,
            CreatedAt TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn