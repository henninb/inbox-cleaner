"""Tests for CLI functionality following TDD principles."""

import pytest
import yaml
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
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