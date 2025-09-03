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
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # Simulate GUI environment
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
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # Simulate GUI environment
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

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # GUI environment
    def test_logout_keyring_success(self, authenticator):
        """Test successful logout by deleting credentials from keyring."""
        import keyring

        result = authenticator.logout()

        keyring.delete_password.assert_called_once_with("inbox-cleaner", "gmail-token")
        assert result is True

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # GUI environment
    def test_logout_keyring_not_found(self, authenticator):
        """Test logout when no credentials exist in keyring."""
        import keyring
        keyring.delete_password.side_effect = Exception("Password not found")

        # Should not raise exception, just return False
        result = authenticator.logout()

        keyring.delete_password.assert_called_once_with("inbox-cleaner", "gmail-token")
        assert result is False

    @patch.dict('os.environ', {'HEADLESS': 'true'})  # Headless environment
    @patch('pathlib.Path')
    def test_logout_file_success(self, mock_path, authenticator):
        """Test successful logout by deleting credentials file in headless environment."""
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_path.return_value = mock_file

        result = authenticator.logout()

        mock_file.unlink.assert_called_once()
        assert result is True

    @patch.dict('os.environ', {'HEADLESS': 'true'})  # Headless environment
    @patch('pathlib.Path')
    def test_logout_file_not_found(self, mock_path, authenticator):
        """Test logout when credentials file doesn't exist."""
        mock_file = Mock()
        mock_file.exists.return_value = False
        mock_path.return_value = mock_file

        result = authenticator.logout()

        mock_file.unlink.assert_not_called()
        assert result is False

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # GUI environment
    @patch('pathlib.Path')
    def test_logout_both_storages(self, mock_path, authenticator):
        """Test logout clears both keyring and file storage."""
        import keyring
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_path.return_value = mock_file

        result = authenticator.logout()

        # Should try both keyring and file
        keyring.delete_password.assert_called_once_with("inbox-cleaner", "gmail-token")
        mock_file.unlink.assert_called_once()
        assert result is True

    @patch.dict('sys.modules', {'keyring': MagicMock()})
    @patch.dict('os.environ', {'DISPLAY': ':0'}, clear=True)  # GUI environment
    @patch('pathlib.Path')
    def test_logout_partial_success(self, mock_path, authenticator):
        """Test logout when keyring fails but file succeeds."""
        import keyring
        keyring.delete_password.side_effect = Exception("Keyring error")
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_path.return_value = mock_file

        result = authenticator.logout()

        # Should still try file even if keyring fails
        keyring.delete_password.assert_called_once_with("inbox-cleaner", "gmail-token")
        mock_file.unlink.assert_called_once()
        assert result is True

    @patch('requests.post')
    @patch.object(GmailAuthenticator, 'save_credentials')
    @patch('time.sleep')  # Speed up polling in tests
    def test_device_flow_success(self, mock_sleep, mock_save, mock_requests, authenticator):
        """Test successful device flow authentication."""
        # Mock device authorization response
        device_mock = Mock()
        device_mock.json.return_value = {
            'device_code': 'test_device_code',
            'user_code': 'ABCD-1234',
            'verification_uri': 'https://www.google.com/device',
            'expires_in': 1800,
            'interval': 1  # Fast polling for tests
        }
        device_mock.raise_for_status.return_value = None

        # Mock successful token response
        token_mock = Mock()
        token_mock.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token'
        }

        # First call returns device info, second call returns tokens
        mock_requests.side_effect = [device_mock, token_mock]

        with patch('inbox_cleaner.auth.OAuth2Credentials.from_authorized_user_info') as mock_creds_create:
            mock_creds = Mock()
            mock_creds_create.return_value = mock_creds

            result = authenticator.authenticate_device_flow()

            assert result == mock_creds
            mock_save.assert_called_once_with(mock_creds)

    @patch('requests.post')
    @patch('time.sleep')
    def test_device_flow_user_denial(self, mock_sleep, mock_requests, authenticator):
        """Test device flow when user denies access."""
        # Mock device authorization response
        device_mock = Mock()
        device_mock.json.return_value = {
            'device_code': 'test_device_code',
            'user_code': 'ABCD-1234',
            'verification_uri': 'https://www.google.com/device',
            'expires_in': 1800,
            'interval': 1
        }
        device_mock.raise_for_status.return_value = None

        # Mock access denied token response
        token_mock = Mock()
        token_mock.json.return_value = {'error': 'access_denied'}

        mock_requests.side_effect = [device_mock, token_mock]

        with pytest.raises(AuthenticationError, match="User denied access"):
            authenticator.authenticate_device_flow()

    @patch('requests.post')
    @patch('time.time')
    @patch('time.sleep')
    def test_device_flow_timeout(self, mock_sleep, mock_time, mock_requests, authenticator):
        """Test device flow timeout."""
        # Mock device authorization response
        device_mock = Mock()
        device_mock.json.return_value = {
            'device_code': 'test_device_code',
            'user_code': 'ABCD-1234',
            'verification_uri': 'https://www.google.com/device',
            'expires_in': 1,  # Very short timeout
            'interval': 1
        }
        device_mock.raise_for_status.return_value = None

        # Mock timeout scenario
        mock_time.side_effect = [0, 2]  # First call returns 0, second returns 2 (expired)
        mock_requests.return_value = device_mock

        with pytest.raises(AuthenticationError, match="Device flow timed out"):
            authenticator.authenticate_device_flow()

    @patch('inbox_cleaner.auth.InstalledAppFlow')
    @patch.object(GmailAuthenticator, 'save_credentials')
    @patch('inbox_cleaner.auth.TempAuthServer')
    def test_temporary_server_auth_success(self, mock_server_class, mock_save, mock_flow_class, authenticator):
        """Test successful authentication using temporary web server."""
        # Mock the OAuth flow
        mock_flow = Mock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ('https://test-auth-url.com', 'state')

        # Mock temporary server
        mock_server = Mock()
        mock_server_class.return_value = mock_server
        mock_server.start.return_value = None
        mock_server.wait_for_callback.return_value = '4/test_auth_code'
        mock_server.port = 8080

        # Mock credentials
        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "test_token"}'
        mock_flow.credentials = mock_creds

        result = authenticator.authenticate_with_temp_server()

        assert result == mock_creds
        mock_server.start.assert_called_once()
        mock_server.wait_for_callback.assert_called_once()
        mock_server.stop.assert_called_once()
        mock_flow.fetch_token.assert_called_once_with(code='4/test_auth_code')
        mock_save.assert_called_once_with(mock_creds)

    @patch('inbox_cleaner.auth.InstalledAppFlow')
    @patch('inbox_cleaner.auth.TempAuthServer')
    def test_temporary_server_auth_timeout(self, mock_server_class, mock_flow_class, authenticator):
        """Test temporary server authentication timeout."""
        mock_flow = Mock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ('https://test-auth-url.com', 'state')

        # Mock server timeout
        mock_server = Mock()
        mock_server_class.return_value = mock_server
        mock_server.start.return_value = None
        mock_server.wait_for_callback.side_effect = TimeoutError("Authentication timed out")
        mock_server.port = 8080

        with pytest.raises(AuthenticationError, match="Authentication timed out"):
            authenticator.authenticate_with_temp_server()

        mock_server.stop.assert_called_once()

    @patch('inbox_cleaner.auth.InstalledAppFlow')
    @patch('inbox_cleaner.auth.TempAuthServer')
    def test_temporary_server_port_busy(self, mock_server_class, mock_flow_class, authenticator):
        """Test temporary server when port is busy - should try alternative ports."""
        mock_flow = Mock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ('https://test-auth-url.com', 'state')

        # Mock server startup failure on first port, success on second
        mock_server1 = Mock()
        mock_server2 = Mock()
        mock_server_class.side_effect = [mock_server1, mock_server2]

        mock_server1.start.side_effect = OSError("Address already in use")
        mock_server2.start.return_value = None
        mock_server2.wait_for_callback.return_value = '4/test_code'
        mock_server2.port = 8081

        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "test_token"}'
        mock_flow.credentials = mock_creds

        result = authenticator.authenticate_with_temp_server()

        assert result == mock_creds
        # Should have tried both servers
        assert mock_server_class.call_count == 2
        mock_server1.start.assert_called_once()
        mock_server2.start.assert_called_once()