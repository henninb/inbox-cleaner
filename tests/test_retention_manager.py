"""Comprehensive tests for retention manager business logic."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, timezone, timedelta
from pathlib import Path

from inbox_cleaner.retention_manager import RetentionManager, CategoryResult, USPS_EXPECTED_PATTERNS
from inbox_cleaner.auth import AuthenticationError


class TestRetentionManagerInit:
    """Test RetentionManager initialization and setup."""

    def test_init_default_retention_days(self):
        """Test default retention days is 30."""
        rm = RetentionManager()
        assert rm.retention_days == 30
        assert rm.service is None
        assert rm.db_path is None

    def test_init_custom_retention_days(self):
        """Test custom retention days."""
        rm = RetentionManager(retention_days=60)
        assert rm.retention_days == 60

    def test_cutoff_date_calculation(self):
        """Test cutoff date is calculated correctly."""
        with patch('inbox_cleaner.retention_manager.datetime') as mock_datetime:
            mock_now = datetime(2023, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            rm = RetentionManager(retention_days=30)
            expected_cutoff = mock_now - timedelta(days=30)
            assert rm.cutoff_date == expected_cutoff

    @patch('inbox_cleaner.retention_manager.Path.exists')
    def test_setup_services_no_config(self, mock_exists):
        """Test setup_services raises error when config doesn't exist."""
        mock_exists.return_value = False
        rm = RetentionManager()
        
        with pytest.raises(RuntimeError, match="config.yaml not found"):
            rm.setup_services()

    @patch('inbox_cleaner.retention_manager.Path.exists')
    @patch('inbox_cleaner.retention_manager.open', new_callable=mock_open)
    @patch('inbox_cleaner.retention_manager.yaml.safe_load')
    @patch('inbox_cleaner.retention_manager.GmailAuthenticator')
    @patch('inbox_cleaner.retention_manager.build')
    def test_setup_services_success(self, mock_build, mock_auth_class, mock_yaml, mock_file, mock_exists):
        """Test successful setup of services."""
        # Arrange
        mock_exists.return_value = True
        mock_config = {
            'gmail': {'client_id': 'test', 'client_secret': 'secret', 'scopes': ['scope']},
            'database': {'path': './test.db'}
        }
        mock_yaml.return_value = mock_config
        
        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_auth.get_valid_credentials.return_value = mock_credentials
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        rm = RetentionManager()
        
        # Act
        rm.setup_services()
        
        # Assert
        assert rm.service == mock_service
        assert rm.db_path == './test.db'
        mock_auth.get_valid_credentials.assert_called_once()
        mock_build.assert_called_once_with('gmail', 'v1', credentials=mock_credentials)

    @patch('inbox_cleaner.retention_manager.Path.exists')
    @patch('inbox_cleaner.retention_manager.open', new_callable=mock_open)
    @patch('inbox_cleaner.retention_manager.yaml.safe_load')
    @patch('inbox_cleaner.retention_manager.GmailAuthenticator')
    def test_setup_services_auth_failure(self, mock_auth_class, mock_yaml, mock_file, mock_exists):
        """Test setup_services handles authentication failure."""
        # Arrange
        mock_exists.return_value = True
        mock_config = {
            'gmail': {'client_id': 'test', 'client_secret': 'secret', 'scopes': ['scope']},
            'database': {'path': './test.db'}
        }
        mock_yaml.return_value = mock_config
        
        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_auth.get_valid_credentials.side_effect = AuthenticationError("Auth failed")
        
        rm = RetentionManager()
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Authentication failed: Auth failed"):
            rm.setup_services()


