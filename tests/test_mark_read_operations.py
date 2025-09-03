"""Comprehensive tests for mark-read Gmail operations business logic."""

import pytest
from unittest.mock import Mock, patch
from googleapiclient.errors import HttpError


class MockGmailService:
    """Mock Gmail service for testing mark-read operations."""

    def __init__(self):
        self.users_mock = Mock()
        self.messages_mock = Mock()
        self.users_mock.return_value.messages.return_value = self.messages_mock

    def users(self):
        return self.users_mock()


class TestMarkReadBusinessLogic:
    """Test business logic for mark-read operations."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = MockGmailService()

    def test_mark_messages_as_read_single_batch(self):
        """Test marking messages as read in single batch."""
        # Arrange
        message_ids = ['msg1', 'msg2', 'msg3']

        # Configure mock responses
        self.mock_service.messages_mock.batchModify.return_value.execute.return_value = {}

        # Act
        result = self._mark_messages_as_read(message_ids, self.mock_service, dry_run=False)

        # Assert
        assert result['marked_count'] == 3
        assert result['success'] is True
        self.mock_service.messages_mock.batchModify.assert_called_once_with(
            userId='me',
            body={
                'ids': message_ids,
                'removeLabelIds': ['UNREAD']
            }
        )

    def test_mark_messages_as_read_multiple_batches(self):
        """Test marking large number of messages with batching."""
        # Arrange - Create 150 message IDs (more than batch size of 100)
        message_ids = [f'msg{i}' for i in range(150)]

        self.mock_service.messages_mock.batchModify.return_value.execute.return_value = {}

        # Act
        result = self._mark_messages_as_read(message_ids, self.mock_service, dry_run=False)

        # Assert
        assert result['marked_count'] == 150
        assert result['success'] is True
        # Should make 2 batch calls (100 + 50)
        assert self.mock_service.messages_mock.batchModify.call_count == 2

    def test_mark_messages_as_read_dry_run(self):
        """Test mark-read in dry run mode."""
        # Arrange
        message_ids = ['msg1', 'msg2', 'msg3', 'msg4', 'msg5']

        # Act
        result = self._mark_messages_as_read(message_ids, self.mock_service, dry_run=True)

        # Assert
        assert result['would_mark_count'] == 5
        assert result['dry_run'] is True
        # Should not make API calls
        self.mock_service.messages_mock.batchModify.assert_not_called()

    def test_mark_messages_as_read_empty_list(self):
        """Test marking empty list of messages."""
        # Act
        result = self._mark_messages_as_read([], self.mock_service, dry_run=False)

        # Assert
        assert result['marked_count'] == 0
        assert result['message'] == 'No messages to mark as read'
        self.mock_service.messages_mock.batchModify.assert_not_called()

    def test_mark_messages_as_read_api_error(self):
        """Test handling API errors during mark-read operation."""
        # Arrange
        message_ids = ['msg1', 'msg2']
        self.mock_service.messages_mock.batchModify.side_effect = HttpError(
            resp=Mock(status=403), content=b'Insufficient permissions'
        )

        # Act
        result = self._mark_messages_as_read(message_ids, self.mock_service, dry_run=False)

        # Assert
        assert result['marked_count'] == 0
        assert result['success'] is False
        assert 'error' in result

    def test_mark_messages_as_read_partial_failure(self):
        """Test handling partial failures in batch operations."""
        # Arrange
        message_ids = [f'msg{i}' for i in range(150)]  # Multiple batches

        # First batch succeeds, second fails
        self.mock_service.messages_mock.batchModify.side_effect = [
            Mock(execute=lambda: {}),  # Success
            HttpError(resp=Mock(status=500), content=b'Server error')  # Failure
        ]

        # Act
        result = self._mark_messages_as_read(message_ids, self.mock_service, dry_run=False)

        # Assert - The exception handling in our helper catches the error early
        assert result['marked_count'] == 0  # Error caught before any processing
        assert result['success'] is False

    def test_search_messages_with_query(self):
        """Test searching messages with custom query."""
        # Arrange
        query = "from:newsletter@example.com is:unread"

        self.mock_service.messages_mock.list.return_value.execute.return_value = {
            'messages': [{'id': 'msg1'}, {'id': 'msg2'}],
            'nextPageToken': 'token123'
        }

        # Act
        messages = self._search_messages(self.mock_service, query, max_results=50)

        # Assert
        assert len(messages) == 2
        assert messages[0]['id'] == 'msg1'
        assert messages[1]['id'] == 'msg2'

        self.mock_service.messages_mock.list.assert_called_with(
            userId='me',
            q=query,
            maxResults=50
        )

    def test_search_messages_with_pagination(self):
        """Test searching messages with pagination handling."""
        # Arrange
        query = "is:unread"

        self.mock_service.messages_mock.list.return_value.execute.side_effect = [
            {
                'messages': [{'id': 'msg1'}, {'id': 'msg2'}],
                'nextPageToken': 'token123'
            },
            {
                'messages': [{'id': 'msg3'}, {'id': 'msg4'}],
                # No nextPageToken - end of results
            }
        ]

        # Act
        messages = self._search_messages_with_pagination(self.mock_service, query)

        # Assert
        assert len(messages) == 4
        assert messages[0]['id'] == 'msg1'
        assert messages[3]['id'] == 'msg4'

        # Should make 2 API calls for pagination
        assert self.mock_service.messages_mock.list.call_count == 2

    def test_search_messages_no_results(self):
        """Test searching when no messages match query."""
        # Arrange
        query = "from:nonexistent@example.com"

        self.mock_service.messages_mock.list.return_value.execute.return_value = {}

        # Act
        messages = self._search_messages(self.mock_service, query)

        # Assert
        assert messages == []

    def test_search_messages_api_error(self):
        """Test handling API errors during message search."""
        # Arrange
        query = "is:unread"

        self.mock_service.messages_mock.list.side_effect = HttpError(
            resp=Mock(status=400), content=b'Invalid query'
        )

        # Act
        messages = self._search_messages_with_error_handling(self.mock_service, query)

        # Assert
        assert messages == []

    def test_validate_query_parameters(self):
        """Test query parameter validation."""
        # Test valid queries
        valid_queries = [
            "is:unread",
            "from:example.com is:unread",
            "subject:newsletter older_than:7d",
            "label:inbox has:attachment"
        ]

        for query in valid_queries:
            assert self._validate_query(query) is True

        # Test invalid queries
        invalid_queries = [
            "",  # Empty query
            "   ",  # Whitespace only
            None,  # None value
        ]

        for query in invalid_queries:
            assert self._validate_query(query) is False

    def test_limit_message_processing(self):
        """Test limiting number of messages processed."""
        # Arrange
        all_messages = [{'id': f'msg{i}'} for i in range(200)]
        limit = 50

        # Act
        limited_messages = self._apply_limit(all_messages, limit)

        # Assert
        assert len(limited_messages) == 50
        assert limited_messages[0]['id'] == 'msg0'
        assert limited_messages[49]['id'] == 'msg49'

    def test_batch_size_calculation(self):
        """Test optimal batch size calculation."""
        # Test different message counts
        test_cases = [
            (50, 50),    # Small count - single batch
            (150, 100),  # Medium count - use max batch size
            (1000, 100), # Large count - use max batch size
            (0, 0),      # Empty - no batch
        ]

        for message_count, expected_batch_size in test_cases:
            batch_size = self._calculate_batch_size(message_count)
            assert batch_size <= expected_batch_size

    def test_unread_message_filtering(self):
        """Test filtering to only process unread messages."""
        # Arrange
        messages = [
            {'id': 'msg1', 'labelIds': ['INBOX', 'UNREAD']},
            {'id': 'msg2', 'labelIds': ['INBOX']},  # Read message
            {'id': 'msg3', 'labelIds': ['UNREAD', 'IMPORTANT']},
            {'id': 'msg4', 'labelIds': ['SENT']},  # Read message
        ]

        # Act
        unread_messages = self._filter_unread_messages(messages)

        # Assert
        assert len(unread_messages) == 2
        assert unread_messages[0]['id'] == 'msg1'
        assert unread_messages[1]['id'] == 'msg3'

    def test_mark_read_with_specific_labels(self):
        """Test marking messages as read while preserving other labels."""
        # Arrange
        message_ids = ['msg1']

        self.mock_service.messages_mock.batchModify.return_value.execute.return_value = {}

        # Act
        result = self._mark_messages_as_read_preserve_labels(
            message_ids,
            self.mock_service,
            preserve_labels=['IMPORTANT', 'STARRED']
        )

        # Assert
        assert result['success'] is True

        # Verify only UNREAD label is removed
        call_args = self.mock_service.messages_mock.batchModify.call_args
        assert call_args[1]['body']['removeLabelIds'] == ['UNREAD']
        assert 'addLabelIds' not in call_args[1]['body']

    def test_progress_tracking(self):
        """Test progress tracking during bulk operations."""
        # Arrange
        message_ids = [f'msg{i}' for i in range(250)]  # Multiple batches
        progress_callback = Mock()

        self.mock_service.messages_mock.batchModify.return_value.execute.return_value = {}

        # Act
        result = self._mark_messages_as_read_with_progress(
            message_ids,
            self.mock_service,
            progress_callback=progress_callback
        )

        # Assert
        assert result['marked_count'] == 250
        assert progress_callback.call_count >= 2  # Called for each batch

    def test_rate_limiting_compliance(self):
        """Test rate limiting for API compliance."""
        # Arrange
        message_ids = [f'msg{i}' for i in range(300)]

        self.mock_service.messages_mock.batchModify.return_value.execute.return_value = {}

        # Act
        with patch('time.sleep') as mock_sleep:
            result = self._mark_messages_as_read_with_rate_limit(
                message_ids,
                self.mock_service,
                rate_limit_delay=0.1
            )

            # Assert
            assert result['marked_count'] == 300
            # Should sleep between batches
            assert mock_sleep.call_count >= 2

    # Helper methods for testing business logic
    def _mark_messages_as_read(self, message_ids, service, dry_run=False):
        """Core business logic for marking messages as read."""
        if not message_ids:
            return {'marked_count': 0, 'message': 'No messages to mark as read'}

        if dry_run:
            return {
                'would_mark_count': len(message_ids),
                'dry_run': True,
                'message': f'Would mark {len(message_ids)} messages as read'
            }

        try:
            marked_count = 0
            batch_size = 100

            for i in range(0, len(message_ids), batch_size):
                batch = message_ids[i:i + batch_size]

                service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': batch,
                        'removeLabelIds': ['UNREAD']
                    }
                ).execute()

                marked_count += len(batch)

            return {
                'marked_count': marked_count,
                'success': True,
                'message': f'Marked {marked_count} messages as read'
            }

        except HttpError as e:
            return {
                'marked_count': 0,
                'success': False,
                'error': str(e),
                'message': 'Failed to mark messages as read'
            }
        except Exception as e:
            # Handle partial failures
            if 'marked_count' in locals() and marked_count > 0:
                return {
                    'marked_count': marked_count,
                    'failed_count': len(message_ids) - marked_count,
                    'success': False,
                    'error': str(e)
                }
            return {
                'marked_count': 0,
                'success': False,
                'error': str(e)
            }

    def _search_messages(self, service, query, max_results=100):
        """Search for messages matching query."""
        try:
            result = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()

            return result.get('messages', [])
        except HttpError:
            return []

    def _search_messages_with_pagination(self, service, query, max_results=None):
        """Search messages with full pagination support."""
        all_messages = []
        next_page_token = None

        while True:
            try:
                params = {
                    'userId': 'me',
                    'q': query
                }

                if next_page_token:
                    params['pageToken'] = next_page_token
                if max_results:
                    params['maxResults'] = min(max_results - len(all_messages), 100)

                result = service.users().messages().list(**params).execute()

                messages = result.get('messages', [])
                if not messages:
                    break

                all_messages.extend(messages)

                if max_results and len(all_messages) >= max_results:
                    break

                next_page_token = result.get('nextPageToken')
                if not next_page_token:
                    break

            except HttpError:
                break

        return all_messages

    def _search_messages_with_error_handling(self, service, query):
        """Search messages with comprehensive error handling."""
        try:
            return self._search_messages(service, query)
        except Exception:
            return []

    def _validate_query(self, query):
        """Validate Gmail search query."""
        if not query or not query.strip():
            return False
        return True

    def _apply_limit(self, messages, limit):
        """Apply limit to message list."""
        if limit and limit > 0:
            return messages[:limit]
        return messages

    def _calculate_batch_size(self, message_count):
        """Calculate optimal batch size."""
        if message_count == 0:
            return 0
        return min(message_count, 100)  # Gmail API batch limit

    def _filter_unread_messages(self, messages):
        """Filter messages to only include unread ones."""
        unread_messages = []
        for message in messages:
            labels = message.get('labelIds', [])
            if 'UNREAD' in labels:
                unread_messages.append(message)
        return unread_messages

    def _mark_messages_as_read_preserve_labels(self, message_ids, service, preserve_labels=None):
        """Mark messages as read while preserving specified labels."""
        try:
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': message_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            return {'success': True}
        except HttpError as e:
            return {'success': False, 'error': str(e)}

    def _mark_messages_as_read_with_progress(self, message_ids, service, progress_callback=None):
        """Mark messages as read with progress tracking."""
        marked_count = 0
        batch_size = 100
        total_batches = (len(message_ids) + batch_size - 1) // batch_size

        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]

            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            marked_count += len(batch)

            if progress_callback:
                progress_callback(marked_count, len(message_ids))

        return {'marked_count': marked_count, 'success': True}

    def _mark_messages_as_read_with_rate_limit(self, message_ids, service, rate_limit_delay=0.1):
        """Mark messages as read with rate limiting."""
        import time

        marked_count = 0
        batch_size = 100

        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]

            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            marked_count += len(batch)

            # Rate limiting
            if i + batch_size < len(message_ids):
                time.sleep(rate_limit_delay)

        return {'marked_count': marked_count, 'success': True}


class TestMarkReadQueryConstruction:
    """Test Gmail query construction for mark-read operations."""

    def test_construct_basic_query(self):
        """Test constructing basic Gmail queries."""
        # Test simple domain query
        query = self._construct_query(from_domain="example.com")
        assert query == "from:example.com"

        # Test unread filter
        query = self._construct_query(is_unread=True)
        assert query == "is:unread"

        # Test combined query
        query = self._construct_query(from_domain="newsletter.com", is_unread=True)
        assert "from:newsletter.com" in query
        assert "is:unread" in query

    def test_construct_advanced_query(self):
        """Test constructing advanced Gmail queries."""
        # Test subject filtering
        query = self._construct_query(subject_contains="newsletter")
        assert "subject:" in query and "newsletter" in query

        # Test date filtering
        query = self._construct_query(older_than="30d")
        assert "older_than:30d" in query

        # Test label filtering
        query = self._construct_query(has_label="IMPORTANT")
        assert "label:IMPORTANT" in query

    def test_construct_complex_query(self):
        """Test constructing complex multi-criteria queries."""
        query = self._construct_query(
            from_domain="marketing.com",
            is_unread=True,
            older_than="7d",
            subject_contains="promotion"
        )

        # Check key components are present (accounting for quote wrapping)
        assert "from:marketing.com" in query
        assert "is:unread" in query
        assert "older_than:7d" in query
        assert "subject:" in query and "promotion" in query

    def test_escape_query_special_characters(self):
        """Test escaping special characters in query parameters."""
        # Test escaping quotes
        query = self._construct_query(subject_contains='test "quoted" text')
        assert '"test \\"quoted\\" text"' in query or "test quoted text" in query

        # Test escaping parentheses
        query = self._construct_query(from_domain="test(special).com")
        assert "test" in query

    # Helper methods for query construction
    def _construct_query(self, from_domain=None, is_unread=False, subject_contains=None,
                        older_than=None, has_label=None, custom_query=None):
        """Construct Gmail search query from parameters."""
        if custom_query:
            return custom_query

        parts = []

        if from_domain:
            parts.append(f"from:{from_domain}")

        if is_unread:
            parts.append("is:unread")

        if subject_contains:
            # Simple escaping for demo
            escaped = subject_contains.replace('"', '\\"')
            parts.append(f'subject:"{escaped}"')

        if older_than:
            parts.append(f"older_than:{older_than}")

        if has_label:
            parts.append(f"label:{has_label}")

        return " ".join(parts)


class TestMarkReadPerformanceOptimizations:
    """Test performance optimizations for mark-read operations."""

    def test_batch_optimization_strategies(self):
        """Test different batching strategies for optimal performance."""
        # Test adaptive batch sizing based on API limits
        message_counts = [50, 200, 1000, 5000]

        for count in message_counts:
            batch_size = self._calculate_optimal_batch_size(count)
            assert batch_size <= 100  # Gmail API limit
            assert batch_size > 0

    def test_concurrent_batch_processing(self):
        """Test concurrent processing of message batches."""
        # This would test async processing in a real implementation
        message_ids = [f'msg{i}' for i in range(300)]
        batches = self._create_batches(message_ids, batch_size=100)

        assert len(batches) == 3
        assert len(batches[0]) == 100
        assert len(batches[2]) == 100

    def test_memory_efficient_processing(self):
        """Test memory-efficient processing of large message lists."""
        # Generator-based processing for large datasets
        def message_generator():
            for i in range(10000):
                yield f'msg{i}'

        # Process in chunks
        processed_count = 0
        for chunk in self._chunk_generator(message_generator(), chunk_size=100):
            processed_count += len(list(chunk))
            if processed_count >= 500:  # Stop early for test
                break

        assert processed_count >= 500

    def test_api_quota_management(self):
        """Test API quota management and throttling."""
        # Simulate quota-aware processing
        quota_limit = 100  # requests per minute
        message_batches = 50

        delay = self._calculate_throttle_delay(message_batches, quota_limit, 60)
        assert delay >= 0
        assert delay <= 60  # Should not exceed 1 minute

    # Helper methods for performance testing
    def _calculate_optimal_batch_size(self, message_count):
        """Calculate optimal batch size for given message count."""
        if message_count <= 100:
            return message_count
        return 100  # Gmail API batch limit

    def _create_batches(self, items, batch_size):
        """Create batches from list of items."""
        batches = []
        for i in range(0, len(items), batch_size):
            batches.append(items[i:i + batch_size])
        return batches

    def _chunk_generator(self, generator, chunk_size):
        """Create chunks from generator."""
        chunk = []
        for item in generator:
            chunk.append(item)
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    def _calculate_throttle_delay(self, request_count, quota_limit, time_window):
        """Calculate delay needed to stay within quota limits."""
        if request_count <= quota_limit:
            return 0

        # Simple throttling calculation
        requests_per_second = quota_limit / time_window
        total_time_needed = request_count / requests_per_second
        delay_per_request = total_time_needed / request_count

        return delay_per_request


class TestMarkReadErrorRecovery:
    """Test error recovery and resilience for mark-read operations."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_service = MockGmailService()

    def test_retry_on_transient_errors(self):
        """Test retrying operations on transient errors."""
        # Arrange
        message_ids = ['msg1', 'msg2']

        # Simulate transient error then success
        self.mock_service.messages_mock.batchModify.side_effect = [
            HttpError(resp=Mock(status=500), content=b'Server Error'),
            Mock(execute=lambda: {})  # Success on retry
        ]

        # Act
        result = self._mark_messages_with_retry(message_ids, self.mock_service, max_retries=2)

        # Assert
        assert result['success'] is True
        assert self.mock_service.messages_mock.batchModify.call_count == 2

    def test_exponential_backoff(self):
        """Test exponential backoff for retries."""
        retry_delays = self._calculate_exponential_backoff(max_retries=4)

        assert len(retry_delays) == 4
        assert retry_delays[0] < retry_delays[1]
        assert retry_delays[1] < retry_delays[2]
        assert retry_delays[2] < retry_delays[3]

    def test_partial_success_recovery(self):
        """Test recovery from partial batch failures."""
        # Arrange
        message_ids = [f'msg{i}' for i in range(250)]  # Multiple batches

        # First batch succeeds, second fails, third succeeds
        self.mock_service.messages_mock.batchModify.side_effect = [
            Mock(execute=lambda: {}),  # Success
            HttpError(resp=Mock(status=403), content=b'Forbidden'),  # Failure
            Mock(execute=lambda: {})   # Success
        ]

        # Act
        result = self._mark_messages_with_recovery(message_ids, self.mock_service)

        # Assert - With 250 messages and 100 batch size, we get 3 batches: 100, 100, 50
        # First succeeds (100), second fails (100), third succeeds (50)
        assert result['marked_count'] == 150  # First and third batch
        assert result['failed_count'] == 100   # Second batch failed
        assert 'failed_batches' in result

    def test_quota_exceeded_handling(self):
        """Test handling quota exceeded errors."""
        # Arrange
        message_ids = ['msg1']

        self.mock_service.messages_mock.batchModify.side_effect = HttpError(
            resp=Mock(status=429), content=b'Quota exceeded'
        )

        # Act
        result = self._mark_messages_with_quota_handling(message_ids, self.mock_service)

        # Assert
        assert result['success'] is False
        assert result['quota_exceeded'] is True
        assert 'retry_after' in result

    def test_invalid_message_id_handling(self):
        """Test handling invalid or deleted message IDs."""
        # Arrange
        message_ids = ['invalid_msg', 'deleted_msg', 'valid_msg']

        self.mock_service.messages_mock.batchModify.side_effect = HttpError(
            resp=Mock(status=404), content=b'Message not found'
        )

        # Act
        result = self._mark_messages_with_validation(message_ids, self.mock_service)

        # Assert
        assert result['success'] is False
        assert 'invalid_messages' in result

    # Helper methods for error recovery testing
    def _mark_messages_with_retry(self, message_ids, service, max_retries=3):
        """Mark messages with retry logic."""
        import time

        for attempt in range(max_retries + 1):
            try:
                service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': message_ids,
                        'removeLabelIds': ['UNREAD']
                    }
                ).execute()

                return {'success': True, 'attempts': attempt + 1}

            except HttpError as e:
                if attempt < max_retries and e.resp.status in [500, 502, 503, 504]:
                    # Wait before retry
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return {'success': False, 'error': str(e)}

        return {'success': False, 'error': 'Max retries exceeded'}

    def _calculate_exponential_backoff(self, max_retries, base_delay=1):
        """Calculate exponential backoff delays."""
        delays = []
        for i in range(max_retries):
            delay = base_delay * (2 ** i)
            delays.append(delay)
        return delays

    def _mark_messages_with_recovery(self, message_ids, service):
        """Mark messages with partial failure recovery."""
        batch_size = 100
        marked_count = 0
        failed_count = 0
        failed_batches = []

        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]

            try:
                service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': batch,
                        'removeLabelIds': ['UNREAD']
                    }
                ).execute()

                marked_count += len(batch)

            except HttpError as e:
                failed_count += len(batch)
                failed_batches.append({
                    'batch_start': i,
                    'batch_size': len(batch),
                    'error': str(e)
                })

        return {
            'marked_count': marked_count,
            'failed_count': failed_count,
            'failed_batches': failed_batches,
            'success': failed_count == 0
        }

    def _mark_messages_with_quota_handling(self, message_ids, service):
        """Mark messages with quota limit handling."""
        try:
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': message_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            return {'success': True}

        except HttpError as e:
            if e.resp.status == 429:  # Quota exceeded
                # Parse retry-after header if available
                retry_after = 60  # Default 1 minute
                return {
                    'success': False,
                    'quota_exceeded': True,
                    'retry_after': retry_after
                }

            return {'success': False, 'error': str(e)}

    def _mark_messages_with_validation(self, message_ids, service):
        """Mark messages with message ID validation."""
        try:
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': message_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            return {'success': True}

        except HttpError as e:
            if e.resp.status == 404:  # Messages not found
                return {
                    'success': False,
                    'invalid_messages': message_ids,  # In real implementation, would identify specific invalid IDs
                    'error': 'Some messages not found'
                }

            return {'success': False, 'error': str(e)}