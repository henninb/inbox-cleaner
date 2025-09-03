# tests/test_retention.py
import pytest
from unittest.mock import mock_open, patch
import yaml

# This will fail until the new module is created
import pytest
from unittest.mock import mock_open, patch, MagicMock
import yaml

from inbox_cleaner.retention import RetentionConfig, RetentionRule, GmailRetentionManager, RetentionAnalysis


class TestRetentionConfig:
    def test_load_from_config(self):
        """
        Test that RetentionConfig correctly loads and parses rules
        from a dictionary representing config.yaml.
        """
        config_data = {
            'retention_rules': [
                {
                    'domain': 'usps.com',
                    'retention_days': 7,
                    'description': 'USPS delivery notifications'
                },
                {
                    'sender': 'no-reply@spotify.com',
                    'retention_days': 30
                },
                {
                    'domain': 'accounts.google.com',
                    'retention_days': 90,
                    'subject_contains': ['security alert', 'sign-in'],
                    'description': 'Google security alerts'
                }
            ]
        }

        retention_config = RetentionConfig(config_data)
        rules = retention_config.get_rules()

        assert len(rules) == 3

        # Check the first rule
        assert rules[0].domain == 'usps.com'
        assert rules[0].retention_days == 7
        assert rules[0].description == 'USPS delivery notifications'
        assert rules[0].sender is None
        assert rules[0].subject_contains is None

        # Check the second rule (with defaults)
        assert rules[1].sender == 'no-reply@spotify.com'
        assert rules[1].retention_days == 30
        assert rules[1].description == '' # Default value
        assert rules[1].domain is None

        # Check the third rule
        assert rules[2].domain == 'accounts.google.com'
        assert rules[2].subject_contains == ['security alert', 'sign-in']

    def test_generate_gmail_query(self):
        """
        Test that the correct Gmail query is generated from a RetentionRule.
        """
        # Rule 1: Simple domain rule
        rule1 = RetentionRule(domain="usps.com", retention_days=7)
        query1 = RetentionConfig.generate_gmail_query(rule1)
        assert 'from:usps.com' in query1
        assert 'older_than:7d' in query1
        assert '-in:spam' in query1
        assert '-in:trash' in query1

        # Rule 2: Sender rule with subject
        rule2 = RetentionRule(
            sender="no-reply@spotify.com",
            retention_days=30,
            subject_contains=["your weekly playlist", "new music"]
        )
        query2 = RetentionConfig.generate_gmail_query(rule2)
        assert 'from:no-reply@spotify.com' in query2
        assert 'older_than:30d' in query2
        assert 'subject:"your weekly playlist"' in query2
        assert 'subject:"new music"' in query2
        assert '(subject:"your weekly playlist" OR subject:"new music")' in query2

        # Rule 3: Rule with default retention
        rule3 = RetentionRule(domain="hulumail.com")
        query3 = RetentionConfig.generate_gmail_query(rule3)
        assert 'older_than:30d' in query3


