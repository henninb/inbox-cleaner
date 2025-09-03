"""Comprehensive tests for UnsubscribeEngine business logic."""

import pytest
import time
import base64
from unittest.mock import Mock, patch, MagicMock
from googleapiclient.errors import HttpError

from inbox_cleaner.unsubscribe_engine import UnsubscribeEngine
from inbox_cleaner.database import DatabaseManager


class TestUnsubscribeEngineInit:
    """Test UnsubscribeEngine initialization."""

    def test_init_with_service_and_db(self):
        """Test initialization with service and database manager."""
        mock_service = Mock()
        mock_db = Mock()

        engine = UnsubscribeEngine(mock_service, mock_db)

        assert engine.service == mock_service
        assert engine.db == mock_db


class TestUnsubscribeEngineFindLinks:
    """Test unsubscribe link finding functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = Mock()
        self.mock_db = Mock()
        self.engine = UnsubscribeEngine(self.mock_service, self.mock_db)

    def test_find_unsubscribe_links_no_messages(self):
        """Test finding unsubscribe links when no messages exist."""
        # Arrange
        domain = "test.com"
        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': []
        }

        # Act
        result = self.engine.find_unsubscribe_links(domain, sample_size=5)

        # Assert
        assert result == []
        self.mock_service.users().messages().list.assert_called_once_with(
            userId='me',
            q='from:test.com',
            maxResults=5
        )

    def test_find_unsubscribe_links_with_messages(self):
        """Test finding unsubscribe links in messages."""
        # Arrange
        domain = "newsletter.com"
        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}]
        }

        # Mock message details with unsubscribe info
        mock_message = {
            'id': 'msg1',
            'payload': {
                'headers': [
                    {'name': 'List-Unsubscribe', 'value': '<https://newsletter.com/unsubscribe?id=123>'},
                    {'name': 'Subject', 'value': 'Weekly Newsletter'}
                ],
                'body': {
                    'data': base64.urlsafe_b64encode(
                        'Click here to unsubscribe: https://newsletter.com/opt-out'.encode()
                    ).decode().rstrip('=')
                }
            }
        }

        self.mock_service.users().messages().get.return_value.execute.return_value = mock_message

        # Act
        result = self.engine.find_unsubscribe_links(domain, sample_size=2)

        # Assert
        assert len(result) == 2  # Two messages processed
        assert result[0]['domain'] == domain
        assert result[0]['message_id'] == 'msg1'
        assert 'unsubscribe_links' in result[0]
        assert len(result[0]['unsubscribe_links']) > 0

    def test_find_unsubscribe_links_http_error(self):
        """Test handling HTTP errors when searching for messages."""
        # Arrange
        domain = "error.com"
        self.mock_service.users().messages().list.side_effect = HttpError(
            resp=Mock(status=404), content=b'Not found'
        )

        # Act
        result = self.engine.find_unsubscribe_links(domain)

        # Assert
        assert result == []

    def test_extract_unsubscribe_info_with_header(self):
        """Test extracting unsubscribe info from List-Unsubscribe header."""
        # Arrange
        message = {
            'id': 'test_msg',
            'payload': {
                'headers': [
                    {
                        'name': 'List-Unsubscribe',
                        'value': '<https://example.com/unsubscribe> <mailto:unsubscribe@example.com>'
                    },
                    {'name': 'Subject', 'value': 'Test Email'}
                ],
                'body': {'data': base64.urlsafe_b64encode('Plain text content'.encode()).decode().rstrip('=')}
            }
        }

        # Act
        result = self.engine._extract_unsubscribe_info(message, "example.com")

        # Assert
        assert result is not None
        assert result['domain'] == "example.com"
        assert result['message_id'] == 'test_msg'
        assert 'https://example.com/unsubscribe' in result['unsubscribe_links']
        assert 'mailto:unsubscribe@example.com' in result['unsubscribe_links']

    def test_extract_unsubscribe_info_from_content(self):
        """Test extracting unsubscribe links from email content."""
        # Arrange
        email_content = "To unsubscribe, visit https://newsletter.com/optout or email optout@newsletter.com"
        encoded_content = base64.urlsafe_b64encode(email_content.encode()).decode().rstrip('=')

        message = {
            'id': 'content_msg',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'Newsletter'}],
                'body': {'data': encoded_content}
            }
        }

        # Act
        result = self.engine._extract_unsubscribe_info(message, "newsletter.com")

        # Assert
        assert result is not None
        assert 'https://newsletter.com/optout' in result['unsubscribe_links']
        assert 'optout@newsletter.com' in result['unsubscribe_links']

    def test_extract_unsubscribe_info_no_links(self):
        """Test extraction when no unsubscribe links are found."""
        # Arrange
        message = {
            'id': 'no_links',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'Regular Email'}],
                'body': {'data': base64.urlsafe_b64encode('Regular content without links'.encode()).decode().rstrip('=')}
            }
        }

        # Act
        result = self.engine._extract_unsubscribe_info(message, "example.com")

        # Assert
        assert result is None


class TestUnsubscribeEngineEmailParsing:
    """Test email content parsing functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.engine = UnsubscribeEngine(Mock(), Mock())

    def test_decode_base64_valid(self):
        """Test decoding valid base64 content."""
        # Arrange
        text = "Hello World!"
        encoded = base64.urlsafe_b64encode(text.encode()).decode().rstrip('=')

        # Act
        result = self.engine._decode_base64(encoded)

        # Assert
        assert result == text

    def test_decode_base64_invalid(self):
        """Test decoding invalid base64 returns empty string."""
        # Act
        result = self.engine._decode_base64("invalid-base64!")

        # Assert
        assert result == ""

    def test_extract_email_content_plain_text(self):
        """Test extracting content from plain text email."""
        # Arrange
        content = "This is plain text content"
        encoded = base64.urlsafe_b64encode(content.encode()).decode().rstrip('=')
        payload = {
            'body': {'data': encoded}
        }

        # Act
        result = self.engine._extract_email_content(payload)

        # Assert
        assert content in result

    def test_extract_email_content_multipart(self):
        """Test extracting content from multipart email."""
        # Arrange
        plain_content = "Plain text part"
        html_content = "<p>HTML part</p>"

        plain_encoded = base64.urlsafe_b64encode(plain_content.encode()).decode().rstrip('=')
        html_encoded = base64.urlsafe_b64encode(html_content.encode()).decode().rstrip('=')

        payload = {
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {'data': plain_encoded}
                },
                {
                    'mimeType': 'text/html',
                    'body': {'data': html_encoded}
                }
            ]
        }

        # Act
        result = self.engine._extract_email_content(payload)

        # Assert
        assert plain_content in result
        assert 'HTML part' in result  # HTML tags should be stripped

    def test_extract_part_content_nested_multipart(self):
        """Test extracting content from nested multipart structure."""
        # Arrange
        nested_content = "Nested content"
        nested_encoded = base64.urlsafe_b64encode(nested_content.encode()).decode().rstrip('=')

        part = {
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {'data': nested_encoded}
                }
            ]
        }

        # Act
        result = self.engine._extract_part_content(part)

        # Assert
        assert nested_content in result

    def test_extract_part_content_html_tag_removal(self):
        """Test HTML tag removal from HTML content."""
        # Arrange
        html_content = "<html><body><h1>Title</h1><p>Paragraph with <a href='link'>link</a></p></body></html>"
        encoded = base64.urlsafe_b64encode(html_content.encode()).decode().rstrip('=')

        part = {
            'mimeType': 'text/html',
            'body': {'data': encoded}
        }

        # Act
        result = self.engine._extract_part_content(part)

        # Assert
        assert '<' not in result
        assert '>' not in result
        assert 'Title' in result
        assert 'Paragraph with link' in result


