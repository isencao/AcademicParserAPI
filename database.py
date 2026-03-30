import sqlite3
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class IDocumentRepository(ABC):
    @abstractmethod
    def init_db(self) -> None: pass
    
    @abstractmethod
    def save_note(self, card_id: str, doc_id: str, kind: str, title: str, body: str, anchors: str, span_hint: str) -> None: pass
    
    @abstractmethod
    def get_all_notes(self) -> List[Dict[str, Any]]: pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, int]: pass
    
    @abstractmethod
    def clear_database(self) -> None: pass
    
    @abstractmethod
    def is_file_processed(self, file_hash: str) -> bool: pass
    
    @abstractmethod
    def mark_file_processed(self, file_hash: str, filename: str) -> None: pass

    @abstractmethod
    def log_performance(self, filename: str, pages: int, process_time_sec: float, total_tokens: int) -> None: pass

    @abstractmethod
    def get_analytics(self) -> List[Dict[str, Any]]: pass

class SQLiteDocumentRepository(IDocumentRepository):
    def __init__(self, db_path: str = "academic_notes.db"):
        self.db_path = db_path
        self.init_db() 

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Final Şeması: Tüm akademik alanlar mevcut
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT,
                    doc_id TEXT,
                    kind TEXT,
                    title TEXT,
                    body TEXT,
                    anchors TEXT,
                    span_hint TEXT, 
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    pages INTEGER,
                    process_time_sec REAL,
                    total_tokens INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def save_note(self, card_id: str, doc_id: str, kind: str, title: str, body: str, anchors: str, span_hint: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (card_id, doc_id, kind, title, body, anchors, span_hint) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                (card_id, doc_id, kind, title, body, anchors, span_hint)
            )
            conn.commit()

    def get_all_notes(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT kind, COUNT(*) as count FROM notes GROUP BY kind")
            rows = cursor.fetchall()
            return {row["kind"]: row["count"] for row in rows}

    def clear_database(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes")
            cursor.execute("DELETE FROM processed_files") 
            conn.commit()

    def is_file_processed(self, file_hash: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT filename FROM processed_files WHERE file_hash = ?", (file_hash,))
            result = cursor.fetchone()
            return result is not None

    def mark_file_processed(self, file_hash: str, filename: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO processed_files (file_hash, filename) VALUES (?, ?)", 
                (file_hash, filename)
            )
            conn.commit()

    def log_performance(self, filename: str, pages: int, process_time_sec: float, total_tokens: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO analytics_log (filename, pages, process_time_sec, total_tokens) VALUES (?, ?, ?, ?)", 
                (filename, pages, process_time_sec, total_tokens)
            )
            conn.commit()

    def get_analytics(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM analytics_log ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

def get_db_repository() -> IDocumentRepository:
    return SQLiteDocumentRepository()