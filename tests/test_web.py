"""Tests for web interface module."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path

from inbox_cleaner.database import DatabaseManager


class TestWebApp:
    """Test web application setup and basic functionality."""

    def test_app_creation(self):
        """Test that FastAPI app can be created."""
        from inbox_cleaner.web import create_app

        app = create_app()
        assert app is not None
        assert hasattr(app, 'router')

    def test_health_check_endpoint(self):
        """Test health check endpoint returns 200."""
        from inbox_cleaner.web import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_root_redirect_to_dashboard(self):
        """Test root path redirects to dashboard."""
        from inbox_cleaner.web import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard" in response.headers["location"]


class TestEmailAPI:
    """Test email listing and management API endpoints."""

    @pytest.fixture
    def test_db(self):
        """Create temporary test database."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name

        # Create test database with sample data
        with DatabaseManager(db_path) as db:
            # Add sample emails for testing
            from inbox_cleaner.extractor import EmailMetadata
            from datetime import datetime

            sample_email = EmailMetadata(
                message_id="test_123",
                thread_id="thread_123",
                sender_email="test@example.com",
                sender_domain="example.com",
                sender_hash="hash123",
                subject="Test Email",
                date_received=datetime.now(),
                labels=["INBOX"],
                snippet="Test snippet"
            )
            db.insert_email(sample_email)

        yield db_path
        os.unlink(db_path)

    def test_email_list_api_endpoint(self, test_db):
        """Test email list API returns paginated results."""
        from inbox_cleaner.web import create_app

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/api/emails")
        assert response.status_code == 200

        data = response.json()
        assert "emails" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert isinstance(data["emails"], list)

    def test_email_list_pagination(self, test_db):
        """Test email list supports pagination parameters."""
        from inbox_cleaner.web import create_app

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/api/emails?page=1&per_page=10")
        assert response.status_code == 200

        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 10

    def test_email_search_api(self, test_db):
        """Test email search functionality."""
        from inbox_cleaner.web import create_app

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/api/emails/search?q=test")
        assert response.status_code == 200

        data = response.json()
        assert "emails" in data
        assert "query" in data
        assert data["query"] == "test"


class TestWebPages:
    """Test HTML template rendering."""

    @pytest.fixture
    def test_db(self):
        """Create temporary test database."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name

        with DatabaseManager(db_path) as db:
            pass  # Empty database for testing

        yield db_path
        os.unlink(db_path)

    def test_dashboard_page_renders(self, test_db):
        """Test dashboard page renders with email statistics."""
        from inbox_cleaner.web import create_app

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Inbox Cleaner" in response.content

    def test_email_list_page_renders(self, test_db):
        """Test email list page renders with pagination."""
        from inbox_cleaner.web import create_app

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/emails")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Email List" in response.content

    def test_search_page_renders(self, test_db):
        """Test search page renders correctly."""
        from inbox_cleaner.web import create_app

        app = create_app(db_path=test_db)
        client = TestClient(app)

        response = client.get("/search")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Search Emails" in response.content


class TestConfigurationIntegration:
    """Test web app integrates with configuration system."""

    def test_app_uses_config_database_path(self):
        """Test app uses database path from configuration."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name

        with DatabaseManager(db_path) as db:
            pass

        from inbox_cleaner.web import create_app
        app = create_app(db_path=db_path)

        assert app is not None

        os.unlink(db_path)

    def test_app_handles_missing_database(self):
        """Test app handles missing database gracefully."""
        from inbox_cleaner.web import create_app

        # Should not raise exception even with non-existent database
        app = create_app(db_path="/nonexistent/path.db")
        assert app is not None