class TestUnsubscribeEngineFilters:
    """Test Gmail filter creation and management."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = Mock()
        self.mock_db = Mock()
        self.engine = UnsubscribeEngine(self.mock_service, self.mock_db)

    def test_create_delete_filter_dry_run(self):
        """Test creating filter in dry run mode."""
        # Arrange
        domain = "spam.com"

        # Act
        result = self.engine.create_delete_filter(domain, dry_run=True)

        # Assert
        assert result['domain'] == domain
        assert result['action'] == 'DRY RUN - Filter not created'
        assert 'filter_criteria' in result
        assert result['filter_criteria']['from'] == domain
        assert 'TRASH' in result['filter_actions']['addLabelIds']
        # Should not make API call
        self.mock_service.users().settings().filters().create.assert_not_called()

    def test_create_delete_filter_success(self):
        """Test successful filter creation."""
        # Arrange
        domain = "unwanted.com"
        mock_response = {'id': 'filter_123'}
        self.mock_service.users().settings().filters().create.return_value.execute.return_value = mock_response

        # Act
        result = self.engine.create_delete_filter(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert result['filter_id'] == 'filter_123'
        assert result['action'] == 'Filter created successfully'
        assert result['success'] is True

        # Verify API call
        expected_filter_body = {
            'criteria': {'from': domain},
            'action': {
                'addLabelIds': ['TRASH'],
                'removeLabelIds': ['INBOX', 'UNREAD']
            }
        }
        self.mock_service.users().settings().filters().create.assert_called_once_with(
            userId='me',
            body=expected_filter_body
        )

    def test_create_delete_filter_http_error(self):
        """Test filter creation with HTTP error."""
        # Arrange
        domain = "error.com"
        self.mock_service.users().settings().filters().create.side_effect = HttpError(
            resp=Mock(status=400), content=b'Bad Request'
        )

        # Act
        result = self.engine.create_delete_filter(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert 'error' in result
        assert result['action'] == 'Filter creation failed'

    def test_list_existing_filters(self):
        """Test listing existing Gmail filters."""
        # Arrange
        mock_filters = {
            'filter': [
                {'id': 'f1', 'criteria': {'from': 'spam.com'}},
                {'id': 'f2', 'criteria': {'subject': 'unwanted'}}
            ]
        }
        self.mock_service.users().settings().filters().list.return_value.execute.return_value = mock_filters

        # Act
        result = self.engine.list_existing_filters()

        # Assert
        assert len(result) == 2
        assert result[0]['id'] == 'f1'
        assert result[1]['id'] == 'f2'

    def test_list_existing_filters_http_error(self):
        """Test listing filters with HTTP error."""
        # Arrange
        self.mock_service.users().settings().filters().list.side_effect = HttpError(
            resp=Mock(status=403), content=b'Forbidden'
        )

        # Act
        result = self.engine.list_existing_filters()

        # Assert
        assert result == []

    def test_delete_filter_success(self):
        """Test successful filter deletion."""
        # Arrange
        filter_id = "filter_to_delete"
        self.mock_service.users().settings().filters().delete.return_value.execute.return_value = {}

        # Act
        result = self.engine.delete_filter(filter_id)

        # Assert
        assert result is True
        self.mock_service.users().settings().filters().delete.assert_called_once_with(
            userId='me',
            id=filter_id
        )

    def test_delete_filter_http_error(self):
        """Test filter deletion with HTTP error."""
        # Arrange
        filter_id = "nonexistent_filter"
        self.mock_service.users().settings().filters().delete.side_effect = HttpError(
            resp=Mock(status=404), content=b'Not Found'
        )

        # Act
        result = self.engine.delete_filter(filter_id)

        # Assert
        assert result is False


class TestUnsubscribeEngineEmailDeletion:
    """Test email deletion functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = Mock()
        self.mock_db = Mock()
        self.engine = UnsubscribeEngine(self.mock_service, self.mock_db)

    def test_delete_existing_emails_no_messages(self):
        """Test deletion when no messages exist."""
        # Arrange
        domain = "empty.com"
        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': []
        }

        # Act
        result = self.engine.delete_existing_emails(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert result['deleted_count'] == 0
        assert result['message'] == 'No emails found'

    def test_delete_existing_emails_dry_run(self):
        """Test email deletion in dry run mode."""
        # Arrange
        domain = "test.com"
        mock_messages = [{'id': f'msg{i}'} for i in range(10)]
        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': mock_messages
        }

        # Act
        result = self.engine.delete_existing_emails(domain, dry_run=True)

        # Assert
        assert result['domain'] == domain
        assert result['found_count'] == 10
        assert result['action'] == 'DRY RUN - No emails moved to trash'
        # Should not make modification calls
        self.mock_service.users().messages().modify.assert_not_called()

    def test_delete_existing_emails_execute_mode(self):
        """Test actual email deletion."""
        # Arrange
        domain = "delete.com"
        mock_messages = [{'id': 'msg1'}, {'id': 'msg2'}, {'id': 'msg3'}]
        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': mock_messages
        }
        self.mock_service.users().messages().modify.return_value.execute.return_value = {}

        # Act
        result = self.engine.delete_existing_emails(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert result['found_count'] == 3
        assert result['deleted_count'] == 3
        assert result['success'] is True

        # Verify modification calls
        assert self.mock_service.users().messages().modify.call_count == 3

    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_delete_existing_emails_partial_failure(self, mock_sleep):
        """Test email deletion with some failures."""
        # Arrange
        domain = "partial.com"
        mock_messages = [{'id': 'msg1'}, {'id': 'msg2'}, {'id': 'msg3'}]
        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': mock_messages
        }

        # Make first call succeed, second fail, third succeed
        self.mock_service.users().messages().modify.side_effect = [
            Mock(execute=lambda: {}),  # Success
            HttpError(resp=Mock(status=400), content=b'Bad Request'),  # Failure
            Mock(execute=lambda: {})   # Success
        ]

        # Act
        result = self.engine.delete_existing_emails(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert result['found_count'] == 3
        assert result['deleted_count'] == 2  # Only 2 succeeded
        assert result['success'] is True

    def test_delete_existing_emails_http_error(self):
        """Test email deletion with HTTP error on search."""
        # Arrange
        domain = "error.com"
        self.mock_service.users().messages().list.side_effect = HttpError(
            resp=Mock(status=500), content=b'Server Error'
        )

        # Act
        result = self.engine.delete_existing_emails(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert 'error' in result


class TestUnsubscribeEngineWorkflow:
    """Test complete unsubscribe and block workflow."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = Mock()
        self.mock_db = Mock()
        self.engine = UnsubscribeEngine(self.mock_service, self.mock_db)

    @patch.object(UnsubscribeEngine, 'find_unsubscribe_links')
    @patch.object(UnsubscribeEngine, 'create_delete_filter')
    @patch.object(UnsubscribeEngine, 'delete_existing_emails')
    def test_unsubscribe_and_block_domain_complete_workflow(self, mock_delete, mock_filter, mock_links):
        """Test complete workflow with all steps successful."""
        # Arrange
        domain = "workflow.com"

        mock_links.return_value = [
            {
                'unsubscribe_links': ['https://workflow.com/unsubscribe', 'mailto:unsubscribe@workflow.com'],
                'message_id': 'msg1'
            }
        ]
        mock_filter.return_value = {'success': True, 'filter_id': 'filter123'}
        mock_delete.return_value = {'success': True, 'deleted_count': 5}

        # Act
        result = self.engine.unsubscribe_and_block_domain(domain, dry_run=False)

        # Assert
        assert result['domain'] == domain
        assert len(result['steps']) == 3

        # Check each step
        assert result['steps'][0]['step'] == 'find_unsubscribe'
        assert result['steps'][0]['success'] is True

        assert result['steps'][1]['step'] == 'create_filter'
        assert result['steps'][1]['success'] is True

        assert result['steps'][2]['step'] == 'delete_existing'
        assert result['steps'][2]['success'] is True

    @patch.object(UnsubscribeEngine, 'find_unsubscribe_links')
    @patch.object(UnsubscribeEngine, 'create_delete_filter')
    @patch.object(UnsubscribeEngine, 'delete_existing_emails')
    def test_unsubscribe_and_block_domain_no_unsubscribe_links(self, mock_delete, mock_filter, mock_links):
        """Test workflow when no unsubscribe links are found."""
        # Arrange
        domain = "nolinks.com"

        mock_links.return_value = []
        mock_filter.return_value = {'success': True, 'filter_id': 'filter123'}
        mock_delete.return_value = {'success': True, 'deleted_count': 3}

        # Act
        result = self.engine.unsubscribe_and_block_domain(domain, dry_run=True)

        # Assert
        assert result['domain'] == domain
        assert result['steps'][0]['step'] == 'find_unsubscribe'
        assert result['steps'][0]['success'] is False
        assert result['steps'][0]['message'] == 'No unsubscribe links found'

    @patch.object(UnsubscribeEngine, 'find_unsubscribe_links')
    @patch.object(UnsubscribeEngine, 'create_delete_filter')
    @patch.object(UnsubscribeEngine, 'delete_existing_emails')
    def test_unsubscribe_and_block_domain_dry_run(self, mock_delete, mock_filter, mock_links):
        """Test workflow in dry run mode."""
        # Arrange
        domain = "dryrun.com"

        mock_links.return_value = [{'unsubscribe_links': ['https://dryrun.com/unsubscribe']}]
        mock_filter.return_value = {'action': 'DRY RUN - Filter not created', 'success': False}
        mock_delete.return_value = {'action': 'DRY RUN - No emails moved to trash', 'success': False}

        # Act
        result = self.engine.unsubscribe_and_block_domain(domain, dry_run=True)

        # Assert
        mock_links.assert_called_once_with(domain, sample_size=3)
        mock_filter.assert_called_once_with(domain, dry_run=True)
        mock_delete.assert_called_once_with(domain, dry_run=True)


class TestUnsubscribeEngineFilterApplication:
    """Test filter application functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = Mock()
        self.mock_db = Mock()
        self.engine = UnsubscribeEngine(self.mock_service, self.mock_db)

    def test_construct_query_from_filter_from_criteria(self):
        """Test query construction from filter criteria."""
        # Test 'from' criteria
        criteria = {'from': 'test@example.com'}
        result = self.engine._construct_query_from_filter(criteria)
        assert result == 'from:test@example.com'

    def test_construct_query_from_filter_multiple_criteria(self):
        """Test query construction with multiple criteria."""
        criteria = {
            'from': 'sender@example.com',
            'to': 'recipient@test.com',
            'subject': 'Important'
        }
        result = self.engine._construct_query_from_filter(criteria)
        expected_parts = ['from:sender@example.com', 'to:recipient@test.com', 'subject:Important']
        for part in expected_parts:
            assert part in result

    def test_construct_query_from_filter_raw_query(self):
        """Test query construction when raw query is present."""
        criteria = {
            'from': 'sender@example.com',  # This should be ignored
            'query': 'is:unread older_than:30d'  # This should be used
        }
        result = self.engine._construct_query_from_filter(criteria)
        assert result == 'is:unread older_than:30d'

    def test_construct_query_from_filter_empty_criteria(self):
        """Test query construction with empty criteria."""
        criteria = {}
        result = self.engine._construct_query_from_filter(criteria)
        assert result is None

    @patch.object(UnsubscribeEngine, 'list_existing_filters')
    def test_apply_filters_no_filters(self, mock_list_filters):
        """Test applying filters when none exist."""
        # Arrange
        mock_list_filters.return_value = []

        # Act
        result = self.engine.apply_filters(dry_run=True)

        # Assert
        assert result['total_deleted'] == 0
        assert result['message'] == 'No filters found.'

    @patch.object(UnsubscribeEngine, 'list_existing_filters')
    def test_apply_filters_no_delete_filters(self, mock_list_filters):
        """Test applying filters when no delete filters exist."""
        # Arrange
        mock_list_filters.return_value = [
            {
                'id': 'filter1',
                'criteria': {'from': 'test.com'},
                'action': {'addLabelIds': ['IMPORTANT']}  # Not a delete filter
            }
        ]

        # Act
        result = self.engine.apply_filters(dry_run=True)

        # Assert
        assert result['processed_filters'] == 0

    @patch.object(UnsubscribeEngine, 'list_existing_filters')
    def test_apply_filters_dry_run_mode(self, mock_list_filters):
        """Test applying filters in dry run mode."""
        # Arrange
        mock_list_filters.return_value = [
            {
                'id': 'filter1',
                'criteria': {'from': 'spam.com'},
                'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
            }
        ]

        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}, {'id': 'msg3'}]
        }

        # Act
        result = self.engine.apply_filters(dry_run=True)

        # Assert
        assert result['processed_filters'] == 1
        assert result['total_deleted'] == 3
        assert result['dry_run'] is True
        # Should not make batch modify calls
        self.mock_service.users().messages().batchModify.assert_not_called()

    @patch.object(UnsubscribeEngine, 'list_existing_filters')
    @patch('time.sleep')  # Mock sleep for faster tests
    def test_apply_filters_execute_mode(self, mock_sleep, mock_list_filters):
        """Test applying filters in execute mode."""
        # Arrange
        mock_list_filters.return_value = [
            {
                'id': 'filter1',
                'criteria': {'from': 'unwanted.com'},
                'action': {'addLabelIds': ['TRASH']}
            }
        ]

        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': [{'id': f'msg{i}'} for i in range(75)]  # More than batch size
        }
        self.mock_service.users().messages().batchModify.return_value.execute.return_value = {}

        # Act
        result = self.engine.apply_filters(dry_run=False)

        # Assert
        assert result['processed_filters'] == 1
        assert result['total_deleted'] == 75
        assert result['dry_run'] is False

        # Should make multiple batch calls (75 messages / 50 per batch = 2 batches)
        assert self.mock_service.users().messages().batchModify.call_count == 2

    @patch.object(UnsubscribeEngine, 'list_existing_filters')
    def test_apply_filters_with_http_error(self, mock_list_filters):
        """Test applying filters with HTTP error."""
        # Arrange
        mock_list_filters.return_value = [
            {
                'id': 'filter1',
                'criteria': {'from': 'error.com'},
                'action': {'addLabelIds': ['TRASH']}
            }
        ]

        self.mock_service.users().messages().list.side_effect = HttpError(
            resp=Mock(status=500), content=b'Server Error'
        )

        # Act
        result = self.engine.apply_filters(dry_run=False)

        # Assert
        assert result['processed_filters'] == 1
        assert result['total_deleted'] == 0  # Nothing deleted due to error


