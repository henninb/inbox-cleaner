"""Tests for email analysis module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path

from inbox_cleaner.database import DatabaseManager
from inbox_cleaner.extractor import EmailMetadata


class TestEmailAnalyzer:
    """Test email analysis functionality."""

    @pytest.fixture
    def test_db_with_emails(self):
        """Create test database with sample emails."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        with DatabaseManager(db_path) as db:
            # Add sample emails with different characteristics
            emails = [
                # Spam/phishing samples
                EmailMetadata(
                    message_id="spam_1",
                    thread_id="spam_1",
                    sender_email="noreply@suspicious-bank.com",
                    sender_domain="suspicious-bank.com",
                    sender_hash="hash_spam1",
                    subject="URGENT: Your account will be suspended!!! Click now!!!",
                    date_received=datetime.now(),
                    labels=["INBOX"],
                    snippet="Your account has suspicious activity. Click here immediately.",
                    category="promotional"
                ),
                # Legitimate emails
                EmailMetadata(
                    message_id="legit_1",
                    thread_id="legit_1", 
                    sender_email="notifications@usps.com",
                    sender_domain="usps.com",
                    sender_hash="hash_legit1",
                    subject="Your package will be delivered today",
                    date_received=datetime.now(),
                    labels=["INBOX", "IMPORTANT"],
                    snippet="Track your package delivery.",
                    category="personal"
                ),
                # Old USPS email (should be flagged for deletion)
                EmailMetadata(
                    message_id="old_usps",
                    thread_id="old_usps",
                    sender_email="info@email.informeddelivery.usps.com", 
                    sender_domain="email.informeddelivery.usps.com",
                    sender_hash="hash_old",
                    subject="Informed Delivery Daily Digest",
                    date_received=datetime.now() - timedelta(days=45),
                    labels=["INBOX"],
                    snippet="Your daily mail preview.",
                    category="updates"
                ),
                # Promotional emails
                EmailMetadata(
                    message_id="promo_1",
                    thread_id="promo_1",
                    sender_email="sales@target.com",
                    sender_domain="target.com", 
                    sender_hash="hash_promo1",
                    subject="50% off everything! Limited time!",
                    date_received=datetime.now(),
                    labels=["INBOX", "CATEGORY_PROMOTIONS"],
                    snippet="Shop now for amazing deals.",
                    category="promotional"
                ),
                # Social emails
                EmailMetadata(
                    message_id="social_1",
                    thread_id="social_1",
                    sender_email="notifications@facebook.com",
                    sender_domain="facebook.com",
                    sender_hash="hash_social1", 
                    subject="John Doe liked your post",
                    date_received=datetime.now(),
                    labels=["INBOX", "CATEGORY_SOCIAL"],
                    snippet="See what's happening with your friends.",
                    category="social"
                )
            ]
            
            for email in emails:
                db.insert_email(email)
        
        yield db_path
        os.unlink(db_path)

    def test_spam_phishing_detection(self, test_db_with_emails):
        """Test spam and phishing email detection."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        suspicious_emails = analyzer.detect_suspicious_emails()
        
        assert len(suspicious_emails) > 0
        assert any("suspicious-bank.com" in email["sender_domain"] for email in suspicious_emails)
        
        # Check for spam indicators
        spam_indicators = analyzer.get_spam_indicators()
        assert "urgent_language" in spam_indicators
        assert "suspicious_domains" in spam_indicators

    def test_domain_distribution_analysis(self, test_db_with_emails):
        """Test email domain distribution analysis."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        domain_stats = analyzer.get_domain_distribution()
        
        assert isinstance(domain_stats, dict)
        assert len(domain_stats) > 0
        
        # Should include our test domains
        domain_names = list(domain_stats.keys())
        assert "usps.com" in domain_names
        assert "target.com" in domain_names

    def test_category_analysis(self, test_db_with_emails):
        """Test email category analysis.""" 
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        category_stats = analyzer.get_category_analysis()
        
        assert "promotional" in category_stats
        assert "social" in category_stats
        assert "personal" in category_stats
        
        # Should have counts for each category
        assert category_stats["promotional"]["count"] > 0
        assert category_stats["social"]["count"] > 0

    def test_cleanup_recommendations(self, test_db_with_emails):
        """Test automated cleanup recommendations."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        recommendations = analyzer.get_cleanup_recommendations()
        
        assert "expired_emails" in recommendations
        assert "spam_candidates" in recommendations
        assert "bulk_promotional" in recommendations
        
        # Should find old USPS emails for deletion
        expired = recommendations["expired_emails"]
        assert len(expired) > 0
        assert any("informeddelivery.usps.com" in email["sender_domain"] for email in expired)

    def test_detailed_statistics(self, test_db_with_emails):
        """Test comprehensive email statistics."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        stats = analyzer.get_detailed_statistics()
        
        # Should include all key metrics
        assert "total_emails" in stats
        assert "label_distribution" in stats
        assert "domain_distribution" in stats
        assert "category_breakdown" in stats
        assert "time_distribution" in stats
        assert "suspicious_count" in stats

    def test_usps_email_expiration_rules(self, test_db_with_emails):
        """Test USPS email expiration logic."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        expired_usps = analyzer.get_expired_usps_emails(days_to_keep=30)
        
        assert len(expired_usps) > 0
        # Should find the 45-day old USPS email
        cutoff = datetime.now() - timedelta(days=30)
        assert any(datetime.fromisoformat(email["date_received"]) < cutoff
                  for email in expired_usps)

    def test_promotional_email_analysis(self, test_db_with_emails):
        """Test promotional email analysis and recommendations."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        promo_analysis = analyzer.analyze_promotional_emails()
        
        assert "total_promotional" in promo_analysis
        assert "top_domains" in promo_analysis
        assert "recommendations" in promo_analysis
        assert promo_analysis["total_promotional"] > 0

    def test_social_email_analysis(self, test_db_with_emails):
        """Test social email analysis."""
        from inbox_cleaner.analysis import EmailAnalyzer
        
        analyzer = EmailAnalyzer(test_db_with_emails)
        social_analysis = analyzer.analyze_social_emails()
        
        assert "total_social" in social_analysis
        assert "platforms" in social_analysis
        assert social_analysis["total_social"] > 0