class TestRetentionManagerHelpers:
    """Test RetentionManager helper methods."""

    def test_parse_dt_valid_iso(self):
        """Test parsing valid ISO datetime."""
        rm = RetentionManager()
        dt_str = "2023-12-15T10:30:00Z"
        result = rm._parse_dt(dt_str)
        
        expected = datetime(2023, 12, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_dt_with_timezone(self):
        """Test parsing datetime with timezone."""
        rm = RetentionManager()
        dt_str = "2023-12-15T10:30:00+00:00"
        result = rm._parse_dt(dt_str)
        
        expected = datetime(2023, 12, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_dt_no_timezone_adds_utc(self):
        """Test parsing datetime without timezone adds UTC."""
        rm = RetentionManager()
        dt_str = "2023-12-15T10:30:00"
        result = rm._parse_dt(dt_str)
        
        expected = datetime(2023, 12, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_parse_dt_empty_returns_min(self):
        """Test parsing empty string returns datetime.min."""
        rm = RetentionManager()
        result = rm._parse_dt("")
        
        expected = datetime.min.replace(tzinfo=timezone.utc)
        assert result == expected

    def test_parse_dt_none_returns_min(self):
        """Test parsing None returns datetime.min."""
        rm = RetentionManager()
        result = rm._parse_dt(None)
        
        expected = datetime.min.replace(tzinfo=timezone.utc)
        assert result == expected

    def test_parse_dt_invalid_returns_min(self):
        """Test parsing invalid datetime returns datetime.min."""
        rm = RetentionManager()
        result = rm._parse_dt("invalid-datetime")
        
        expected = datetime.min.replace(tzinfo=timezone.utc)
        assert result == expected

    def test_split_recent_old_cutoff_logic(self):
        """Test split_recent_old correctly separates emails by cutoff date."""
        rm = RetentionManager(retention_days=30)
        
        # Create test emails with dates before and after cutoff
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(days=10)).isoformat()
        old_date = (now - timedelta(days=40)).isoformat()
        
        emails = [
            {'id': '1', 'date_received': recent_date, 'subject': 'Recent'},
            {'id': '2', 'date_received': old_date, 'subject': 'Old'},
            {'id': '3', 'date_received': recent_date, 'subject': 'Recent2'},
        ]
        
        result = rm._split_recent_old(emails)
        
        assert len(result.recent) == 2
        assert len(result.old) == 1
        assert result.recent[0]['subject'] == 'Recent'
        assert result.recent[1]['subject'] == 'Recent2'
        assert result.old[0]['subject'] == 'Old'

    def test_is_usps_expected_patterns(self):
        """Test USPS expected delivery pattern matching."""
        rm = RetentionManager()
        
        test_cases = [
            # Positive cases - with usps.com domain
            {'subject': 'USPS® Expected Delivery for your package', 'sender_email': 'test@usps.com', 'expected': True},
            {'subject': 'Expected Delivery Monday 2024 Between 2pm-6pm', 'sender_email': 'notify@usps.com', 'expected': True},
            {'subject': 'Expected Delivery arriving by 3pm', 'sender_email': 'test@usps.com', 'expected': True},
            {'subject': 'Package 1234567890123456789', 'sender_email': 'notify@usps.com', 'expected': True},
            
            # Positive cases - non-usps domain but USPS in subject
            {'subject': 'USPS delivery notification', 'sender_email': 'other@domain.com', 'expected': False},  # No matching pattern
            {'subject': 'USPS® Expected Delivery notice', 'sender_email': 'other@domain.com', 'expected': True},  # Has USPS® and pattern
            
            # Negative cases
            {'subject': 'Regular email', 'sender_email': 'test@gmail.com', 'expected': False},
            {'subject': 'Amazon delivery', 'sender_email': 'amazon@example.com', 'expected': False},
        ]
        
        for case in test_cases:
            email = {
                'subject': case['subject'],
                'sender_email': case['sender_email'],
                'sender_domain': case['sender_email'].split('@')[1] if '@' in case['sender_email'] else ''
            }
            result = rm._is_usps_expected(email)
            assert result == case['expected'], f"Failed for: {case['subject']}"

    def test_is_usps_expected_domain_variations(self):
        """Test USPS pattern matching with different domain formats."""
        rm = RetentionManager()
        
        # Test with sender_domain instead of sender_email
        email = {
            'subject': 'Regular subject',
            'sender_email': 'notify@informsdelivery.com',
            'sender_domain': 'usps.com'
        }
        # Should return False as neither sender nor domain contains usps.com and subject doesn't match patterns
        assert rm._is_usps_expected(email) == False
        
        # Test with USPS in subject but no domain match
        email = {
            'subject': 'USPS® Expected Delivery notice',
            'sender_email': 'test@example.com',
            'sender_domain': 'example.com'
        }
        # Should return True because subject contains USPS® and matches pattern
        assert rm._is_usps_expected(email) == True


class TestRetentionManagerDatabaseFinders:
    """Test database finder methods."""

    def test_db_find_no_db_path(self):
        """Test _db_find returns empty list when no db_path."""
        rm = RetentionManager()
        rm.db_path = None
        
        result = rm._db_find("test query")
        assert result == []

    @patch('inbox_cleaner.retention_manager.DatabaseManager')
    def test_db_find_success(self, mock_db_class):
        """Test _db_find returns database results."""
        rm = RetentionManager()
        rm.db_path = './test.db'
        
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_emails = [{'id': '1', 'subject': 'Test'}]
        mock_db.search_emails.return_value = mock_emails
        
        result = rm._db_find("test query")
        
        assert result == mock_emails
        mock_db.search_emails.assert_called_once_with("test query", per_page=100000)

    @patch.object(RetentionManager, '_db_find')
    def test_find_usps(self, mock_db_find):
        """Test find_usps calls _db_find with correct query."""
        rm = RetentionManager()
        mock_emails = [{'id': '1', 'sender_domain': 'usps.com'}]
        mock_db_find.return_value = mock_emails
        
        result = rm.find_usps()
        
        assert result == mock_emails
        mock_db_find.assert_called_once_with("usps.com")

    @patch.object(RetentionManager, '_db_find')
    def test_find_security_alerts_filtering(self, mock_db_find):
        """Test find_security_alerts filters candidates correctly."""
        rm = RetentionManager()
        
        candidates = [
            {
                'id': '1',
                'subject': 'Security alert on your account',
                'sender_email': 'no-reply@accounts.google.com',
                'sender_domain': 'accounts.google.com'
            },
            {
                'id': '2',
                'subject': 'Regular email',
                'sender_email': 'test@accounts.google.com',
                'sender_domain': 'accounts.google.com'
            },
            {
                'id': '3',
                'subject': 'Critical security alert detected',
                'sender_email': 'security@accounts.google.com',
                'sender_domain': 'accounts.google.com'
            }
        ]
        mock_db_find.return_value = candidates
        
        result = rm.find_security_alerts()
        
        # Should return emails with security alert keywords
        assert len(result) == 2
        assert result[0]['id'] == '1'
        assert result[1]['id'] == '3'
        mock_db_find.assert_called_once_with("accounts.google.com")

    @patch.object(RetentionManager, '_db_find')
    def test_find_hulu_filtering(self, mock_db_find):
        """Test find_hulu filters by domain correctly."""
        rm = RetentionManager()
        
        candidates = [
            {'id': '1', 'sender_email': 'promo@hulumail.com', 'sender_domain': 'hulumail.com'},
            {'id': '2', 'sender_email': 'test@example.com', 'sender_domain': 'example.com'},
            {'id': '3', 'sender_email': 'support@hulu.com', 'sender_domain': 'hulumail.com'},
        ]
        mock_db_find.return_value = candidates
        
        result = rm.find_hulu()
        
        # Should return emails from hulumail.com domain
        assert len(result) == 2
        assert result[0]['id'] == '1'
        assert result[1]['id'] == '3'

    @patch.object(RetentionManager, '_db_find')
    def test_find_privacy_exact_match(self, mock_db_find):
        """Test find_privacy requires exact email match."""
        rm = RetentionManager()
        
        candidates = [
            {'id': '1', 'sender_email': 'support@privacy.com'},
            {'id': '2', 'sender_email': 'noreply@privacy.com'},
            {'id': '3', 'sender_email': 'support@privacy.com'},
        ]
        mock_db_find.return_value = candidates
        
        result = rm.find_privacy()
        
        # Should return only emails from exact address
        assert len(result) == 2
        assert all(email['sender_email'] == 'support@privacy.com' for email in result)

    @patch.object(RetentionManager, '_db_find')
    def test_find_spotify_exact_match(self, mock_db_find):
        """Test find_spotify requires exact email match."""
        rm = RetentionManager()
        
        candidates = [
            {'id': '1', 'sender_email': 'no-reply@spotify.com'},
            {'id': '2', 'sender_email': 'support@spotify.com'},
            {'id': '3', 'sender_email': 'no-reply@spotify.com'},
        ]
        mock_db_find.return_value = candidates
        
        result = rm.find_spotify()
        
        # Should return only emails from exact address
        assert len(result) == 2
        assert all(email['sender_email'] == 'no-reply@spotify.com' for email in result)

    @patch.object(RetentionManager, '_db_find')
    def test_find_acorns_exact_match(self, mock_db_find):
        """Test find_acorns requires exact email match."""
        rm = RetentionManager()
        
        candidates = [
            {'id': '1', 'sender_email': 'info@notifications.acorns.com'},
            {'id': '2', 'sender_email': 'support@acorns.com'},
            {'id': '3', 'sender_email': 'info@notifications.acorns.com'},
        ]
        mock_db_find.return_value = candidates
        
        result = rm.find_acorns()
        
        # Should return only emails from exact address
        assert len(result) == 2
        assert all(email['sender_email'] == 'info@notifications.acorns.com' for email in result)

    @patch.object(RetentionManager, '_db_find')
    def test_find_va_exact_match(self, mock_db_find):
        """Test find_va requires exact email match."""
        rm = RetentionManager()
        
        candidates = [
            {'id': '1', 'sender_email': 'veteransaffairs@messages.va.gov'},
            {'id': '2', 'sender_email': 'support@va.gov'},
            {'id': '3', 'sender_email': 'veteransaffairs@messages.va.gov'},
        ]
        mock_db_find.return_value = candidates
        
        result = rm.find_va()
        
        # Should return only emails from exact address
        assert len(result) == 2
        assert all(email['sender_email'] == 'veteransaffairs@messages.va.gov' for email in result)


class TestRetentionManagerAnalysis:
    """Test analysis and cleanup methods."""

    def setup_method(self):
        """Setup test data for analysis tests."""
        self.rm = RetentionManager(retention_days=30)
        
        # Mock all finder methods
        self.usps_emails = [
            {'id': '1', 'subject': 'USPS delivery', 'date_received': '2023-12-01T10:00:00Z'},
            {'id': '2', 'subject': 'USPS old', 'date_received': '2023-10-01T10:00:00Z'}
        ]
        self.security_emails = [
            {'id': '3', 'subject': 'Security alert', 'date_received': '2023-12-01T10:00:00Z'}
        ]
        
    @patch.object(RetentionManager, 'find_usps')
    @patch.object(RetentionManager, 'find_security_alerts')
    @patch.object(RetentionManager, 'find_hulu')
    @patch.object(RetentionManager, 'find_privacy')
    @patch.object(RetentionManager, 'find_spotify')
    @patch.object(RetentionManager, 'find_acorns')
    @patch.object(RetentionManager, 'find_va')
    def test_analyze_all_categories(self, mock_va, mock_acorns, mock_spotify, mock_privacy,
                                   mock_hulu, mock_security, mock_usps):
        """Test analyze method calls all finders and splits results."""
        # Arrange
        mock_usps.return_value = self.usps_emails
        mock_security.return_value = self.security_emails
        mock_hulu.return_value = []
        mock_privacy.return_value = []
        mock_spotify.return_value = []
        mock_acorns.return_value = []
        mock_va.return_value = []
        
        # Act
        results = self.rm.analyze()
        
        # Assert
        assert 'usps' in results
        assert 'security' in results
        assert 'hulu' in results
        assert 'privacy' in results
        assert 'spotify' in results
        assert 'acorns' in results
        assert 'va' in results
        
        # Check that all finder methods were called
        mock_usps.assert_called_once()
        mock_security.assert_called_once()
        mock_hulu.assert_called_once()
        mock_privacy.assert_called_once()
        mock_spotify.assert_called_once()
        mock_acorns.assert_called_once()
        mock_va.assert_called_once()
        
        # Check that results are CategoryResult objects
        assert isinstance(results['usps'], CategoryResult)
        assert isinstance(results['security'], CategoryResult)

    @patch.object(RetentionManager, 'analyze')
    @patch('inbox_cleaner.retention_manager.DatabaseManager')
    def test_cleanup_db_dry_run(self, mock_db_class, mock_analyze):
        """Test cleanup_db in dry run mode."""
        # Arrange
        mock_results = {
            'usps': CategoryResult(recent=[], old=[{'id': '1', 'message_id': 'msg1'}]),
            'security': CategoryResult(recent=[], old=[{'id': '2', 'message_id': 'msg2'}]),
            'hulu': CategoryResult(recent=[], old=[]),
            'privacy': CategoryResult(recent=[], old=[]),
            'spotify': CategoryResult(recent=[], old=[]),
            'acorns': CategoryResult(recent=[], old=[]),
            'va': CategoryResult(recent=[], old=[])
        }
        mock_analyze.return_value = mock_results
        
        self.rm.db_path = './test.db'
        self.rm.service = Mock()
        
        # Act
        count, results = self.rm.cleanup_db(dry_run=True)
        
        # Assert
        assert count == 2  # 2 old emails total
        assert results == mock_results
        # Should not interact with Gmail API or database in dry run
        self.rm.service.users().messages().trash.assert_not_called()

    @patch.object(RetentionManager, 'analyze')
    @patch('inbox_cleaner.retention_manager.DatabaseManager')
    def test_cleanup_db_execute(self, mock_db_class, mock_analyze):
        """Test cleanup_db in execute mode."""
        # Arrange
        old_emails = [
            {'id': '1', 'message_id': 'msg1'},
            {'id': '2', 'message_id': 'msg2'}
        ]
        mock_results = {
            'usps': CategoryResult(recent=[], old=old_emails),
            'security': CategoryResult(recent=[], old=[]),
            'hulu': CategoryResult(recent=[], old=[]),
            'privacy': CategoryResult(recent=[], old=[]),
            'spotify': CategoryResult(recent=[], old=[]),
            'acorns': CategoryResult(recent=[], old=[]),
            'va': CategoryResult(recent=[], old=[])
        }
        mock_analyze.return_value = mock_results
        
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        self.rm.db_path = './test.db'
        self.rm.service = Mock()
        
        # Act
        count, results = self.rm.cleanup_db(dry_run=False)
        
        # Assert
        assert count == 2  # Successfully processed 2 emails
        # Should have called Gmail API to trash emails
        assert self.rm.service.users().messages().trash.call_count == 2
        # Should have called database to delete emails
        assert mock_db.delete_email.call_count == 2

    @patch.object(RetentionManager, 'analyze')
    @patch('inbox_cleaner.retention_manager.DatabaseManager')
    def test_cleanup_db_partial_failure(self, mock_db_class, mock_analyze):
        """Test cleanup_db handles partial failures gracefully."""
        # Arrange
        old_emails = [
            {'id': '1', 'message_id': 'msg1'},
            {'id': '2', 'message_id': 'msg2'}
        ]
        mock_results = {
            'usps': CategoryResult(recent=[], old=old_emails),
            'security': CategoryResult(recent=[], old=[]),
            'hulu': CategoryResult(recent=[], old=[]),
            'privacy': CategoryResult(recent=[], old=[]),
            'spotify': CategoryResult(recent=[], old=[]),
            'acorns': CategoryResult(recent=[], old=[]),
            'va': CategoryResult(recent=[], old=[])
        }
        mock_analyze.return_value = mock_results
        
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        self.rm.db_path = './test.db'
        self.rm.service = Mock()
        
        # Make first email fail, second succeed
        self.rm.service.users().messages().trash.side_effect = [
            Exception("API Error"),
            Mock()  # Success
        ]
        
        # Act
        count, results = self.rm.cleanup_db(dry_run=False)
        
        # Assert
        assert count == 1  # Only one succeeded
        assert self.rm.service.users().messages().trash.call_count == 2
        # Only one database deletion should succeed
        assert mock_db.delete_email.call_count == 1


class TestRetentionManagerCleanupLive:
    """Test live Gmail cleanup functionality."""

    def setup_method(self):
        """Setup for live cleanup tests."""
        self.rm = RetentionManager(retention_days=30)
        self.rm.service = Mock()

    def test_cleanup_live_collect_messages(self):
        """Test message collection from Gmail API."""
        # Mock Gmail API responses - need responses for all 7 categories (usps, security, hulu, privacy, spotify, acorns, va)
        # Each category makes at least one call, some may paginate
        self.rm.service.users().messages().list.return_value.execute.side_effect = [
            # USPS - with pagination
            {'messages': [{'id': 'msg1'}, {'id': 'msg2'}], 'nextPageToken': 'token1'},
            {'messages': [{'id': 'msg3'}]},  # No nextPageToken - end of pagination
            # Security alerts
            {'messages': [{'id': 'msg4'}]},
            # Hulu
            {'messages': []},
            # Privacy
            {'messages': [{'id': 'msg5'}]},
            # Spotify
            {'messages': []},
            # Acorns
            {'messages': []},
            # VA
            {'messages': []}
        ]
        
        # Act
        counts = self.rm.cleanup_live(dry_run=True, verbose=False)
        
        # Assert
        # Should have made API calls for all categories
        assert self.rm.service.users().messages().list.call_count >= 7  # One for each category
        assert counts['total'] > 0

    def test_cleanup_live_no_messages_found(self):
        """Test cleanup_live when no old messages found."""
        # Mock Gmail API to return no messages for all queries
        self.rm.service.users().messages().list.return_value.execute.return_value = {
            'messages': []
        }
        
        # Act
        counts = self.rm.cleanup_live(dry_run=False, verbose=False)
        
        # Assert
        assert counts['total'] == 0
        # Should not attempt batch modify
        self.rm.service.users().messages().batchModify.assert_not_called()

    def test_cleanup_live_execute_mode(self):
        """Test cleanup_live in execute mode moves messages to trash."""
        # Mock Gmail API responses
        self.rm.service.users().messages().list.return_value.execute.side_effect = [
            {'messages': [{'id': f'msg{i}'} for i in range(5)]},  # usps
            {'messages': []},  # security (no messages)
            {'messages': [{'id': 'msg6'}]},  # hulu
            {'messages': []},  # privacy
            {'messages': []},  # spotify  
            {'messages': []},  # acorns
            {'messages': []},  # va
        ]
        
        # Act
        counts = self.rm.cleanup_live(dry_run=False, verbose=False)
        
        # Assert
        assert counts['usps'] == 5
        assert counts['hulu'] == 1
        assert counts['total'] == 6
        # Should have called batchModify to move messages to trash
        self.rm.service.users().messages().batchModify.assert_called()

    def test_cleanup_live_batch_processing(self):
        """Test cleanup_live handles large batches correctly."""
        # Create 1000+ messages to test batching
        large_message_list = [{'id': f'msg{i}'} for i in range(1200)]
        
        self.rm.service.users().messages().list.return_value.execute.side_effect = [
            {'messages': large_message_list},  # usps
            {'messages': []},  # other categories empty
            {'messages': []},
            {'messages': []},
            {'messages': []},
            {'messages': []},
            {'messages': []},
        ]
        
        # Act
        counts = self.rm.cleanup_live(dry_run=False, verbose=False)
        
        # Assert
        assert counts['usps'] == 1200
        assert counts['total'] == 1200
        # Should have made multiple batch calls (1200 messages / 500 per batch = 3 batches)
        assert self.rm.service.users().messages().batchModify.call_count == 3

    def test_cleanup_live_handles_permission_error(self):
        """Test cleanup_live handles insufficient permissions gracefully."""
        # Mock messages found
        self.rm.service.users().messages().list.return_value.execute.side_effect = [
            {'messages': [{'id': 'msg1'}]},  # usps
            {'messages': []}, {'messages': []}, {'messages': []},  # others empty
            {'messages': []}, {'messages': []}, {'messages': []},
        ]
        
        # Mock permission error
        permission_error = Exception("insufficientPermissions: Insufficient Permission")
        self.rm.service.users().messages().batchModify.side_effect = permission_error
        
        # Act
        counts = self.rm.cleanup_live(dry_run=False, verbose=True)
        
        # Assert
        assert counts['total'] == 0  # No messages moved due to error
        self.rm.service.users().messages().batchModify.assert_called_once()


class TestRetentionManagerUtilities:
    """Test utility and helper methods."""

    def setup_method(self):
        """Setup for utility tests."""
        self.rm = RetentionManager()

    def test_format_email_line_complete_info(self):
        """Test _format_email_line with complete email information."""
        email = {
            'date_received': '2023-12-15T10:30:00Z',
            'sender_email': 'test@example.com',
            'subject': 'Test email subject'
        }
        
        result = self.rm._format_email_line(email)
        expected = "2023-12-15 | test@example.com | Test email subject"
        assert result == expected

    def test_format_email_line_long_subject_truncation(self):
        """Test _format_email_line truncates long subjects."""
        long_subject = "This is a very long email subject that should be truncated because it exceeds the maximum allowed length for display purposes"
        email = {
            'date_received': '2023-12-15T10:30:00Z',
            'sender_email': 'test@example.com',
            'subject': long_subject
        }
        
        result = self.rm._format_email_line(email)
        assert result.endswith('...')
        assert len(result.split('|')[2].strip()) <= 100

    def test_format_email_line_missing_fields(self):
        """Test _format_email_line handles missing fields gracefully."""
        email = {
            'sender_domain': 'example.com',
            'subject': 'Test'
        }
        
        result = self.rm._format_email_line(email)
        assert 'example.com' in result
        assert 'Test' in result

    @patch.object(RetentionManager, 'analyze')
    def test_print_kept_summary(self, mock_analyze):
        """Test print_kept_summary displays categories correctly."""
        # Arrange
        mock_results = {
            'usps': CategoryResult(
                recent=[
                    {'date_received': '2023-12-15T10:00:00Z', 'sender_email': 'test@usps.com', 'subject': 'USPS delivery'},
                    {'date_received': '2023-12-14T10:00:00Z', 'sender_email': 'notify@usps.com', 'subject': 'Package update'}
                ],
                old=[]
            ),
            'security': CategoryResult(recent=[], old=[]),
            'hulu': CategoryResult(recent=[], old=[]),
            'privacy': CategoryResult(recent=[], old=[]),
            'spotify': CategoryResult(recent=[], old=[]),
            'acorns': CategoryResult(recent=[], old=[]),
            'va': CategoryResult(recent=[], old=[])
        }
        mock_analyze.return_value = mock_results
        
        # Act & Assert - mainly testing it doesn't crash
        # Since this method prints to stdout, we mainly test it executes successfully
        self.rm.print_kept_summary()
        mock_analyze.assert_called_once()

    @patch.object(RetentionManager, 'analyze')
    @patch('inbox_cleaner.retention_manager.DatabaseManager')
    def test_cleanup_orphaned_emails_no_old_emails(self, mock_db_class, mock_analyze):
        """Test cleanup_orphaned_emails when no old emails exist."""
        # Arrange
        mock_results = {category: CategoryResult(recent=[], old=[]) for category in ['usps', 'security', 'hulu', 'privacy', 'spotify', 'acorns', 'va']}
        mock_analyze.return_value = mock_results
        
        self.rm.db_path = './test.db'
        
        # Act
        result = self.rm.cleanup_orphaned_emails(verbose=False)
        
        # Assert
        assert result == 0
        # Should not interact with Gmail API
        assert not hasattr(self.rm, 'service') or self.rm.service is None

    @patch.object(RetentionManager, 'analyze')
    @patch('inbox_cleaner.retention_manager.DatabaseManager')
    def test_cleanup_orphaned_emails_removes_missing(self, mock_db_class, mock_analyze):
        """Test cleanup_orphaned_emails removes emails not found in Gmail."""
        # Arrange
        old_emails = [
            {'message_id': 'msg1', 'subject': 'Old email 1'},
            {'message_id': 'msg2', 'subject': 'Old email 2'},
            {'message_id': 'msg3', 'subject': 'Old email 3'},
        ]
        mock_results = {
            'usps': CategoryResult(recent=[], old=old_emails),
            'security': CategoryResult(recent=[], old=[]),
            'hulu': CategoryResult(recent=[], old=[]),
            'privacy': CategoryResult(recent=[], old=[]),
            'spotify': CategoryResult(recent=[], old=[]),
            'acorns': CategoryResult(recent=[], old=[]),
            'va': CategoryResult(recent=[], old=[])
        }
        mock_analyze.return_value = mock_results
        
        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        
        self.rm.db_path = './test.db'
        self.rm.service = Mock()
        
        # Mock Gmail API responses - msg1 and msg3 exist, msg2 doesn't
        def gmail_get_side_effect(userId, id):
            if id == 'msg2':
                raise Exception("Not Found: 404")
            return Mock()  # Email exists
        
        self.rm.service.users().messages().get.side_effect = gmail_get_side_effect
        
        # Act
        result = self.rm.cleanup_orphaned_emails(verbose=False)
        
        # Assert
        assert result == 1  # Only msg2 should be removed
        assert self.rm.service.users().messages().get.call_count == 3
        mock_db.delete_email.assert_called_once_with('msg2')

    def test_cleanup_orphaned_emails_no_db_path(self):
        """Test cleanup_orphaned_emails returns 0 when no db_path set."""
        self.rm.db_path = None
        
        result = self.rm.cleanup_orphaned_emails()
        assert result == 0


class TestRetentionManagerEdgeCases:
    """Test edge cases and error scenarios."""

    def test_usps_patterns_comprehensive(self):
        """Test all USPS_EXPECTED_PATTERNS work correctly."""
        rm = RetentionManager()
        
        # Test each pattern individually
        pattern_tests = [
            "USPS® Package Expected Delivery",
            "Expected Delivery Monday 2024 Between 2pm-6pm", 
            "Expected Delivery arriving by 3pm today",
            "Tracking: 1234567890123456789 - package info"
        ]
        
        for subject in pattern_tests:
            email = {
                'subject': subject,
                'sender_email': 'test@usps.com',
                'sender_domain': 'usps.com'
            }
            assert rm._is_usps_expected(email), f"Pattern should match: {subject}"

    def test_security_alerts_keyword_variations(self):
        """Test security alert keyword matching variations."""
        rm = RetentionManager()
        
        test_cases = [
            {'subject': 'Security Alert: New device sign-in', 'expected': True},
            {'subject': 'Critical Security Alert on your account', 'expected': True},
            {'subject': 'New sign-in from Chrome on Windows', 'expected': True},
            {'subject': 'Suspicious sign-in prevented', 'expected': True},
            {'subject': 'Account security notification', 'expected': False},  # Not in keyword list
            {'subject': 'Regular email', 'expected': False}
        ]
        
        for case in test_cases:
            candidates = [{
                'subject': case['subject'],
                'sender_email': 'no-reply@accounts.google.com',
                'sender_domain': 'accounts.google.com'
            }]
            
            with patch.object(rm, '_db_find', return_value=candidates):
                result = rm.find_security_alerts()
                if case['expected']:
                    assert len(result) == 1, f"Should match: {case['subject']}"
                else:
                    assert len(result) == 0, f"Should not match: {case['subject']}"

    def test_empty_email_data_handling(self):
        """Test handling of emails with missing or empty data."""
        rm = RetentionManager()
        
        # Test with minimal email data
        minimal_email = {'id': '1'}
        result = rm._is_usps_expected(minimal_email)
        assert result == False
        
        # Test date parsing with missing date
        result = rm._split_recent_old([minimal_email])
        assert len(result.old) == 1  # Should go to old due to missing date -> datetime.min

    @patch('inbox_cleaner.retention_manager.yaml.safe_load')
    @patch('inbox_cleaner.retention_manager.open', new_callable=mock_open)
    @patch('inbox_cleaner.retention_manager.Path.exists')
    def test_config_loading_edge_cases(self, mock_exists, mock_file, mock_yaml):
        """Test configuration loading with various edge cases."""
        mock_exists.return_value = True
        
        # Test with malformed YAML
        mock_yaml.side_effect = Exception("YAML parse error")
        rm = RetentionManager()
        
        with pytest.raises(Exception):
            rm.setup_services()
            
        # Test with missing required config sections
        mock_yaml.side_effect = None
        mock_yaml.return_value = {'invalid': 'config'}
        
        with pytest.raises(KeyError):
            rm.setup_services()