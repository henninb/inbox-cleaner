"""Tests for OAuth2 authentication module."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

from inbox_cleaner.auth import GmailAuthenticator, AuthenticationError


class TestGmailAuthenticator:
    """Test cases for Gmail OAuth2 authentication."""

    @pytest.fixture
    def auth_config(self):
        """Mock authentication configuration."""
        return {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
        }

    @pytest.fixture
    def authenticator(self, auth_config):
        """Create a GmailAuthenticator instance for testing."""
        return GmailAuthenticator(auth_config)

    def test_init_with_valid_config(self, auth_config):
        """Test authenticator initialization with valid config."""
        auth = GmailAuthenticator(auth_config)
        assert auth.client_id == "test_client_id"
        assert auth.scopes == ["https://www.googleapis.com/auth/gmail.readonly"]

    def test_init_with_missing_client_id(self):
        """Test authenticator initialization fails with missing client_id."""
        config = {"client_secret": "secret", "scopes": ["scope"]}
        with pytest.raises(ValueError, match="client_id is required"):
            GmailAuthenticator(config)

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # Simulate GUI environment with display
    def test_save_credentials_success(self, authenticator):
        """Test saving credentials to keyring in GUI environment."""
        import keyring
        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "test_token"}'

        authenticator.save_credentials(mock_creds)

        keyring.set_password.assert_called_once_with(
            "inbox-cleaner", "gmail-token", '{"token": "test_token"}'
        )

    @patch.dict('os.environ', {'HEADLESS': 'true'})  # Simulate headless environment
    @patch('builtins.open', mock_open())
    @patch('os.chmod')
    @patch('pathlib.Path')
    def test_save_credentials_headless(self, mock_path, mock_chmod, authenticator):
        """Test saving credentials to file in headless environment."""
        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "test_token"}'
        mock_file_path = Mock()
        mock_path.return_value = mock_file_path

        authenticator.save_credentials(mock_creds)

        # Should create file and set permissions
        mock_chmod.assert_called_once_with(mock_file_path, 0o600)

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    def test_load_credentials_success(self, authenticator):
        """Test loading credentials from keyring."""
        import keyring
        keyring.get_password.return_value = '{"token": "test_token"}'

        with patch('inbox_cleaner.auth.OAuth2Credentials.from_authorized_user_info') as mock_from_info:
            mock_creds = Mock()
            mock_from_info.return_value = mock_creds

            result = authenticator.load_credentials()

            assert result == mock_creds
            mock_from_info.assert_called_once()

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    def test_load_credentials_not_found(self, authenticator):
        """Test loading credentials when none exist."""
        import keyring
        keyring.get_password.return_value = None

        result = authenticator.load_credentials()

        assert result is None

    @patch('inbox_cleaner.auth.InstalledAppFlow')
    @patch.object(GmailAuthenticator, 'save_credentials')
    @patch.object(GmailAuthenticator, '_is_headless_environment', return_value=False)
    def test_authenticate_new_user(self, mock_headless, mock_save, mock_flow_class, authenticator):
        """Test authentication flow for new user in GUI environment."""
        # Mock the OAuth flow
        mock_flow = Mock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_creds = Mock()
        mock_flow.run_local_server.return_value = mock_creds

        result = authenticator.authenticate()

        assert result == mock_creds
        mock_save.assert_called_once_with(mock_creds)

    @patch('inbox_cleaner.auth.InstalledAppFlow')
    @patch.object(GmailAuthenticator, 'save_credentials')
    @patch.object(GmailAuthenticator, '_is_headless_environment', return_value=True)
    @patch('builtins.input', return_value='test_auth_code')
    def test_authenticate_manual_headless(self, mock_input, mock_headless, mock_save, mock_flow_class, authenticator):
        """Test authentication flow in headless environment with manual code entry."""
        # Mock the OAuth flow
        mock_flow = Mock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ('https://test-auth-url.com', 'state')
        mock_creds = Mock()
        mock_flow.credentials = mock_creds

        result = authenticator.authenticate()

        assert result == mock_creds
        mock_flow.authorization_url.assert_called_once_with(prompt='consent')
        mock_flow.fetch_token.assert_called_once_with(code='test_auth_code')
        mock_save.assert_called_once_with(mock_creds)

    @patch('inbox_cleaner.auth.InstalledAppFlow')
    @patch.object(GmailAuthenticator, 'save_credentials')
    @patch.object(GmailAuthenticator, '_is_headless_environment', return_value=True)
    @patch('builtins.input', return_value='http://localhost:8080/?state=test&code=4/test_code&scope=gmail')
    def test_authenticate_manual_url_parsing(self, mock_input, mock_headless, mock_save, mock_flow_class, authenticator):
        """Test authentication flow with full redirect URL parsing."""
        # Mock the OAuth flow
        mock_flow = Mock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ('https://test-auth-url.com', 'state')
        mock_creds = Mock()
        mock_flow.credentials = mock_creds

        result = authenticator.authenticate()

        assert result == mock_creds
        mock_flow.authorization_url.assert_called_once_with(prompt='consent')
        mock_flow.fetch_token.assert_called_once_with(code='4/test_code')  # Should extract code from URL
        mock_save.assert_called_once_with(mock_creds)

    @patch.object(GmailAuthenticator, 'load_credentials')
    def test_get_valid_credentials_existing_valid(self, mock_load, authenticator):
        """Test getting credentials when existing ones are valid."""
        mock_creds = Mock()
        mock_creds.valid = True
        mock_load.return_value = mock_creds

        result = authenticator.get_valid_credentials()

        assert result == mock_creds

    @patch.object(GmailAuthenticator, 'load_credentials')
    @patch.object(GmailAuthenticator, 'save_credentials')
    def test_get_valid_credentials_refresh_needed(self, mock_save, mock_load, authenticator):
        """Test getting credentials when refresh is needed."""
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_load.return_value = mock_creds

        with patch('inbox_cleaner.auth.Request') as mock_request:
            mock_creds.refresh.return_value = None  # Successful refresh

            result = authenticator.get_valid_credentials()

            assert result == mock_creds
            mock_creds.refresh.assert_called_once()
            mock_save.assert_called_once_with(mock_creds)

    @patch.object(GmailAuthenticator, 'load_credentials')
    @patch.object(GmailAuthenticator, 'authenticate')
    def test_get_valid_credentials_reauth_needed(self, mock_auth, mock_load, authenticator):
        """Test getting credentials when re-authentication is needed."""
        mock_load.return_value = None  # No existing credentials
        mock_new_creds = Mock()
        mock_auth.return_value = mock_new_creds

        result = authenticator.get_valid_credentials()

        assert result == mock_new_creds
        mock_auth.assert_called_once()

    def test_authentication_error_handling(self, authenticator):
        """Test proper error handling for authentication failures."""
        with patch.object(authenticator, 'authenticate', side_effect=Exception("OAuth failed")):
            with pytest.raises(AuthenticationError, match="Failed to authenticate"):
                authenticator.get_valid_credentials()