class TestAnalysisWebEndpoints:
    """Test web API endpoints for email analysis."""

    @pytest.fixture
    def test_db_with_emails(self):
        """Create test database with sample emails."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            db_path = tmp.name
        
        with DatabaseManager(db_path) as db:
            # Add sample data for web testing
            sample_email = EmailMetadata(
                message_id="web_test_1",
                thread_id="web_test_1",
                sender_email="test@example.com",
                sender_domain="example.com",
                sender_hash="hash_web1",
                subject="Test Email",
                date_received=datetime.now(),
                labels=["INBOX"],
                snippet="Test snippet"
            )
            db.insert_email(sample_email)
        
        yield db_path
        os.unlink(db_path)

    def test_analysis_api_endpoint(self, test_db_with_emails):
        """Test analysis API endpoint returns proper data."""
        from inbox_cleaner.web import create_app
        from fastapi.testclient import TestClient
        
        app = create_app(db_path=test_db_with_emails)
        client = TestClient(app)
        
        response = client.get("/api/analysis")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_emails" in data
        assert "suspicious_count" in data
        assert "domain_distribution" in data
        assert "cleanup_recommendations" in data

    def test_analysis_dashboard_page(self, test_db_with_emails):
        """Test analysis dashboard page renders correctly."""
        from inbox_cleaner.web import create_app
        from fastapi.testclient import TestClient
        
        app = create_app(db_path=test_db_with_emails)
        client = TestClient(app)
        
        response = client.get("/analysis")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"Email Analysis" in response.content

    def test_cleanup_recommendations_endpoint(self, test_db_with_emails):
        """Test cleanup recommendations API endpoint."""
        from inbox_cleaner.web import create_app
        from fastapi.testclient import TestClient
        
        app = create_app(db_path=test_db_with_emails)
        client = TestClient(app)
        
        response = client.get("/api/analysis/cleanup")
        assert response.status_code == 200
        
        data = response.json()
        assert "expired_emails" in data
        assert "spam_candidates" in data
        assert "recommendations" in data