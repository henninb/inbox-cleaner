"""Tests for email deletion functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from datetime import datetime
from pathlib import Path

from inbox_cleaner.database import DatabaseManager
from inbox_cleaner.extractor import EmailMetadata


class TestSpamRuleManager:
    """Test spam rule management system."""

    def test_spam_rule_creation(self):
        """Test creating spam rules."""
        from inbox_cleaner.spam_rules import SpamRuleManager

        rule_manager = SpamRuleManager()

        # Create a domain-based rule
        rule = rule_manager.create_domain_rule(
            domain="m.jabra.com",
            action="delete",
            reason="Excessive promotional emails"
        )

        assert rule["domain"] == "m.jabra.com"
        assert rule["action"] == "delete"
        assert rule["type"] == "domain"
        assert "rule_id" in rule

    def test_spam_rule_matching(self):
        """Test spam rule matching against emails."""
        from inbox_cleaner.spam_rules import SpamRuleManager

        rule_manager = SpamRuleManager()

        # Create rules
        rule_manager.create_domain_rule("m.jabra.com", "delete", "Spam")
        rule_manager.create_subject_rule("URGENT.*ACT NOW", "delete", "Phishing pattern")

        # Test email matching
        jabra_email = {
            "sender_domain": "m.jabra.com",
            "subject": "New headphones available"
        }

        phishing_email = {
            "sender_domain": "example.com",
            "subject": "URGENT: ACT NOW to save your account"
        }

        legitimate_email = {
            "sender_domain": "legitimate.com",
            "subject": "Normal email"
        }

        assert rule_manager.matches_spam_rule(jabra_email) is not None
        assert rule_manager.matches_spam_rule(phishing_email) is not None
        assert rule_manager.matches_spam_rule(legitimate_email) is None

    def test_spam_rule_persistence(self):
        """Test saving and loading spam rules."""
        from inbox_cleaner.spam_rules import SpamRuleManager

        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            rules_file = tmp.name

        try:
            # Create rules and save
            rule_manager = SpamRuleManager(rules_file=rules_file)
            rule_manager.create_domain_rule("spam.com", "delete", "Test rule")
            rule_manager.save_rules()

            # Load in new instance
            new_manager = SpamRuleManager(rules_file=rules_file)
            new_manager.load_rules()

            rules = new_manager.get_all_rules()
            assert len(rules) == 1
            assert rules[0]["domain"] == "spam.com"

        finally:
            os.unlink(rules_file)


class TestEmailDeletion:
    """Test email deletion from Gmail and database."""

    @pytest.fixture
    def test_db_with_emails(self):
        """Create test database with sample emails."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name

        with DatabaseManager(db_path) as db:
            # Add emails including some from m.jabra.com
            emails = [
                EmailMetadata(
                    message_id="jabra_1",
                    thread_id="jabra_1",
                    sender_email="promo@m.jabra.com",
                    sender_domain="m.jabra.com",
                    sender_hash="hash_jabra1",
                    subject="New headphones available!",
                    date_received=datetime.now(),
                    labels=["INBOX", "CATEGORY_PROMOTIONS"],
                    snippet="Check out our latest wireless headphones."
                ),
                EmailMetadata(
                    message_id="jabra_2",
                    thread_id="jabra_2",
                    sender_email="sales@m.jabra.com",
                    sender_domain="m.jabra.com",
                    sender_hash="hash_jabra2",
                    subject="50% off everything!",
                    date_received=datetime.now(),
                    labels=["INBOX", "CATEGORY_PROMOTIONS"],
                    snippet="Limited time offer on all products."
                ),
                EmailMetadata(
                    message_id="legit_1",
                    thread_id="legit_1",
                    sender_email="important@company.com",
                    sender_domain="company.com",
                    sender_hash="hash_legit1",
                    subject="Important meeting tomorrow",
                    date_received=datetime.now(),
                    labels=["INBOX", "IMPORTANT"],
                    snippet="Don't forget about the team meeting."
                )
            ]

            for email in emails:
                db.insert_email(email)

        yield db_path
        os.unlink(db_path)

    def test_gmail_email_deletion(self):
        """Test deleting emails from Gmail via API."""
        from inbox_cleaner.deletion import EmailDeletionManager

        # Mock Gmail service
        mock_service = Mock()
        mock_service.users().messages().delete().execute.return_value = {}

        deleter = EmailDeletionManager(gmail_service=mock_service, db_path="test.db")

        # Test deleting single email
        result = deleter.delete_from_gmail("message_123")
        assert result is True

        # Verify API was called correctly
        mock_service.users().messages().delete.assert_called_with(
            userId='me', id='message_123'
        )

    def test_database_email_deletion(self, test_db_with_emails):
        """Test deleting emails from local database."""
        from inbox_cleaner.deletion import EmailDeletionManager

        deleter = EmailDeletionManager(gmail_service=None, db_path=test_db_with_emails)

        # Test deleting single email
        result = deleter.delete_from_database("jabra_1")
        assert result is True

        # Verify email was deleted from database
        with DatabaseManager(test_db_with_emails) as db:
            email = db.get_email_by_id("jabra_1")
            assert email is None

    def test_bulk_deletion_by_domain(self, test_db_with_emails):
        """Test bulk deletion of emails by domain."""
        from inbox_cleaner.deletion import EmailDeletionManager

        # Mock Gmail service for bulk deletion
        mock_service = Mock()
        mock_service.users().messages().delete().execute.return_value = {}

        deleter = EmailDeletionManager(gmail_service=mock_service, db_path=test_db_with_emails)

        # Test bulk deletion of m.jabra.com emails
        results = deleter.delete_emails_by_domain("m.jabra.com", dry_run=False)

        assert results["total_found"] == 2
        assert results["gmail_deleted"] == 2
        assert results["database_deleted"] == 2
        assert len(results["failed"]) == 0

        # Verify emails were deleted from database
        with DatabaseManager(test_db_with_emails) as db:
            jabra_emails = db.get_emails_by_domain("m.jabra.com")
            assert len(jabra_emails) == 0

            # Verify legitimate emails remain
            other_emails = db.get_emails_by_domain("company.com")
            assert len(other_emails) == 1

    def test_dry_run_deletion(self, test_db_with_emails):
        """Test dry run mode for deletion preview."""
        from inbox_cleaner.deletion import EmailDeletionManager

        deleter = EmailDeletionManager(gmail_service=None, db_path=test_db_with_emails)

        # Test dry run
        results = deleter.delete_emails_by_domain("m.jabra.com", dry_run=True)

        assert results["total_found"] == 2
        assert results["gmail_deleted"] == 0  # No actual deletion in dry run
        assert results["database_deleted"] == 0
        assert "would_delete" in results
        assert len(results["would_delete"]) == 2

        # Verify no emails were actually deleted
        with DatabaseManager(test_db_with_emails) as db:
            jabra_emails = db.get_emails_by_domain("m.jabra.com")
            assert len(jabra_emails) == 2

    def test_deletion_error_handling(self):
        """Test error handling during deletion."""
        from inbox_cleaner.deletion import EmailDeletionManager

        # Mock Gmail service that throws errors
        mock_service = Mock()
        mock_service.users().messages().delete().execute.side_effect = Exception("API Error")

        deleter = EmailDeletionManager(gmail_service=mock_service, db_path="nonexistent.db")

        # Test single deletion with error
        result = deleter.delete_from_gmail("message_123")
        assert result is False


