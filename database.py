import sqlite3
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

RELATION_TYPES = {"related_to", "depends_on", "example_of", "uses", "generalizes"}

class IDocumentRepository(ABC):
    @abstractmethod
    def init_db(self) -> None: pass

    @abstractmethod
    def save_note(self, card_id: str, doc_id: str, kind: str, title: str, body: str, anchors: str, span_hint: str,
                  tags: str = "[]", confidence: float = 1.0, extraction_method: str = "llm") -> None: pass

    @abstractmethod
    def update_note(self, card_id: str, kind: str, title: str, body: str) -> None: pass

    @abstractmethod
    def delete_note(self, card_id: str) -> None: pass

    @abstractmethod
    def get_all_notes(self) -> List[Dict[str, Any]]: pass

    @abstractmethod
    def get_note_by_card_id(self, card_id: str) -> Optional[Dict[str, Any]]: pass

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

    @abstractmethod
    def add_relation(self, source_card_id: str, target_card_id: str, relation_type: str, created_by: str = "user") -> int: pass

    @abstractmethod
    def get_relations(self, card_id: Optional[str] = None) -> List[Dict[str, Any]]: pass

    @abstractmethod
    def delete_relation(self, relation_id: int) -> None: pass

    @abstractmethod
    def clear_auto_relations(self) -> None: pass

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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT,
                    doc_id TEXT,
                    kind TEXT,
                    title TEXT,
                    body TEXT,
                    anchors TEXT,
                    tags TEXT,
                    span_hint TEXT,
                    confidence REAL DEFAULT 1.0,
                    extraction_method TEXT DEFAULT 'llm',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Migration: add new columns to existing databases
            for col, definition in [
                ("tags", "TEXT"),
                ("confidence", "REAL DEFAULT 1.0"),
                ("extraction_method", "TEXT DEFAULT 'llm'"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE notes ADD COLUMN {col} {definition}")
                except Exception:
                    pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS card_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_card_id TEXT NOT NULL,
                    target_card_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    created_by TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_card_id, target_card_id, relation_type)
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

    def save_note(self, card_id: str, doc_id: str, kind: str, title: str, body: str, anchors: str, span_hint: str,
                  tags: str = "[]", confidence: float = 1.0, extraction_method: str = "llm") -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notes (card_id, doc_id, kind, title, body, anchors, span_hint, tags, confidence, extraction_method) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (card_id, doc_id, kind, title, body, anchors, span_hint, tags, confidence, extraction_method)
            )
            conn.commit()

    def update_note(self, card_id: str, kind: str, title: str, body: str) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute(
                "UPDATE notes SET kind=?, title=?, body=? WHERE card_id=?",
                (kind, title, body, card_id)
            )
            conn.commit()

    def delete_note(self, card_id: str) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM notes WHERE card_id=?", (card_id,))
            conn.commit()

    def get_all_notes(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_note_by_card_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE card_id = ?", (card_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

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

    def add_relation(self, source_card_id: str, target_card_id: str, relation_type: str, created_by: str = "user") -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO card_relations (source_card_id, target_card_id, relation_type, created_by) VALUES (?,?,?,?)",
                (source_card_id, target_card_id, relation_type, created_by)
            )
            conn.commit()
            return cursor.lastrowid

    def get_relations(self, card_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if card_id:
                cursor.execute(
                    "SELECT * FROM card_relations WHERE source_card_id=? OR target_card_id=? ORDER BY id DESC",
                    (card_id, card_id)
                )
            else:
                cursor.execute("SELECT * FROM card_relations ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_relation(self, relation_id: int) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM card_relations WHERE id=?", (relation_id,))
            conn.commit()

    def clear_auto_relations(self) -> None:
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM card_relations WHERE created_by='auto'")
            conn.commit()

def get_db_repository() -> IDocumentRepository:
    return SQLiteDocumentRepository()