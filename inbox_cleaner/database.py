"""SQLite database operations for email metadata storage."""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from .extractor import EmailMetadata

# SQL schema constants
CREATE_EMAILS_TABLE = """
CREATE TABLE IF NOT EXISTS emails_metadata (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT,
    sender_domain TEXT,
    sender_hash TEXT,
    subject TEXT,
    date_received DATETIME,
    labels TEXT,  -- JSON array
    snippet TEXT,
    content TEXT,
    estimated_importance REAL,
    category TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sender_domain ON emails_metadata(sender_domain)",
    "CREATE INDEX IF NOT EXISTS idx_date_received ON emails_metadata(date_received)",
    "CREATE INDEX IF NOT EXISTS idx_category ON emails_metadata(category)",
    "CREATE INDEX IF NOT EXISTS idx_labels ON emails_metadata(labels)",
]


class DatabaseManager:
    """Manages SQLite database operations for email metadata."""

    def __init__(self, db_path: str) -> None:
        """Initialize database manager."""
        self.db_path = db_path

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Create database file and tables
        self._create_tables()

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(CREATE_EMAILS_TABLE)

                # Create indexes for performance
                for index_sql in CREATE_INDEXES:
                    conn.execute(index_sql)

                conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to create database tables: {e}")

    def insert_email(self, email: EmailMetadata) -> bool:
        """Insert email metadata into database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO emails_metadata
                    (message_id, thread_id, sender_domain, sender_hash, subject,
                     date_received, labels, snippet, content, estimated_importance, category, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    email.message_id,
                    email.thread_id,
                    email.sender_domain,
                    email.sender_hash,
                    email.subject,
                    email.date_received.isoformat(),
                    json.dumps(email.labels),
                    email.snippet,
                    email.content,
                    email.estimated_importance,
                    email.category
                ))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def insert_batch(self, emails: List[EmailMetadata]) -> int:
        """Insert batch of email metadata."""
        if not emails:
            return 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                data = []
                for email in emails:
                    data.append((
                        email.message_id,
                        email.thread_id,
                        email.sender_domain,
                        email.sender_hash,
                        email.subject,
                        email.date_received.isoformat(),
                        json.dumps(email.labels),
                        email.snippet,
                        email.content,
                        email.estimated_importance,
                        email.category
                    ))

                cursor = conn.executemany("""
                    INSERT OR REPLACE INTO emails_metadata
                    (message_id, thread_id, sender_domain, sender_hash, subject,
                     date_received, labels, snippet, content, estimated_importance, category, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, data)

                conn.commit()
                return cursor.rowcount
        except sqlite3.Error:
            return 0

    def get_email_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve email by message ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM emails_metadata WHERE message_id = ?
                """, (message_id,))

                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    result['labels'] = json.loads(result['labels'])
                    return result
                return None
        except sqlite3.Error:
            return None

    def get_emails_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all emails from a specific domain."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM emails_metadata
                    WHERE sender_domain = ?
                    ORDER BY date_received DESC
                """, (domain,))

                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result['labels'] = json.loads(result['labels'])
                    results.append(result)
                return results
        except sqlite3.Error:
            return []

    def get_emails_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get emails within date range."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM emails_metadata
                    WHERE date_received BETWEEN ? AND ?
                    ORDER BY date_received DESC
                """, (start_date.isoformat(), end_date.isoformat()))

                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result['labels'] = json.loads(result['labels'])
                    results.append(result)
                return results
        except sqlite3.Error:
            return []

    def update_email_category(self, message_id: str, category: str) -> bool:
        """Update email category."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE emails_metadata
                    SET category = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE message_id = ?
                """, (category, message_id))

                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def delete_email(self, message_id: str) -> bool:
        """Delete email by message ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM emails_metadata WHERE message_id = ?
                """, (message_id,))

                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total emails
                total_cursor = conn.execute("SELECT COUNT(*) FROM emails_metadata")
                total_emails = total_cursor.fetchone()[0]

                # Category statistics
                category_cursor = conn.execute("""
                    SELECT category, COUNT(*) FROM emails_metadata
                    WHERE category IS NOT NULL
                    GROUP BY category
                """)
                categories = dict(category_cursor.fetchall())

                # Label statistics - more complex due to JSON
                label_stats = defaultdict(int)
                labels_cursor = conn.execute("SELECT labels FROM emails_metadata")
                for (labels_json,) in labels_cursor.fetchall():
                    try:
                        labels = json.loads(labels_json)
                        for label in labels:
                            label_stats[label] += 1
                    except (json.JSONDecodeError, TypeError):
                        continue

                return {
                    'total_emails': total_emails,
                    'categories': categories,
                    'labels': dict(label_stats)
                }
        except sqlite3.Error:
            return {
                'total_emails': 0,
                'categories': {},
                'labels': {}
            }

    def get_domain_statistics(self) -> Dict[str, int]:
        """Get email count by domain."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT sender_domain, COUNT(*) FROM emails_metadata
                    GROUP BY sender_domain
                    ORDER BY COUNT(*) DESC
                """)
                return dict(cursor.fetchall())
        except sqlite3.Error:
            return {}

    def search_emails(self, query: str) -> List[Dict[str, Any]]:
        """Search emails by content."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM emails_metadata
                    WHERE subject LIKE ? OR snippet LIKE ? OR content LIKE ?
                    ORDER BY date_received DESC
                    LIMIT 100
                """, (f'%{query}%', f'%{query}%', f'%{query}%'))

                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result['labels'] = json.loads(result['labels'])
                    results.append(result)
                return results
        except sqlite3.Error:
            return []

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # SQLite connections are automatically closed when they go out of scope
        pass