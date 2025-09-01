"""Tests for Gmail data extraction module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List, Dict

from inbox_cleaner.extractor import GmailExtractor, EmailMetadata, ExtractionError


class TestGmailExtractor:
    """Test cases for Gmail data extraction."""

    @pytest.fixture
    def mock_service(self):
        """Mock Gmail API service."""
        service = Mock()
        return service

    @pytest.fixture
    def extractor(self, mock_service):
        """Create a GmailExtractor instance for testing."""
        return GmailExtractor(mock_service)

    @pytest.fixture
    def sample_message_list(self):
        """Sample message list response from Gmail API."""
        return {
            'messages': [
                {'id': 'msg1', 'threadId': 'thread1'},
                {'id': 'msg2', 'threadId': 'thread2'},
            ],
            'nextPageToken': 'next_token_123',
            'resultSizeEstimate': 2
        }

    @pytest.fixture
    def sample_message_detail(self):
        """Sample detailed message from Gmail API."""
        return {
            'id': 'msg1',
            'threadId': 'thread1',
            'labelIds': ['INBOX', 'UNREAD'],
            'snippet': 'This is a test email snippet',
            'internalDate': '1640995200000',  # 2022-01-01 00:00:00 UTC
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'sender@example.com'},
                    {'name': 'Subject', 'value': 'Test Email Subject'},
                    {'name': 'Date', 'value': 'Sat, 01 Jan 2022 00:00:00 +0000'},
                ],
                'body': {
                    'data': 'VGhpcyBpcyBhIHRlc3QgZW1haWwgYm9keQ=='  # Base64 encoded
                }
            }
        }

    def test_init_with_service(self, mock_service):
        """Test extractor initialization with Gmail service."""
        extractor = GmailExtractor(mock_service)
        assert extractor.service == mock_service
        assert extractor.batch_size == 1000  # default

    def test_init_with_custom_batch_size(self, mock_service):
        """Test extractor initialization with custom batch size."""
        extractor = GmailExtractor(mock_service, batch_size=500)
        assert extractor.batch_size == 500

    def test_get_message_list_success(self, extractor, sample_message_list):
        """Test successful message list retrieval."""
        extractor.service.users().messages().list().execute.return_value = sample_message_list

        result = extractor.get_message_list(query="is:unread")

        assert result == sample_message_list
        extractor.service.users().messages().list.assert_called_with(
            userId='me', q="is:unread", maxResults=1000, pageToken=None
        )

    def test_get_message_list_with_page_token(self, extractor, sample_message_list):
        """Test message list retrieval with pagination."""
        extractor.service.users().messages().list().execute.return_value = sample_message_list

        result = extractor.get_message_list(query="is:unread", page_token="token123")

        extractor.service.users().messages().list.assert_called_with(
            userId='me', q="is:unread", maxResults=1000, pageToken="token123"
        )

    def test_get_message_list_api_error(self, extractor):
        """Test message list retrieval with API error."""
        from googleapiclient.errors import HttpError

        mock_error = Mock()
        mock_error.resp.status = 403
        extractor.service.users().messages().list().execute.side_effect = HttpError(
            mock_error, b'{"error": {"message": "Rate limit exceeded"}}'
        )

        with pytest.raises(ExtractionError, match="Failed to retrieve message list"):
            extractor.get_message_list(query="is:unread")

    def test_get_message_detail_success(self, extractor, sample_message_detail):
        """Test successful message detail retrieval."""
        extractor.service.users().messages().get().execute.return_value = sample_message_detail

        result = extractor.get_message_detail("msg1")

        assert result == sample_message_detail
        extractor.service.users().messages().get.assert_called_with(
            userId='me', id="msg1", format='full'
        )

    def test_extract_email_metadata_success(self, extractor, sample_message_detail):
        """Test successful email metadata extraction."""
        result = extractor.extract_email_metadata(sample_message_detail)

        assert isinstance(result, EmailMetadata)
        assert result.message_id == "msg1"
        assert result.thread_id == "thread1"
        assert result.sender_email == "sender@example.com"
        assert result.sender_domain == "example.com"
        assert result.subject == "Test Email Subject"
        assert result.labels == ['INBOX', 'UNREAD']
        assert result.snippet == 'This is a test email snippet'
        assert isinstance(result.date_received, datetime)

    def test_extract_email_metadata_missing_headers(self, extractor):
        """Test email metadata extraction with missing headers."""
        message = {
            'id': 'msg1',
            'threadId': 'thread1',
            'labelIds': ['INBOX'],
            'snippet': 'Test snippet',
            'internalDate': '1640995200000',
            'payload': {'headers': []}  # No headers
        }

        result = extractor.extract_email_metadata(message)

        assert result.sender_email == ""
        assert result.sender_domain == ""
        assert result.subject == ""

    def test_extract_content_with_plain_text(self, extractor):
        """Test content extraction from plain text email."""
        payload = {
            'body': {
                'data': 'VGhpcyBpcyBwbGFpbiB0ZXh0'  # Base64: "This is plain text"
            },
            'mimeType': 'text/plain'
        }

        result = extractor.extract_content(payload)

        assert result == "This is plain text"

    def test_extract_content_multipart(self, extractor):
        """Test content extraction from multipart email."""
        payload = {
            'parts': [
                {
                    'body': {'data': 'UGxhaW4gdGV4dCBwYXJ0'},  # "Plain text part"
                    'mimeType': 'text/plain'
                },
                {
                    'body': {'data': 'PGh0bWw+SFRNTCBwYXJ0PC9odG1sPg=='},  # "<html>HTML part</html>"
                    'mimeType': 'text/html'
                }
            ]
        }

        result = extractor.extract_content(payload)

        # Should prefer plain text over HTML
        assert "Plain text part" in result

    def test_extract_batch_success(self, extractor, sample_message_detail):
        """Test successful batch extraction."""
        message_ids = ["msg1", "msg2"]

        # Mock the message detail calls
        extractor.service.users().messages().get().execute.side_effect = [
            sample_message_detail,
            {**sample_message_detail, 'id': 'msg2'}  # Second message
        ]

        with patch.object(extractor, 'extract_email_metadata') as mock_extract:
            mock_metadata = Mock(spec=EmailMetadata)
            mock_extract.return_value = mock_metadata

            results = extractor.extract_batch(message_ids)

            assert len(results) == 2
            assert all(isinstance(r, EmailMetadata) for r in results)
            assert mock_extract.call_count == 2

    def test_extract_all_with_progress_callback(self, extractor, sample_message_list, sample_message_detail):
        """Test extracting all messages with progress tracking."""
        # Remove nextPageToken to prevent infinite loop
        sample_message_list_no_next = sample_message_list.copy()
        if 'nextPageToken' in sample_message_list_no_next:
            del sample_message_list_no_next['nextPageToken']

        # Mock the message list call
        extractor.service.users().messages().list().execute.return_value = sample_message_list_no_next

        # Mock the message detail calls
        extractor.service.users().messages().get().execute.return_value = sample_message_detail

        progress_calls = []
        def progress_callback(current, total):
            progress_calls.append((current, total))

        with patch.object(extractor, 'extract_email_metadata') as mock_extract:
            mock_metadata = Mock(spec=EmailMetadata)
            mock_extract.return_value = mock_metadata

            results = extractor.extract_all(
                query="is:unread",
                progress_callback=progress_callback
            )

            assert len(results) == 2
            assert len(progress_calls) > 0
            # Should have called progress callback
            assert progress_calls[-1] == (2, 2)  # Final call should show completion

    def test_extract_all_with_limit(self, extractor, sample_message_list):
        """Test extracting messages with a limit."""
        sample_message_list_copy = sample_message_list.copy()
        sample_message_list_copy['messages'] = sample_message_list_copy['messages'] * 10  # 20 messages
        # Remove nextPageToken to prevent infinite loop in test
        if 'nextPageToken' in sample_message_list_copy:
            del sample_message_list_copy['nextPageToken']
        extractor.service.users().messages().list().execute.return_value = sample_message_list_copy

        with patch.object(extractor, 'extract_batch') as mock_extract_batch:
            mock_extract_batch.return_value = [Mock(spec=EmailMetadata)] * 5

            results = extractor.extract_all(query="is:unread", max_results=5)

            assert len(results) == 5

    def test_hash_sender_email(self, extractor):
        """Test email address hashing for privacy."""
        email = "user@example.com"

        hash1 = extractor._hash_sender_email(email)
        hash2 = extractor._hash_sender_email(email)

        # Same email should produce same hash
        assert hash1 == hash2
        # Hash should not contain the original email
        assert email not in hash1
        # Hash should be consistent length
        assert len(hash1) == 64  # SHA-256 hex digest


class TestEmailMetadata:
    """Test cases for EmailMetadata data class."""

    def test_email_metadata_creation(self):
        """Test creating EmailMetadata instance."""
        metadata = EmailMetadata(
            message_id="msg1",
            thread_id="thread1",
            sender_email="test@example.com",
            sender_domain="example.com",
            sender_hash="hash123",
            subject="Test Subject",
            date_received=datetime.now(),
            labels=["INBOX"],
            snippet="Test snippet",
            content="Test content",
            estimated_importance=0.8
        )

        assert metadata.message_id == "msg1"
        assert metadata.sender_domain == "example.com"
        assert metadata.estimated_importance == 0.8

    def test_email_metadata_to_dict(self):
        """Test converting EmailMetadata to dictionary."""
        date_obj = datetime(2022, 1, 1, 12, 0, 0)
        metadata = EmailMetadata(
            message_id="msg1",
            thread_id="thread1",
            sender_email="test@example.com",
            sender_domain="example.com",
            sender_hash="hash123",
            subject="Test Subject",
            date_received=date_obj,
            labels=["INBOX"],
            snippet="Test snippet",
            content="Test content"
        )

        result_dict = metadata.to_dict()

        assert result_dict["message_id"] == "msg1"
        assert result_dict["sender_domain"] == "example.com"
        assert isinstance(result_dict["date_received"], str)  # Should be serialized