class TestSpamRuleWebAPI:
    """Test web API endpoints for spam rule management."""

    @pytest.fixture
    def test_db(self):
        """Create test database."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name

        with DatabaseManager(db_path) as db:
            # Add sample email
            sample_email = EmailMetadata(
                message_id="test_1",
                thread_id="test_1",
                sender_email="test@m.jabra.com",
                sender_domain="m.jabra.com",
                sender_hash="hash_test1",
                subject="Test Email",
                date_received=datetime.now(),
                labels=["INBOX"],
                snippet="Test snippet"
            )
            db.insert_email(sample_email)

        yield db_path
        os.unlink(db_path)

    def test_spam_rules_api_endpoints(self, test_db):
        """Test spam rules API endpoints."""
        from inbox_cleaner.web import create_app
        from fastapi.testclient import TestClient

        # Create temporary rules file for test isolation
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            rules_file = tmp.name

        try:
            # Patch SpamRuleManager to use temp file
            with patch('inbox_cleaner.web.SpamRuleManager') as mock_rule_manager_class:
                mock_rule_manager = Mock()
                mock_rule_manager_class.return_value = mock_rule_manager

                # Mock the rule creation
                test_rule = {
                    "rule_id": "test-rule-id",
                    "domain": "m.jabra.com",
                    "action": "delete",
                    "reason": "Excessive promotional emails",
                    "type": "domain",
                    "active": True
                }
                mock_rule_manager.create_domain_rule.return_value = test_rule
                mock_rule_manager.get_all_rules.return_value = [test_rule]
                mock_rule_manager.get_deletion_stats.return_value = {"total_rules": 1}

                app = create_app(db_path=test_db)
                client = TestClient(app)

                # Test creating spam rule
                rule_data = {
                    "domain": "m.jabra.com",
                    "action": "delete",
                    "reason": "Excessive promotional emails"
                }

                response = client.post("/api/spam-rules", json=rule_data)
                assert response.status_code == 201

                rule = response.json()
                assert rule["domain"] == "m.jabra.com"
                assert rule["action"] == "delete"

                # Test getting all rules
                response = client.get("/api/spam-rules")
                assert response.status_code == 200

                rules = response.json()
                assert len(rules["rules"]) == 1

        finally:
            os.unlink(rules_file)

    def test_bulk_deletion_api_endpoint(self, test_db):
        """Test bulk deletion API endpoint."""
        from inbox_cleaner.web import create_app
        from fastapi.testclient import TestClient

        app = create_app(db_path=test_db)
        client = TestClient(app)

        # Test bulk deletion by domain
        deletion_data = {
            "domain": "m.jabra.com",
            "dry_run": True
        }

        response = client.post("/api/delete/domain", json=deletion_data)
        assert response.status_code == 200

        result = response.json()
        assert result["total_found"] > 0
        assert "would_delete" in result

    def test_spam_rules_web_page(self, test_db):
        """Test spam rules management web page."""
        from inbox_cleaner.web import create_app
        from fastapi.testclient import TestClient

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/spam-rules")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Spam Rules" in response.content