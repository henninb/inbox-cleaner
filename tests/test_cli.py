"""Tests for CLI functionality following TDD principles."""

import pytest
import yaml
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, ANY
from pathlib import Path
from click.testing import CliRunner

from inbox_cleaner.cli import main
from inbox_cleaner.auth import AuthenticationError


class TestCLIFilters:
    """Test CLI filter management functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_list_filters_command_success(self, mock_engine, mock_build, mock_auth,
                                        mock_yaml, mock_open, mock_exists):
        """Test successful list-filters command."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_filters = [
            {
                'id': 'filter1',
                'criteria': {'from': 'spam@example.com'},
                'action': {'addLabelIds': ['TRASH']}
            },
            {
                'id': 'filter2',
                'criteria': {'from': 'test@domain.com'},
                'action': {'addLabelIds': ['INBOX']}
            }
        ]

        mock_engine_instance = Mock()
        mock_engine_instance.list_existing_filters.return_value = mock_filters
        mock_engine.return_value = mock_engine_instance

        # Act
        result = self.runner.invoke(main, ['list-filters'])

        # Assert
        assert result.exit_code == 0
        assert 'filter1' in result.output
        assert 'spam@example.com' in result.output
        assert 'Auto-delete' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_list_filters_command_no_config(self, mock_exists):
        """Test list-filters command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['list-filters'])

        # Assert
        assert result.exit_code != 0
        assert 'config.yaml not found' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_list_filters_command_auth_error(self, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test list-filters command when authentication fails."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_auth.return_value.get_valid_credentials.side_effect = AuthenticationError("Auth failed")

        # Act
        result = self.runner.invoke(main, ['list-filters'])

        # Assert
        assert result.exit_code != 0
        assert 'Authentication failed' in result.output


class TestCLIDeleteEmails:
    """Test CLI email deletion functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_delete_emails_command_dry_run(self, mock_engine, mock_db, mock_build,
                                          mock_auth, mock_yaml, mock_open, mock_exists):
        """Test delete-emails command in dry run mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_engine_instance = Mock()
        mock_result = {
            'steps': [
                {
                    'step': 'delete_existing',
                    'success': True,
                    'result': {
                        'found_count': 5,
                        'deleted_count': 0  # Dry run
                    }
                }
            ]
        }
        mock_engine_instance.unsubscribe_and_block_domain.return_value = mock_result
        mock_engine.return_value = mock_engine_instance

        # Act
        result = self.runner.invoke(main, ['delete-emails', '--domain', 'spam.com', '--dry-run'])

        # Assert
        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
        assert 'Would delete 5' in result.output
        mock_engine_instance.unsubscribe_and_block_domain.assert_called_with('spam.com', dry_run=True)

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_delete_emails_command_execute(self, mock_engine, mock_db, mock_build,
                                          mock_auth, mock_yaml, mock_open, mock_exists):
        """Test delete-emails command in execute mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_engine_instance = Mock()
        mock_result = {
            'steps': [
                {
                    'step': 'delete_existing',
                    'success': True,
                    'result': {
                        'found_count': 5,
                        'deleted_count': 5
                    }
                }
            ]
        }
        mock_engine_instance.unsubscribe_and_block_domain.return_value = mock_result
        mock_engine.return_value = mock_engine_instance

        # Act
        result = self.runner.invoke(main, ['delete-emails', '--domain', 'spam.com', '--execute'])

        # Assert
        assert result.exit_code == 0
        assert 'Deleted 5' in result.output
        mock_engine_instance.unsubscribe_and_block_domain.assert_called_with('spam.com', dry_run=False)

    def test_delete_emails_command_no_domain(self):
        """Test delete-emails command without domain parameter."""
        # Act
        result = self.runner.invoke(main, ['delete-emails', '--dry-run'])

        # Assert
        assert result.exit_code != 0
        assert 'Missing option' in result.output


