import sqlite3

def init_db():
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    # Sayfa (page) sütunu eklendi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            content TEXT,
            source TEXT,
            page TEXT, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# DİKKAT: Fonksiyona 'page' parametresi eklendi!
def save_note(category, content, source, page="-"):
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notes (category, content, source, page) VALUES (?, ?, ?, ?)", 
                   (category, content, source, str(page)))
    conn.commit()
    conn.close()

def get_all_notes():
    conn = sqlite3.connect("academic_notes.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_stats():
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT category, COUNT(*) as count FROM notes GROUP BY category")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def clear_database():
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes")
    conn.commit()
    conn.close()