class TestGmailRetentionManager:
    @patch('inbox_cleaner.retention.build')
    @patch('inbox_cleaner.retention.GmailAuthenticator')
    def test_analyze_retention_searches_gmail(self, mock_auth_class, mock_build):
        """
        Test that analyze_retention uses RetentionConfig to search for emails.
        """
        # Arrange
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        mock_auth.get_valid_credentials.return_value = MagicMock()

        config_data = {
            'retention_rules': [
                {'domain': 'usps.com', 'retention_days': 7},
                {'sender': 'no-reply@spotify.com', 'retention_days': 30}
            ]
        }
        retention_config = RetentionConfig(config_data)

        # Mock the Gmail API response without making a call
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}]
        }

        # Act
        manager = GmailRetentionManager(retention_config, gmail_config={})
        analysis = manager.analyze_retention()

        # Assert
        assert mock_build.called
        assert mock_auth_class.called

        list_mock = mock_service.users.return_value.messages.return_value.list
        assert list_mock.call_count == 2

        # Check that the correct queries were used
        calls = list_mock.call_args_list
        expected_query1 = RetentionConfig.generate_gmail_query(retention_config.get_rules()[0])
        expected_query2 = RetentionConfig.generate_gmail_query(retention_config.get_rules()[1])

        called_queries = [call.kwargs['q'] for call in calls]
        assert expected_query1 in called_queries
        assert expected_query2 in called_queries

        # Check that the analysis result contains the found messages
        rule1_key = retention_config.get_rules()[0].domain
        assert rule1_key in analysis
        assert analysis[rule1_key].messages_found == 2

    @patch('inbox_cleaner.retention.GmailAuthenticator')
    def test_cleanup_old_emails_calls_batch_modify(self, mock_auth_class):
        """
        Test that cleanup_old_emails uses the analysis result to trash emails in a batch.
        """
        # Arrange
        mock_service = MagicMock()
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        mock_auth.get_valid_credentials.return_value = MagicMock()

        config_data = {'retention_rules': [{'domain': 'usps.com', 'retention_days': 7}]}
        retention_config = RetentionConfig(config_data)

        # We can pass the service directly for this test
        manager = GmailRetentionManager(retention_config, gmail_config={}, service=mock_service)

        # Create mock analysis results
        rule = retention_config.get_rules()[0]
        analysis_results = {
            'usps.com': RetentionAnalysis(
                rule=rule,
                messages_found=2,
                messages=[{'id': 'msg1'}, {'id': 'msg2'}]
            )
        }

        # Act
        cleanup_summary = manager.cleanup_old_emails(analysis_results)

        # Assert
        batch_modify_mock = mock_service.users().messages().batchModify
        assert batch_modify_mock.call_count == 1

        call_args = batch_modify_mock.call_args
        assert call_args.kwargs['body']['ids'] == ['msg1', 'msg2']
        assert 'TRASH' in call_args.kwargs['body']['addLabelIds']

        # Check summary
        assert 'usps.com' in cleanup_summary
        assert cleanup_summary['usps.com'] == 2

    def test_load_with_overrides(self):
        """Test that retention days are correctly overridden."""
        config_data = {
            'retention_rules': [
                {'domain': 'usps.com', 'retention_days': 7},
                {'sender': 'no-reply@spotify.com', 'retention_days': 30}
            ]
        }
        overrides = {'usps.com': 3, 'unrelated.com': 10}

        retention_config = RetentionConfig(config_data, overrides=overrides)
        rules = retention_config.get_rules()

        assert rules[0].retention_days == 3  # Overridden
        assert rules[1].retention_days == 30 # Not overridden

    @patch('inbox_cleaner.retention.build')
    @patch('inbox_cleaner.retention.GmailAuthenticator')
    def test_manager_instantiates_auth_with_config(self, mock_auth_class, mock_build):
        """
        Test that GmailRetentionManager instantiates GmailAuthenticator with the correct config.
        """
        # Arrange
        mock_build.return_value = MagicMock()
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        mock_auth.get_valid_credentials.return_value = MagicMock()

        retention_config = RetentionConfig({})
        gmail_config = {'client_id': 'test_id'}

        # Act
        manager = GmailRetentionManager(retention_config, gmail_config=gmail_config)

        # Assert
        mock_auth_class.assert_called_once_with(gmail_config)

    def test_print_retained_emails_shows_kept_messages(self):
        """
        Test that print_retained_emails displays information about kept emails.
        """
        # Mock config for retention manager
        config_data = {
            'retention_rules': [
                {'domain': 'usps.com', 'retention_days': 7},
                {'sender': 'no-reply@spotify.com', 'retention_days': 30}
            ]
        }
        retention_config = RetentionConfig(config_data)

        # Mock service
        mock_service = MagicMock()
        manager = GmailRetentionManager(retention_config, gmail_config={}, service=mock_service)

        # Mock analysis results with some retained (recent) emails
        mock_analysis = {
            'usps.com': RetentionAnalysis(
                rule=retention_config.get_rules()[0],
                messages_found=3,
                messages=[
                    {'id': 'msg1', 'subject': 'Package Delivered', 'sender': 'usps@usps.com', 'date_received': '2023-12-01T10:00:00Z'},
                    {'id': 'msg2', 'subject': 'Expected Delivery Today', 'sender': 'usps@usps.com', 'date_received': '2023-12-02T10:00:00Z'},
                    {'id': 'msg3', 'subject': 'Package in Transit', 'sender': 'usps@usps.com', 'date_received': '2023-12-03T10:00:00Z'}
                ]
            ),
            'no-reply@spotify.com': RetentionAnalysis(
                rule=retention_config.get_rules()[1],
                messages_found=1,
                messages=[
                    {'id': 'msg4', 'subject': 'Your Weekly Playlist', 'sender': 'no-reply@spotify.com', 'date_received': '2023-12-04T10:00:00Z'}
                ]
            )
        }

        # Test that the method should exist and can be called
        assert hasattr(manager, 'print_retained_emails'), "print_retained_emails method should exist"

        # The method should accept analysis results and print information about them
        # We'll implement this to match the retention_manager.py pattern
        with patch('builtins.print') as mock_print:
            manager.print_retained_emails(mock_analysis)

            # Verify that print was called (indicating emails were displayed)
            assert mock_print.called

    def test_sync_with_database_removes_orphaned_emails(self):
        """
        Test that sync_with_database removes emails from database that no longer exist in Gmail.
        """
        config_data = {'retention_rules': [{'domain': 'usps.com', 'retention_days': 7}]}
        retention_config = RetentionConfig(config_data)

        mock_service = MagicMock()
        manager = GmailRetentionManager(retention_config, gmail_config={}, service=mock_service)

        # Mock database manager
        mock_db = MagicMock()

        # Mock some emails that exist in database but not in Gmail (orphaned)
        orphaned_emails = [
            {'message_id': 'orphaned1', 'subject': 'Old Email 1'},
            {'message_id': 'orphaned2', 'subject': 'Old Email 2'},
            {'message_id': 'existing1', 'subject': 'Still Exists'}
        ]

        # Mock Gmail API to return 404 for orphaned emails, 200 for existing
        def gmail_get_side_effect(*args, **kwargs):
            msg_id = kwargs.get('id', '')
            if 'orphaned' in msg_id:
                from googleapiclient.errors import HttpError
                raise HttpError(resp=MagicMock(status=404), content=b'Not Found')
            return {'id': msg_id}

        mock_service.users().messages().get.side_effect = gmail_get_side_effect

        # Test that the method should exist and can be called
        assert hasattr(manager, 'sync_with_database'), "sync_with_database method should exist"

        with patch('inbox_cleaner.retention.DatabaseManager') as mock_db_class:
            mock_db_instance = MagicMock()
            mock_db_class.return_value.__enter__.return_value = mock_db_instance

            # Mock the database to return our test emails
            mock_db_instance.search_emails.return_value = orphaned_emails

            # Call sync method
            removed_count = manager.sync_with_database(mock_db_instance)

            # Verify orphaned emails were deleted from database
            # Should delete 2 orphaned emails, keep 1 existing
            assert removed_count == 2

            # Verify delete_email was called for orphaned messages
            delete_calls = mock_db_instance.delete_email.call_args_list
            assert len(delete_calls) == 2
            assert any(call[0][0] == 'orphaned1' for call in delete_calls)
            assert any(call[0][0] == 'orphaned2' for call in delete_calls)

    @patch('inbox_cleaner.retention.build')
    @patch('inbox_cleaner.retention.GmailAuthenticator')
    def test_analyze_retained_emails_searches_for_newer_emails(self, mock_auth_class, mock_build):
        """
        Test that analyze_retained_emails searches for emails NEWER than retention days.
        """
        # Arrange
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_auth = MagicMock()
        mock_auth_class.return_value = mock_auth
        mock_auth.get_valid_credentials.return_value = MagicMock()

        config_data = {
            'retention_rules': [
                {'domain': 'usps.com', 'retention_days': 7},
                {'sender': 'no-reply@spotify.com', 'retention_days': 30}
            ]
        }
        retention_config = RetentionConfig(config_data)

        # Mock the Gmail API response
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            'messages': [{'id': 'retained1'}, {'id': 'retained2'}]
        }

        # Act
        manager = GmailRetentionManager(retention_config, gmail_config={})
        retained_results = manager.analyze_retained_emails()

        # Assert
        list_mock = mock_service.users.return_value.messages.return_value.list
        assert list_mock.call_count == 2

        # Check that the queries use "newer_than" instead of "older_than"
        calls = list_mock.call_args_list
        for call in calls:
            query = call.kwargs['q']
            assert 'newer_than:' in query
            assert 'older_than:' not in query
            assert '-in:spam -in:trash' in query

        # Check that retained results are returned
        assert 'usps.com' in retained_results
        assert 'no-reply@spotify.com' in retained_results
        assert retained_results['usps.com'].messages_found == 2
