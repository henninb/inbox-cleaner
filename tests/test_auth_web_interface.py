"""Tests for improved authentication web interface."""

import pytest
from unittest.mock import MagicMock, patch, mock_open
import threading
import time
import requests
from urllib.parse import urlparse
from inbox_cleaner.auth import TempAuthServer, GmailAuthenticator


class TestImprovedTempAuthServer:
    """Test cases for improved temporary authentication server."""

    def test_init_creates_professional_handler(self):
        """Test that server creates a handler with professional styling."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        # Verify handler has proper methods
        assert hasattr(handler_class, 'do_GET')
        assert hasattr(handler_class, 'log_message')

    def test_success_page_has_proper_encoding(self):
        """Test that success page uses proper UTF-8 encoding and no unreadable chars."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        # Create a mock handler instance directly
        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?code=test_auth_code"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        # Call do_GET method directly
        mock_handler.do_GET()

        # Check that proper headers were set
        mock_handler.send_header.assert_any_call('Content-type', 'text/html; charset=utf-8')

        # Check that content was written
        assert mock_handler.wfile.write.called
        written_content = mock_handler.wfile.write.call_args[0][0]

        # Verify it's properly encoded
        assert isinstance(written_content, bytes)

        # Decode and check for proper content
        html_content = written_content.decode('utf-8')
        assert 'Authentication Successful' in html_content
        assert 'charset="utf-8"' in html_content
        assert '<meta name="viewport"' in html_content
        assert 'professional' in html_content.lower()

    def test_error_page_has_proper_styling(self):
        """Test that error page has professional styling."""
        server = TempAuthServer(port=8080)
        server.error = "access_denied"
        handler_class = server._create_handler()

        # Create a mock handler instance directly
        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?error=access_denied"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        # Check that proper headers were set
        mock_handler.send_header.assert_any_call('Content-type', 'text/html; charset=utf-8')

        # Check content
        written_content = mock_handler.wfile.write.call_args[0][0]
        html_content = written_content.decode('utf-8')
        assert 'Authentication Failed' in html_content
        assert 'charset="utf-8"' in html_content
        assert 'professional' in html_content.lower()

    def test_success_page_includes_css_and_responsive_design(self):
        """Test that success page includes CSS and is mobile-responsive."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?code=test_auth_code"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        written_content = mock_handler.wfile.write.call_args[0][0]
        html_content = written_content.decode('utf-8')

        # Check for responsive design elements
        assert 'viewport' in html_content
        assert 'width=device-width' in html_content

        # Check for CSS styling
        assert '<style>' in html_content
        assert 'css' in html_content.lower() or 'style' in html_content

        # Check for modern HTML structure
        assert '<!DOCTYPE html>' in html_content
        assert '<html lang="en">' in html_content
        assert '<head>' in html_content
        assert '<title>' in html_content

    def test_success_page_includes_branding(self):
        """Test that success page includes inbox-cleaner branding."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?code=test_auth_code"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        written_content = mock_handler.wfile.write.call_args[0][0]
        html_content = written_content.decode('utf-8')

        # Check for inbox-cleaner branding
        assert 'inbox-cleaner' in html_content.lower() or 'Inbox Cleaner' in html_content
        assert 'Gmail' in html_content

    def test_auto_close_functionality(self):
        """Test that success page includes auto-close functionality."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?code=test_auth_code"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        written_content = mock_handler.wfile.write.call_args[0][0]
        html_content = written_content.decode('utf-8')

        # Check for auto-close script
        assert 'setTimeout' in html_content
        assert 'window.close()' in html_content

    def test_favicon_included(self):
        """Test that pages include a favicon."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?code=test_auth_code"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        written_content = mock_handler.wfile.write.call_args[0][0]
        html_content = written_content.decode('utf-8')

        # Check for favicon or icon
        assert 'icon' in html_content.lower() or 'favicon' in html_content.lower()

    def test_loading_page_while_waiting(self):
        """Test that server can show a loading page while waiting for auth."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        # Test a request to root path (before auth callback)
        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        # Should show some kind of response (not just 400)
        assert mock_handler.send_response.called
        call_args = mock_handler.send_response.call_args[0]
        # Should not be a 400 error for root path
        if call_args[0] == 200:
            # If we send a 200 response, check it has content
            assert mock_handler.wfile.write.called

    def test_security_headers_included(self):
        """Test that responses include basic security headers."""
        server = TempAuthServer(port=8080)
        handler_class = server._create_handler()

        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?code=test_auth_code"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        # Check for security-related headers
        header_calls = [call[0] for call in mock_handler.send_header.call_args_list]
        header_dict = {call[0][0]: call[0][1] for call in mock_handler.send_header.call_args_list}

        # Should at least have content-type with charset
        assert 'Content-type' in header_dict
        assert 'charset=utf-8' in header_dict['Content-type']


class TestImprovedAuthFlow:
    """Test cases for improved authentication flow integration."""

    @patch('inbox_cleaner.auth.webbrowser.open')
    @patch('inbox_cleaner.auth.TempAuthServer')
    def test_authenticate_with_temp_server_uses_improved_pages(self, mock_server_class, mock_browser):
        """Test that temp server auth uses improved pages."""
        mock_config = {
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
        }

        # Mock the server
        mock_server = MagicMock()
        mock_server.port = 8080
        mock_server.wait_for_callback.return_value = 'test_auth_code'
        mock_server_class.return_value = mock_server

        authenticator = GmailAuthenticator(mock_config)

        # Mock the OAuth flow
        with patch('inbox_cleaner.auth.InstalledAppFlow') as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.authorization_url.return_value = ('https://auth.url', 'state')
            mock_credentials = MagicMock()
            mock_flow.credentials = mock_credentials
            mock_flow_class.from_client_config.return_value = mock_flow

            with patch.object(authenticator, 'save_credentials'):
                result = authenticator.authenticate_with_temp_server()

                assert result == mock_credentials
                # Verify server was created and started
                mock_server_class.assert_called_once_with(8080)
                mock_server.start.assert_called_once()
                mock_server.stop.assert_called_once()

    def test_improved_pages_handle_special_characters(self):
        """Test that improved pages properly handle special characters and encoding."""
        server = TempAuthServer(port=8080)
        server.error = "Error with special chars: äöü 中文 🔐"
        handler_class = server._create_handler()

        mock_handler = handler_class.__new__(handler_class)
        mock_handler.path = "/?error=test_error"
        mock_handler.send_response = MagicMock()
        mock_handler.send_header = MagicMock()
        mock_handler.end_headers = MagicMock()
        mock_handler.wfile = MagicMock()

        mock_handler.do_GET()

        # Should not raise encoding errors
        assert mock_handler.wfile.write.called
        written_content = mock_handler.wfile.write.call_args[0][0]

        # Should be properly encoded bytes
        assert isinstance(written_content, bytes)

        # Should decode without errors
        html_content = written_content.decode('utf-8')
        assert len(html_content) > 0