class TestCLIFindUnsubscribe:
    """Test CLI unsubscribe link finding functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_find_unsubscribe_command_success(self, mock_engine, mock_db, mock_build,
                                            mock_auth, mock_yaml, mock_open, mock_exists):
        """Test successful find-unsubscribe command."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_engine_instance = Mock()
        mock_unsubscribe_info = [
            {
                'subject': 'Test Newsletter',
                'unsubscribe_links': [
                    'https://example.com/unsubscribe?email=test@example.com',
                    'mailto:unsubscribe@example.com'
                ]
            }
        ]
        mock_engine_instance.find_unsubscribe_links.return_value = mock_unsubscribe_info
        mock_engine.return_value = mock_engine_instance

        # Act
        result = self.runner.invoke(main, ['find-unsubscribe', '--domain', 'example.com'])

        # Assert
        assert result.exit_code == 0
        assert 'Test Newsletter' in result.output
        assert 'https://example.com/unsubscribe' in result.output
        assert 'mailto:unsubscribe@example.com' in result.output
        mock_engine_instance.find_unsubscribe_links.assert_called_once_with('example.com')

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_find_unsubscribe_command_no_links(self, mock_engine, mock_db, mock_build,
                                              mock_auth, mock_yaml, mock_open, mock_exists):
        """Test find-unsubscribe command when no links are found."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_engine_instance = Mock()
        mock_engine_instance.find_unsubscribe_links.return_value = []
        mock_engine.return_value = mock_engine_instance

        # Act
        result = self.runner.invoke(main, ['find-unsubscribe', '--domain', 'example.com'])

        # Assert
        assert result.exit_code == 0
        assert 'No unsubscribe links found' in result.output

    def test_find_unsubscribe_command_no_domain(self):
        """Test find-unsubscribe command without domain parameter."""
        # Act
        result = self.runner.invoke(main, ['find-unsubscribe'])

        # Assert
        assert result.exit_code != 0
        assert 'Missing option' in result.output


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()

    def test_main_command_help(self):
        """Test main command shows help."""
        # Act
        result = self.runner.invoke(main, ['--help'])

        # Assert
        assert result.exit_code == 0
        assert 'Gmail Inbox Cleaner' in result.output
        assert 'list-filters' in result.output
        assert 'delete-emails' in result.output
        assert 'find-unsubscribe' in result.output

    def test_list_filters_help(self):
        """Test list-filters command help."""
        # Act
        result = self.runner.invoke(main, ['list-filters', '--help'])

        # Assert
        assert result.exit_code == 0
        assert 'List existing Gmail filters' in result.output

    def test_delete_emails_help(self):
        """Test delete-emails command help."""
        # Act
        result = self.runner.invoke(main, ['delete-emails', '--help'])

        # Assert
        assert result.exit_code == 0
        assert 'Delete emails from specified domain' in result.output
        assert '--domain' in result.output
        assert '--dry-run' in result.output
        assert '--execute' in result.output

    def test_find_unsubscribe_help(self):
        """Test find-unsubscribe command help."""
        # Act
        result = self.runner.invoke(main, ['find-unsubscribe', '--help'])

        # Assert
        assert result.exit_code == 0
        assert 'Find unsubscribe links' in result.output
        assert '--domain' in result.output


class TestCLIRetentionCommand:
    """Test CLI retention command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config_data = {
            'retention_rules': [
                {'domain': 'usps.com', 'retention_days': 7},
                {'sender': 'no-reply@spotify.com', 'retention_days': 30}
            ]
        }

    @patch('inbox_cleaner.cli.Path.exists', return_value=True)
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailRetentionManager')
    def test_retention_analyze(self, mock_manager_class, mock_yaml, mock_open, mock_exists):
        """Test retention command with analyze."""
        mock_yaml.return_value = self.mock_config_data
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.analyze_retention.return_value = {
            'usps.com': MagicMock(messages_found=5),
            'no-reply@spotify.com': MagicMock(messages_found=10)
        }

        result = self.runner.invoke(main, ['retention', '--analyze'])

        assert result.exit_code == 0
        assert "Analyzing email retention" in result.output
        assert "Found 15 emails" in result.output
        assert "usps.com: 5 emails" in result.output

    @patch('inbox_cleaner.cli.Path.exists', return_value=True)
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailRetentionManager')
    def test_retention_cleanup_dry_run(self, mock_manager_class, mock_yaml, mock_open, mock_exists):
        """Test retention cleanup in dry-run mode."""
        mock_yaml.return_value = self.mock_config_data
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.cleanup_old_emails.return_value = {'usps.com': 5}
        mock_manager.analyze_retention.return_value = {}

        result = self.runner.invoke(main, ['retention', '--cleanup', '--dry-run'])

        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.output
        assert "Cleaned up 5 emails" in result.output
        mock_manager.cleanup_old_emails.assert_called_once_with(ANY, dry_run=True)

    @patch('inbox_cleaner.cli.Path.exists', return_value=True)
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.RetentionConfig')
    @patch('inbox_cleaner.cli.GmailRetentionManager')
    def test_retention_with_override(self, mock_manager_class, mock_config_class, mock_yaml, mock_open, mock_exists):
        """Test retention command with override."""
        mock_yaml.return_value = self.mock_config_data
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        result = self.runner.invoke(main, ['retention', '--override', 'usps.com:3'])

        assert result.exit_code == 0

        # Check that RetentionConfig was called with the override
        mock_config_class.assert_called_once_with(self.mock_config_data, overrides={'usps.com': 3})


