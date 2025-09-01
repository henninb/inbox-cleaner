"""Tests for SQLite database operations."""

import pytest
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock
import tempfile

from inbox_cleaner.database import DatabaseManager, EmailMetadata


class TestDatabaseManager:
    """Test cases for SQLite database management."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            yield Path(f.name)
        # Cleanup
        Path(f.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def db_manager(self, temp_db_path):
        """Create a DatabaseManager instance for testing."""
        return DatabaseManager(str(temp_db_path))
    
    @pytest.fixture
    def sample_email_metadata(self):
        """Sample EmailMetadata for testing."""
        return EmailMetadata(
            message_id="test_msg_123",
            thread_id="test_thread_123",
            sender_email="sender@example.com",
            sender_domain="example.com", 
            sender_hash="abc123hash",
            subject="Test Email Subject",
            date_received=datetime(2022, 1, 1, 12, 0, 0),
            labels=["INBOX", "UNREAD"],
            snippet="This is a test email snippet",
            content="This is the test email content",
            estimated_importance=0.7
        )
    
    def test_init_creates_database_file(self, temp_db_path):
        """Test that initializing DatabaseManager creates the database file."""
        db_manager = DatabaseManager(str(temp_db_path))
        assert temp_db_path.exists()
        assert db_manager.db_path == str(temp_db_path)
    
    def test_init_creates_tables(self, db_manager):
        """Test that initializing DatabaseManager creates required tables."""
        # Check that tables exist
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Check emails_metadata table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='emails_metadata'
            """)
            assert cursor.fetchone() is not None
            
            # Check table schema
            cursor.execute("PRAGMA table_info(emails_metadata)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            expected_columns = {
                'message_id': 'TEXT',
                'thread_id': 'TEXT',
                'sender_domain': 'TEXT',
                'sender_hash': 'TEXT',
                'subject': 'TEXT',
                'date_received': 'DATETIME',
                'labels': 'TEXT',
                'snippet': 'TEXT',
                'content': 'TEXT',
                'estimated_importance': 'REAL',
                'category': 'TEXT',
                'created_at': 'DATETIME',
                'updated_at': 'DATETIME'
            }
            
            for col_name, col_type in expected_columns.items():
                assert col_name in columns
                assert col_type in columns[col_name].upper()
    
    def test_insert_email_success(self, db_manager, sample_email_metadata):
        """Test successful email metadata insertion."""
        result = db_manager.insert_email(sample_email_metadata)
        
        assert result is True
        
        # Verify the data was inserted
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails_metadata WHERE message_id = ?", 
                          (sample_email_metadata.message_id,))
            row = cursor.fetchone()
            
            assert row is not None
            assert row[0] == sample_email_metadata.message_id  # message_id
            assert row[2] == sample_email_metadata.sender_domain
    
    def test_insert_email_duplicate_handling(self, db_manager, sample_email_metadata):
        """Test handling of duplicate email insertions."""
        # Insert the same email twice
        result1 = db_manager.insert_email(sample_email_metadata)
        result2 = db_manager.insert_email(sample_email_metadata)
        
        assert result1 is True
        assert result2 is True  # Should handle duplicates gracefully
        
        # Verify only one record exists
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM emails_metadata WHERE message_id = ?",
                          (sample_email_metadata.message_id,))
            count = cursor.fetchone()[0]
            assert count == 1
    
    def test_insert_batch_success(self, db_manager):
        """Test successful batch insertion of email metadata."""
        emails = []
        for i in range(5):
            email = EmailMetadata(
                message_id=f"msg_{i}",
                thread_id=f"thread_{i}",
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                sender_hash=f"hash_{i}",
                subject=f"Subject {i}",
                date_received=datetime(2022, 1, i+1, 12, 0, 0),
                labels=["INBOX"],
                snippet=f"Snippet {i}",
                content=f"Content {i}",
                estimated_importance=0.5
            )
            emails.append(email)
        
        result = db_manager.insert_batch(emails)
        
        assert result == 5  # Should return number of inserted records
        
        # Verify all records were inserted
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM emails_metadata")
            count = cursor.fetchone()[0]
            assert count == 5
    
    def test_get_email_by_id(self, db_manager, sample_email_metadata):
        """Test retrieving email by message ID."""
        # Insert test email
        db_manager.insert_email(sample_email_metadata)
        
        # Retrieve it
        result = db_manager.get_email_by_id(sample_email_metadata.message_id)
        
        assert result is not None
        assert result['message_id'] == sample_email_metadata.message_id
        assert result['sender_domain'] == sample_email_metadata.sender_domain
    
    def test_get_email_by_id_not_found(self, db_manager):
        """Test retrieving non-existent email."""
        result = db_manager.get_email_by_id("non_existent_id")
        assert result is None
    
    def test_get_emails_by_domain(self, db_manager):
        """Test retrieving emails by sender domain."""
        # Insert test emails from different domains
        domains = ["example.com", "test.com", "example.com"]
        for i, domain in enumerate(domains):
            email = EmailMetadata(
                message_id=f"msg_{i}",
                thread_id=f"thread_{i}",
                sender_email=f"sender{i}@{domain}",
                sender_domain=domain,
                sender_hash=f"hash_{i}",
                subject=f"Subject {i}",
                date_received=datetime(2022, 1, i+1),
                labels=["INBOX"],
                snippet=f"Snippet {i}",
                content=f"Content {i}"
            )
            db_manager.insert_email(email)
        
        # Get emails from example.com
        results = db_manager.get_emails_by_domain("example.com")
        
        assert len(results) == 2
        assert all(r['sender_domain'] == "example.com" for r in results)
    
    def test_get_emails_by_date_range(self, db_manager):
        """Test retrieving emails by date range."""
        # Insert emails with different dates
        dates = [
            datetime(2022, 1, 1),
            datetime(2022, 1, 15), 
            datetime(2022, 2, 1)
        ]
        
        for i, date in enumerate(dates):
            email = EmailMetadata(
                message_id=f"msg_{i}",
                thread_id=f"thread_{i}",
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                sender_hash=f"hash_{i}",
                subject=f"Subject {i}",
                date_received=date,
                labels=["INBOX"],
                snippet=f"Snippet {i}",
                content=f"Content {i}"
            )
            db_manager.insert_email(email)
        
        # Get emails from January 2022
        start_date = datetime(2022, 1, 1)
        end_date = datetime(2022, 1, 31)
        results = db_manager.get_emails_by_date_range(start_date, end_date)
        
        assert len(results) == 2
        for result in results:
            result_date = datetime.fromisoformat(result['date_received'])
            assert start_date <= result_date <= end_date
    
    def test_update_email_category(self, db_manager, sample_email_metadata):
        """Test updating email category."""
        # Insert test email
        db_manager.insert_email(sample_email_metadata)
        
        # Update category
        result = db_manager.update_email_category(sample_email_metadata.message_id, "newsletter")
        
        assert result is True
        
        # Verify the update
        email = db_manager.get_email_by_id(sample_email_metadata.message_id)
        assert email['category'] == "newsletter"
    
    def test_delete_email(self, db_manager, sample_email_metadata):
        """Test deleting email by message ID."""
        # Insert test email
        db_manager.insert_email(sample_email_metadata)
        
        # Verify it exists
        assert db_manager.get_email_by_id(sample_email_metadata.message_id) is not None
        
        # Delete it
        result = db_manager.delete_email(sample_email_metadata.message_id)
        
        assert result is True
        assert db_manager.get_email_by_id(sample_email_metadata.message_id) is None
    
    def test_get_statistics(self, db_manager):
        """Test getting database statistics."""
        # Insert test emails with different categories and labels
        categories = ["personal", "newsletter", "work", "newsletter"]
        labels_list = [["INBOX"], ["INBOX", "UNREAD"], ["INBOX", "WORK"], ["INBOX", "PROMOTIONAL"]]
        
        for i in range(4):
            email = EmailMetadata(
                message_id=f"msg_{i}",
                thread_id=f"thread_{i}",
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                sender_hash=f"hash_{i}",
                subject=f"Subject {i}",
                date_received=datetime(2022, 1, i+1),
                labels=labels_list[i],
                snippet=f"Snippet {i}",
                content=f"Content {i}",
                category=categories[i]
            )
            db_manager.insert_email(email)
        
        stats = db_manager.get_statistics()
        
        assert stats['total_emails'] == 4
        assert stats['categories']['newsletter'] == 2
        assert stats['categories']['personal'] == 1
        assert stats['labels']['INBOX'] == 4
        assert stats['labels']['UNREAD'] == 1
    
    def test_get_domain_statistics(self, db_manager):
        """Test getting domain-specific statistics."""
        # Insert emails from different domains
        domains = ["example.com", "test.com", "example.com", "spam.com"]
        
        for i, domain in enumerate(domains):
            email = EmailMetadata(
                message_id=f"msg_{i}",
                thread_id=f"thread_{i}",
                sender_email=f"sender{i}@{domain}",
                sender_domain=domain,
                sender_hash=f"hash_{i}",
                subject=f"Subject {i}",
                date_received=datetime(2022, 1, i+1),
                labels=["INBOX"],
                snippet=f"Snippet {i}",
                content=f"Content {i}"
            )
            db_manager.insert_email(email)
        
        stats = db_manager.get_domain_statistics()
        
        assert stats['example.com'] == 2
        assert stats['test.com'] == 1
        assert stats['spam.com'] == 1
    
    def test_search_emails(self, db_manager):
        """Test email search functionality."""
        # Insert test emails with different subjects
        subjects = [
            "Meeting tomorrow at 3pm",
            "Newsletter: Weekly Updates",
            "Meeting cancelled",
            "Your order confirmation"
        ]
        
        for i, subject in enumerate(subjects):
            email = EmailMetadata(
                message_id=f"msg_{i}",
                thread_id=f"thread_{i}",
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                sender_hash=f"hash_{i}",
                subject=subject,
                date_received=datetime(2022, 1, i+1),
                labels=["INBOX"],
                snippet=f"Snippet {i}",
                content=f"Content {i}"
            )
            db_manager.insert_email(email)
        
        # Search for emails with "meeting" in subject
        results = db_manager.search_emails(query="meeting")
        
        assert len(results) == 2
        assert all("meeting" in r['subject'].lower() for r in results)
    
    def test_database_connection_error_handling(self, temp_db_path):
        """Test error handling for database connection issues."""
        # Use an invalid path to trigger connection error
        invalid_path = "/invalid/path/to/database.db"
        
        with pytest.raises(Exception):  # Should raise an exception
            DatabaseManager(invalid_path)
    
    def test_context_manager_usage(self, db_manager):
        """Test using DatabaseManager as a context manager."""
        with db_manager as db:
            assert db == db_manager
            # Database should be accessible
            stats = db.get_statistics()
            assert isinstance(stats, dict)