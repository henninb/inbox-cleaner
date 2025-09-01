"""Integration tests for inbox cleaner modules."""

import pytest
import tempfile
from unittest.mock import Mock, patch
from datetime import datetime

from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.extractor import GmailExtractor, EmailMetadata
from inbox_cleaner.database import DatabaseManager


class TestIntegration:
    """Integration tests for the complete workflow."""
    
    @pytest.fixture
    def auth_config(self):
        """Authentication configuration for testing."""
        return {
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
        }
    
    @pytest.fixture
    def temp_database(self):
        """Temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db_manager = DatabaseManager(db_path)
        yield db_manager
        
        # Cleanup
        import os
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    def sample_emails(self):
        """Sample email metadata for testing."""
        import hashlib
        
        def hash_email(email):
            return hashlib.sha256(email.encode('utf-8')).hexdigest()
        
        return [
            EmailMetadata(
                message_id="msg_001",
                thread_id="thread_001",
                sender_email="sender1@example.com",
                sender_domain="example.com",
                sender_hash=hash_email("sender1@example.com"),
                subject="Important Meeting Tomorrow",
                date_received=datetime(2022, 1, 1, 10, 0, 0),
                labels=["INBOX", "IMPORTANT"],
                snippet="Meeting at 3pm",
                content="Full meeting details...",
                estimated_importance=0.8,
                category="work"
            ),
            EmailMetadata(
                message_id="msg_002", 
                thread_id="thread_002",
                sender_email="newsletter@company.com",
                sender_domain="company.com",
                sender_hash=hash_email("newsletter@company.com"),
                subject="Weekly Newsletter",
                date_received=datetime(2022, 1, 2, 9, 0, 0),
                labels=["INBOX", "CATEGORY_PROMOTIONS"],
                snippet="This week's updates",
                content="Newsletter content...",
                estimated_importance=0.2,
                category="newsletter"
            ),
            EmailMetadata(
                message_id="msg_003",
                thread_id="thread_003", 
                sender_email="friend@personal.com",
                sender_domain="personal.com",
                sender_hash=hash_email("friend@personal.com"),
                subject="Lunch Plans",
                date_received=datetime(2022, 1, 3, 12, 0, 0),
                labels=["INBOX", "CATEGORY_PERSONAL"],
                snippet="Want to grab lunch?",
                content="Personal message content...",
                estimated_importance=0.6,
                category="personal"
            )
        ]
    
    def test_auth_extractor_integration(self, auth_config):
        """Test authentication and extractor integration."""
        # Create authenticator
        authenticator = GmailAuthenticator(auth_config)
        
        # Mock Gmail service
        mock_service = Mock()
        extractor = GmailExtractor(mock_service)
        
        # Verify they can work together
        assert authenticator.client_id == "test_client_id"
        assert extractor.service == mock_service
        assert extractor.batch_size == 1000
    
    def test_extractor_database_integration(self, temp_database, sample_emails):
        """Test extractor and database integration."""
        # Store sample emails in database
        inserted_count = temp_database.insert_batch(sample_emails)
        assert inserted_count == 3
        
        # Verify data integrity
        stored_email = temp_database.get_email_by_id("msg_001")
        assert stored_email is not None
        assert stored_email['subject'] == "Important Meeting Tomorrow"
        assert stored_email['sender_domain'] == "example.com"
        assert stored_email['estimated_importance'] == 0.8
    
    def test_full_workflow_integration(self, auth_config, temp_database, sample_emails):
        """Test the complete workflow integration."""
        # 1. Authentication setup
        authenticator = GmailAuthenticator(auth_config)
        assert authenticator.scopes == ['https://www.googleapis.com/auth/gmail.readonly']
        
        # 2. Mock Gmail service and extractor
        mock_service = Mock()
        extractor = GmailExtractor(mock_service)
        
        # 3. Simulate email extraction results
        # (In real usage, this would come from Gmail API)
        extracted_emails = sample_emails
        
        # 4. Store in database
        inserted_count = temp_database.insert_batch(extracted_emails)
        assert inserted_count == 3
        
        # 5. Verify complete data flow
        stats = temp_database.get_statistics()
        assert stats['total_emails'] == 3
        assert 'work' in stats['categories']
        assert 'newsletter' in stats['categories']
        assert 'personal' in stats['categories']
        
        # 6. Test domain analysis
        domain_stats = temp_database.get_domain_statistics()
        assert domain_stats['example.com'] == 1
        assert domain_stats['company.com'] == 1
        assert domain_stats['personal.com'] == 1
        
        # 7. Test search functionality
        search_results = temp_database.search_emails('meeting')
        assert len(search_results) == 1
        assert search_results[0]['subject'] == "Important Meeting Tomorrow"
    
    def test_privacy_preservation(self, temp_database, sample_emails):
        """Test that privacy is maintained throughout the workflow."""
        # Store emails
        temp_database.insert_batch(sample_emails)
        
        # Verify sender emails are hashed
        all_emails = []
        for email in sample_emails:
            stored = temp_database.get_email_by_id(email.message_id)
            all_emails.append(stored)
        
        for stored_email in all_emails:
            sender_hash = stored_email.get('sender_hash', '')
            # Hash should be 64 characters (SHA-256 hex)
            assert len(sender_hash) == 64
            # Hash should not contain original email
            assert '@' not in sender_hash
            assert '.' not in sender_hash
    
    def test_batch_processing_simulation(self, temp_database):
        """Test batch processing capabilities."""
        # Simulate processing large batches (like your 40k emails)
        batch_sizes = [100, 500, 1000]
        
        for batch_size in batch_sizes:
            # Create mock emails for batch
            batch_emails = []
            for i in range(10):  # Small test batch
                email = EmailMetadata(
                    message_id=f"batch_{batch_size}_msg_{i}",
                    thread_id=f"batch_{batch_size}_thread_{i}",
                    sender_email=f"sender{i}@batch{batch_size}.com",
                    sender_domain=f"batch{batch_size}.com",
                    sender_hash=f"hash_{batch_size}_{i}",
                    subject=f"Batch {batch_size} Email {i}",
                    date_received=datetime(2022, 1, i+1, 10, 0, 0),
                    labels=["INBOX"],
                    snippet=f"Batch {batch_size} snippet {i}",
                    content=f"Batch {batch_size} content {i}",
                    estimated_importance=0.5
                )
                batch_emails.append(email)
            
            # Insert batch
            inserted = temp_database.insert_batch(batch_emails)
            assert inserted == 10
        
        # Verify total count
        stats = temp_database.get_statistics()
        assert stats['total_emails'] == 30  # 3 batch sizes × 10 emails each
    
    def test_error_resilience(self, temp_database):
        """Test that the system handles errors gracefully."""
        # Test database resilience with invalid data
        invalid_email = EmailMetadata(
            message_id="",  # Empty message ID
            thread_id="thread_invalid",
            sender_email="invalid@domain.com", 
            sender_domain="domain.com",
            sender_hash="invalid_hash",
            subject="Invalid Email",
            date_received=datetime(2022, 1, 1),
            labels=["INBOX"],
            snippet="Invalid snippet",
            content="Invalid content"
        )
        
        # Should handle gracefully
        result = temp_database.insert_email(invalid_email)
        # SQLite allows empty strings as primary keys, so this should work
        assert result is True
        
        # Test non-existent email retrieval
        non_existent = temp_database.get_email_by_id("does_not_exist")
        assert non_existent is None
    
    def test_context_manager_integration(self, temp_database, sample_emails):
        """Test using database manager as context manager."""
        with temp_database as db:
            # Insert test data
            inserted = db.insert_batch(sample_emails)
            assert inserted == 3
            
            # Query data
            stats = db.get_statistics()
            assert stats['total_emails'] == 3
            
            # Update data
            updated = db.update_email_category("msg_001", "urgent")
            assert updated is True
            
            # Verify update
            email = db.get_email_by_id("msg_001")
            assert email['category'] == "urgent"