class TestUnsubscribeEngineEdgeCases:
    """Test edge cases and error scenarios."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = Mock()
        self.mock_db = Mock()
        self.engine = UnsubscribeEngine(self.mock_service, self.mock_db)

    def test_extract_unsubscribe_info_malformed_headers(self):
        """Test handling malformed List-Unsubscribe headers."""
        # Arrange
        message = {
            'id': 'malformed',
            'payload': {
                'headers': [
                    {'name': 'List-Unsubscribe', 'value': 'malformed header without proper format'},
                    {'name': 'Subject', 'value': 'Test'}
                ],
                'body': {'data': base64.urlsafe_b64encode('content'.encode()).decode().rstrip('=')}
            }
        }

        # Act
        result = self.engine._extract_unsubscribe_info(message, "test.com")

        # Assert - Should still work, just no links extracted from header
        assert result is None or len(result.get('unsubscribe_links', [])) == 0

    def test_extract_email_content_empty_payload(self):
        """Test extracting content from empty payload."""
        # Arrange
        payload = {}

        # Act
        result = self.engine._extract_email_content(payload)

        # Assert
        assert result == ""

    def test_extract_part_content_unknown_mime_type(self):
        """Test extracting content from unknown MIME type."""
        # Arrange
        part = {
            'mimeType': 'application/octet-stream',
            'body': {'data': base64.urlsafe_b64encode('binary data'.encode()).decode()}
        }

        # Act
        result = self.engine._extract_part_content(part)

        # Assert
        assert result == ""

    def test_find_unsubscribe_links_large_sample_size(self):
        """Test finding unsubscribe links with large sample size."""
        # Arrange
        domain = "newsletter.com"
        large_message_list = [{'id': f'msg{i}'} for i in range(100)]

        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': large_message_list
        }

        # Mock message with no unsubscribe info to speed up test
        mock_message = {
            'id': 'msg1',
            'payload': {
                'headers': [{'name': 'Subject', 'value': 'No unsubscribe'}],
                'body': {'data': base64.urlsafe_b64encode('Regular content'.encode()).decode().rstrip('=')}
            }
        }
        self.mock_service.users().messages().get.return_value.execute.return_value = mock_message

        # Act
        result = self.engine.find_unsubscribe_links(domain, sample_size=50)

        # Assert
        # Should limit to sample_size, not process all messages
        assert self.mock_service.users().messages().list.call_args[1]['maxResults'] == 50

    def test_delete_existing_emails_rate_limiting(self):
        """Test that rate limiting sleep is called during batch processing."""
        # Arrange
        domain = "ratelimit.com"
        # Create enough messages to trigger multiple batches
        mock_messages = [{'id': f'msg{i}'} for i in range(120)]

        self.mock_service.users().messages().list.return_value.execute.return_value = {
            'messages': mock_messages
        }
        self.mock_service.users().messages().modify.return_value.execute.return_value = {}

        # Act
        with patch('time.sleep') as mock_sleep:
            result = self.engine.delete_existing_emails(domain, dry_run=False)

            # Assert
            assert result['deleted_count'] == 120
            # Should call sleep for rate limiting (once per batch, 120/50 = 3 batches)
            assert mock_sleep.call_count >= 2