class TestCLIMarkReadCommand:
    """Test CLI mark-read command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_mark_read_dry_run_default(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test mark-read command in default dry-run mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        # Mock Gmail API responses
        mock_service.users().messages().list().execute.side_effect = [
            {'messages': [{'id': '1'}, {'id': '2'}]},
            {}  # Empty response to stop pagination
        ]

        # Act
        result = self.runner.invoke(main, ['mark-read'])

        # Assert
        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
        assert 'Would mark 2 messages as read' in result.output
        mock_service.users().messages().batchModify.assert_not_called()

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_mark_read_execute_mode(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test mark-read command in execute mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        # Mock Gmail API responses
        mock_service.users().messages().list().execute.side_effect = [
            {'messages': [{'id': '1'}, {'id': '2'}]},
            {}  # Empty response to stop pagination
        ]

        # Act
        result = self.runner.invoke(main, ['mark-read', '--execute'])

        # Assert
        assert result.exit_code == 0
        assert 'EXECUTE' in result.output
        assert 'Marked 2 messages as read' in result.output
        mock_service.users().messages().batchModify.assert_called_once()

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_mark_read_with_custom_query(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test mark-read command with custom query."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_service.users().messages().list().execute.return_value = {}

        # Act
        result = self.runner.invoke(main, ['mark-read', '--query', 'from:spam@example.com'])

        # Assert
        assert result.exit_code == 0
        assert 'from:spam@example.com' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_mark_read_with_limit(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test mark-read command with limit parameter."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_service.users().messages().list().execute.return_value = {
            'messages': [{'id': str(i)} for i in range(10)]
        }

        # Act
        result = self.runner.invoke(main, ['mark-read', '--limit', '5'])

        # Assert
        assert result.exit_code == 0

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_mark_read_auth_error(self, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test mark-read command when authentication fails."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_auth.return_value.get_valid_credentials.side_effect = AuthenticationError("Auth failed")

        # Act
        result = self.runner.invoke(main, ['mark-read'])

        # Assert
        assert result.exit_code == 0
        assert 'Authentication failed' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_mark_read_no_config(self, mock_exists):
        """Test mark-read command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['mark-read'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml not found' in result.output


class TestCLISpamCleanupCommand:
    """Test CLI spam-cleanup command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.SpamRuleManager')
    def test_spam_cleanup_setup_rules(self, mock_spam_rules_class):
        """Test spam-cleanup command with setup-rules option."""
        # Arrange
        mock_spam_rules = Mock()
        mock_spam_rules_class.return_value = mock_spam_rules

        mock_rules = [
            {'type': 'domain', 'pattern': 'spam.com', 'reason': 'Known spam domain'},
            {'type': 'subject', 'pattern': 'FREE MONEY', 'reason': 'Suspicious subject'}
        ]
        mock_spam_rules.create_predefined_spam_rules.return_value = mock_rules

        # Act
        result = self.runner.invoke(main, ['spam-cleanup', '--setup-rules'])

        # Assert
        assert result.exit_code == 0
        assert 'Setting up predefined spam rules' in result.output
        assert 'Created 2 spam detection rules' in result.output
        assert 'spam.com' in result.output
        assert 'FREE MONEY' in result.output
        mock_spam_rules.save_rules.assert_called()

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.SpamRuleManager')
    def test_spam_cleanup_analyze(self, mock_spam_rules_class, mock_db_class, mock_build,
                                 mock_auth, mock_yaml, mock_open, mock_exists):
        """Test spam-cleanup command with analyze option."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_emails = [
            {'sender': 'spam@test.com', 'subject': 'Free money!'},
            {'sender': 'legit@company.com', 'subject': 'Newsletter'}
        ]
        mock_db.search_emails.return_value = mock_emails

        mock_spam_rules = Mock()
        mock_spam_rules_class.return_value = mock_spam_rules

        mock_analysis = {
            'total_emails': 2,
            'suspicious_emails': [
                {
                    'spam_score': 5,
                    'sender': 'spam@test.com',
                    'subject': 'Free money!',
                    'indicators': ['urgent_language']
                }
            ],
            'spam_indicators': {
                'ip_in_sender': 0,
                'misspelled_subjects': 0,
                'prize_scams': 1,
                'urgent_language': 1,
                'suspicious_domains': ['test.com']
            },
            'suggested_rules': [
                {'type': 'domain', 'pattern': 'test.com', 'reason': 'High spam activity'}
            ]
        }
        mock_spam_rules.analyze_spam_patterns.return_value = mock_analysis

        # Act
        result = self.runner.invoke(main, ['spam-cleanup', '--analyze'])

        # Assert
        assert result.exit_code == 0
        assert 'Analyzing last 1000 emails' in result.output
        assert 'Total emails analyzed: 2' in result.output
        assert 'Suspicious emails found: 1' in result.output
        assert 'spam@test.com' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_spam_cleanup_no_config(self, mock_exists):
        """Test spam-cleanup command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['spam-cleanup'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml not found' in result.output


class TestCLICreateSpamFiltersCommand:
    """Test CLI create-spam-filters command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_create_spam_filters_dry_run(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test create-spam-filters command in dry-run mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        # Mock existing filters response
        mock_service.users().settings().filters().list().execute.return_value = {
            'filter': []  # No existing filters
        }

        # Act
        result = self.runner.invoke(main, ['create-spam-filters', '--dry-run'])

        # Assert
        assert result.exit_code == 0
        assert 'DRY RUN' in result.output
        assert 'eleganceaffairs.com' in result.output or 'Free Spins' in result.output
        mock_service.users().settings().filters().create.assert_not_called()

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_create_spam_filters_execute(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test create-spam-filters command in execute mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        # Mock existing filters response
        mock_service.users().settings().filters().list().execute.return_value = {
            'filter': []  # No existing filters
        }

        # Act
        result = self.runner.invoke(main, ['create-spam-filters', '--execute'])

        # Assert
        assert result.exit_code == 0
        assert 'Created' in result.output
        # Should have made filter creation calls
        assert mock_service.users().settings().filters().create.call_count > 0

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    def test_create_spam_filters_no_new_filters(self, mock_build, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test create-spam-filters when all filters already exist."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        # Mock response with many existing filters to match all desired ones
        # Need to create comprehensive list to match the logic in CLI
        existing_filters = []
        # Add all spam domains from the CLI code
        spam_domains = [
            'eleganceaffairs.com', 'speedytype.com', 'mineralsbid.com', 'fp8888.com',
            'pets-tiara.com', 'koidor.com', 'delmedicogroup.com', 'aksuhaliyikama.us.com'
        ]
        subject_keywords = [
            'Free Spins', 'Your Email Has Been Chosen', 'YourVip-Pass',
            'Important Update - MUST SEE', 'Congratulations', 'Millionaire',
            'Million to win', 'WinnersList', 'Instant-Millionaire', 'BonusOnHold'
        ]

        for domain in spam_domains:
            existing_filters.append({
                'criteria': {'from': domain},
                'action': {'addLabelIds': ['TRASH']}
            })

        for keyword in subject_keywords:
            existing_filters.append({
                'criteria': {'query': f'subject:"{keyword}"'},
                'action': {'addLabelIds': ['TRASH']}
            })

        mock_service.users().settings().filters().list().execute.return_value = {
            'filter': existing_filters
        }

        # Act
        result = self.runner.invoke(main, ['create-spam-filters'])

        # Assert
        assert result.exit_code == 0
        assert 'No new spam filters to create' in result.output


class TestCLIApplyFiltersCommand:
    """Test CLI apply-filters command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_apply_filters_dry_run(self, mock_engine_class, mock_db_class, mock_build,
                                  mock_auth, mock_yaml, mock_open, mock_exists):
        """Test apply-filters command in dry-run mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        mock_result = {
            'processed_filters': 3,
            'total_deleted': 15
        }
        mock_engine.apply_filters.return_value = mock_result

        # Act
        result = self.runner.invoke(main, ['apply-filters', '--dry-run'])

        # Assert
        assert result.exit_code == 0
        assert 'DRY RUN MODE' in result.output
        assert 'Processed 3 auto-delete filters' in result.output
        assert 'Would delete 15 emails' in result.output
        mock_engine.apply_filters.assert_called_once_with(dry_run=True)

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.DatabaseManager')
    @patch('inbox_cleaner.cli.UnsubscribeEngine')
    def test_apply_filters_execute(self, mock_engine_class, mock_db_class, mock_build,
                                  mock_auth, mock_yaml, mock_open, mock_exists):
        """Test apply-filters command in execute mode."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        mock_result = {
            'processed_filters': 2,
            'total_deleted': 8
        }
        mock_engine.apply_filters.return_value = mock_result

        # Act
        result = self.runner.invoke(main, ['apply-filters', '--execute'])

        # Assert
        assert result.exit_code == 0
        assert 'EXECUTE MODE' in result.output
        assert 'Deleted 8 emails' in result.output
        mock_engine.apply_filters.assert_called_once_with(dry_run=False)


class TestCLIAuthCommand:
    """Test CLI auth command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_auth_setup_success(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test auth command with setup option successful."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_auth.authenticate.return_value = mock_credentials

        # Act
        result = self.runner.invoke(main, ['auth', '--setup'])

        # Assert
        assert result.exit_code == 0
        assert 'Setting up OAuth2 authentication' in result.output
        assert 'Authentication successful' in result.output
        mock_auth.authenticate.assert_called_once()

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_auth_setup_failure(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test auth command with setup option when authentication fails."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_auth.authenticate.side_effect = AuthenticationError("OAuth failed")

        # Act
        result = self.runner.invoke(main, ['auth', '--setup'])

        # Assert
        assert result.exit_code == 0
        assert 'Authentication failed: OAuth failed' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_auth_status_valid(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test auth command with status option when credentials are valid."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_auth.load_credentials.return_value = mock_credentials

        # Act
        result = self.runner.invoke(main, ['auth', '--status'])

        # Assert
        assert result.exit_code == 0
        assert 'Valid credentials found' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_auth_status_expired(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test auth command with status option when credentials are expired."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_auth.load_credentials.return_value = mock_credentials

        # Act
        result = self.runner.invoke(main, ['auth', '--status'])

        # Assert
        assert result.exit_code == 0
        assert 'Credentials expired' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_auth_default_behavior(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test auth command with no options (default behavior)."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_auth.load_credentials.return_value = mock_credentials

        # Act
        result = self.runner.invoke(main, ['auth'])

        # Assert
        assert result.exit_code == 0
        assert 'Authentication valid' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_auth_no_config(self, mock_exists):
        """Test auth command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['auth'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml not found' in result.output


class TestCLISyncCommand:
    """Test CLI sync command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.GmailExtractor')
    @patch('inbox_cleaner.cli.DatabaseManager')
    def test_sync_initial(self, mock_db_class, mock_extractor_class, mock_build,
                         mock_auth, mock_yaml, mock_open, mock_exists):
        """Test sync command with initial option."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        mock_emails = [{'id': '1'}, {'id': '2'}]
        mock_extractor.extract_all.return_value = mock_emails

        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.get_statistics.return_value = {'total_emails': 2}

        # Act
        result = self.runner.invoke(main, ['sync', '--initial'])

        # Assert
        assert result.exit_code == 0
        assert 'Starting initial sync' in result.output
        assert 'Extracted 2 emails' in result.output
        assert 'Database now contains 2 emails' in result.output
        mock_extractor.extract_all.assert_called_once()

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.build')
    @patch('inbox_cleaner.cli.GmailExtractor')
    @patch('inbox_cleaner.cli.DatabaseManager')
    def test_sync_with_limit(self, mock_db_class, mock_extractor_class, mock_build,
                            mock_auth, mock_yaml, mock_open, mock_exists):
        """Test sync command with limit parameter."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_credentials = Mock()
        mock_auth.return_value.get_valid_credentials.return_value = mock_credentials

        mock_service = Mock()
        mock_build.return_value = mock_service

        mock_extractor = Mock()
        mock_extractor_class.return_value = mock_extractor
        mock_emails = [{'id': str(i)} for i in range(5)]
        mock_extractor.extract_all.return_value = mock_emails

        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.get_statistics.return_value = {'total_emails': 5}

        # Act
        result = self.runner.invoke(main, ['sync', '--limit', '5'])

        # Assert
        assert result.exit_code == 0
        # The limit only shows in initial sync, not regular sync
        assert 'Extracted 5 emails' in result.output
        # Check that extract_all was called with max_results parameter
        call_args = mock_extractor.extract_all.call_args
        assert call_args.kwargs.get('max_results') == 5

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_sync_auth_failure(self, mock_auth, mock_yaml, mock_open, mock_exists):
        """Test sync command when authentication fails."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_auth.return_value.get_valid_credentials.side_effect = AuthenticationError("Auth failed")

        # Act
        result = self.runner.invoke(main, ['sync'])

        # Assert
        assert result.exit_code == 0
        assert 'Authentication failed' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_sync_no_config(self, mock_exists):
        """Test sync command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['sync'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml not found' in result.output


class TestCLIWebCommand:
    """Test CLI web command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'database': {
                'path': './test.db'
            }
        }

    def test_web_no_start_flag(self):
        """Test web command without start flag shows help."""
        # Act
        result = self.runner.invoke(main, ['web'])

        # Assert
        assert result.exit_code == 0
        assert 'Web interface management' in result.output
        assert '--start' in result.output
        assert '--port' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('uvicorn.run')
    @patch('inbox_cleaner.web.create_app')
    def test_web_start_success(self, mock_create_app, mock_uvicorn_run, mock_yaml, mock_open, mock_exists):
        """Test web command with start flag."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config
        mock_app = Mock()
        mock_create_app.return_value = mock_app

        # Act
        result = self.runner.invoke(main, ['web', '--start'])

        # Assert
        assert result.exit_code == 0
        assert 'Starting web interface' in result.output
        assert 'http://127.0.0.1:8000' in result.output
        mock_create_app.assert_called_once_with(db_path='./test.db')
        mock_uvicorn_run.assert_called_once_with(mock_app, host='127.0.0.1', port=8000, log_level='info')

    @patch('inbox_cleaner.cli.Path.exists')
    def test_web_start_no_config(self, mock_exists):
        """Test web command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['web', '--start'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml not found' in result.output


class TestCLIDiagnoseCommand:
    """Test CLI diagnose command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.DatabaseManager')
    def test_diagnose_all_good(self, mock_db_class, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test diagnose command when everything is configured correctly."""
        # Arrange
        # Mock Path.exists to return True for config and test db files
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_auth.load_credentials.return_value = mock_credentials

        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.get_statistics.return_value = {'total_emails': 100}

        # Act
        result = self.runner.invoke(main, ['diagnose'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml found' in result.output
        assert 'Gmail configuration found' in result.output
        assert 'Stored credentials found' in result.output
        assert 'Credentials are valid' in result.output
        assert 'Database found with 100 emails' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_diagnose_no_config(self, mock_exists):
        """Test diagnose command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['diagnose'])

        # Assert
        assert result.exit_code == 0
        assert 'config.yaml not found' in result.output
        assert 'Common Setup Issues' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_diagnose_invalid_config(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test diagnose command when config is invalid."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = {'invalid': 'config'}

        # Act
        result = self.runner.invoke(main, ['diagnose'])

        # Assert
        assert result.exit_code == 0
        assert 'Gmail configuration missing' in result.output


class TestCLIStatusCommand:
    """Test CLI status command functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.runner = CliRunner()
        self.mock_config = {
            'gmail': {
                'client_id': 'test-client-id',
                'client_secret': 'test-secret',
                'scopes': ['test-scope']
            },
            'database': {
                'path': './test.db'
            }
        }

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    @patch('inbox_cleaner.cli.DatabaseManager')
    def test_status_all_ready(self, mock_db_class, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test status command when everything is ready."""
        # Arrange
        # Mock Path.exists to return True for config and test db files
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_auth.load_credentials.return_value = mock_credentials

        mock_db = Mock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.get_statistics.return_value = {'total_emails': 250}

        # Act
        result = self.runner.invoke(main, ['status'])

        # Assert
        assert result.exit_code == 0
        assert 'Inbox Cleaner Status' in result.output
        assert 'Configuration: Ready' in result.output
        assert 'Authentication: Valid' in result.output
        assert 'Database: 250 emails' in result.output
        assert 'Available Features' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    def test_status_no_config(self, mock_exists):
        """Test status command when config file doesn't exist."""
        # Arrange
        mock_exists.return_value = False

        # Act
        result = self.runner.invoke(main, ['status'])

        # Assert
        assert result.exit_code == 0
        assert 'Configuration: Missing' in result.output

    @patch('inbox_cleaner.cli.Path.exists')
    @patch('inbox_cleaner.cli.open')
    @patch('inbox_cleaner.cli.yaml.safe_load')
    @patch('inbox_cleaner.cli.GmailAuthenticator')
    def test_status_auth_error(self, mock_auth_class, mock_yaml, mock_open, mock_exists):
        """Test status command when authentication is not setup."""
        # Arrange
        mock_exists.return_value = True
        mock_yaml.return_value = self.mock_config

        mock_auth = Mock()
        mock_auth_class.return_value = mock_auth
        mock_auth.load_credentials.return_value = None

        # Act
        result = self.runner.invoke(main, ['status'])

        # Assert
        assert result.exit_code == 0
        assert 'Authentication: Setup needed' in result.output