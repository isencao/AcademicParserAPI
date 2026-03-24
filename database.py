import sqlite3

DB_NAME = "academic_notes.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            content TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_note(category, content, source):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notes (category, content, source) VALUES (?, ?, ?)", 
        (category, content, source)
    )
    conn.commit()
    conn.close()

def get_all_notes():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, content, source, created_at FROM notes ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    # Verileri arayüzün beklediği formata (JSON/Dict) çeviriyoruz
    return [
        {
            "ID": row["id"], 
            "Category": row["category"], 
            "Content": row["content"], 
            "Source": row["source"], 
            "CreatedAt": row["created_at"]
        } 
        for row in rows
    ]

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT category, COUNT(*) FROM notes GROUP BY category")
    rows = cursor.fetchall()
    conn.close()
    
    # Kategorileri ve sayılarını sözlük (dict) olarak dönüyoruz
    return {row[0]: row[1] for row in rows}

def clear_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes")
    conn.commit()
    conn.close()