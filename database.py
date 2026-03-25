import sqlite3

def init_db():
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    # Ana not tablomuz
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
    # 🧠 YENİ: Önbellek (Cache) için işlenmiş dosyalar tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_files (
            file_hash TEXT PRIMARY KEY,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

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
    # 🧹 YENİ: Clear Vault yapınca hafızayı da (Cache) sıfırla
    cursor.execute("DELETE FROM processed_files") 
    conn.commit()
    conn.close()

# 🛡️ YENİ: CACHE KONTROL FONKSİYONLARI
def is_file_processed(file_hash):
    """Bu dosya DNA'sı daha önce işlenmiş mi diye bakar."""
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM processed_files WHERE file_hash = ?", (file_hash,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_file_processed(file_hash, filename):
    """İşlemi biten dosyanın DNA'sını veritabanına mühürler."""
    conn = sqlite3.connect("academic_notes.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO processed_files (file_hash, filename) VALUES (?, ?)", (file_hash, filename))
    conn.commit()
    conn.close()