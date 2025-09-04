# tests/test_sync.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from inbox_cleaner.extractor import EmailMetadata
from inbox_cleaner.sync import GmailSynchronizer


class TestGmailSynchronizer:
    def test_init_with_components(self):
        """Test that GmailSynchronizer initializes correctly with components."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        assert synchronizer.service == mock_service
        assert synchronizer.db_manager == mock_db_manager
        assert synchronizer.extractor == mock_extractor

    def test_get_gmail_message_ids_fetches_all_messages(self):
        """Test that get_gmail_message_ids fetches all message IDs from Gmail."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        # Mock Gmail API responses
        mock_service.users().messages().list.return_value.execute.side_effect = [
            {
                'messages': [{'id': 'msg1'}, {'id': 'msg2'}],
                'nextPageToken': 'token1'
            },
            {
                'messages': [{'id': 'msg3'}, {'id': 'msg4'}],
                # No nextPageToken means end of results
            }
        ]

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)
        message_ids = synchronizer.get_gmail_message_ids()

        assert message_ids == {'msg1', 'msg2', 'msg3', 'msg4'}
        assert mock_service.users().messages().list.call_count == 2

    def test_get_gmail_message_ids_respects_max_results(self):
        """Test that get_gmail_message_ids respects max_results parameter."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        # Mock Gmail API to return only the requested number of messages
        def mock_list_execute(**kwargs):
            max_results = kwargs.get('maxResults', 500)
            if max_results == 2:
                return {'messages': [{'id': 'msg1'}, {'id': 'msg2'}]}
            return {'messages': [{'id': 'msg1'}, {'id': 'msg2'}, {'id': 'msg3'}]}

        mock_service.users().messages().list.return_value.execute.side_effect = lambda: mock_list_execute(maxResults=2)

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)
        message_ids = synchronizer.get_gmail_message_ids(max_results=2)

        # Should only get 2 messages due to limit
        assert len(message_ids) == 2
        assert message_ids == {'msg1', 'msg2'}

    def test_get_database_message_ids_fetches_all_stored_ids(self):
        """Test that get_database_message_ids fetches all message IDs from database."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        # Mock database response
        mock_db_manager.get_all_message_ids.return_value = ['db_msg1', 'db_msg2', 'db_msg3']

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)
        message_ids = synchronizer.get_database_message_ids()

        assert message_ids == {'db_msg1', 'db_msg2', 'db_msg3'}
        mock_db_manager.get_all_message_ids.assert_called_once()

    def test_sync_identifies_new_emails_to_add(self):
        """Test that sync correctly identifies new emails that need to be added."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        # Mock the helper methods
        synchronizer.get_gmail_message_ids = MagicMock(return_value={'msg1', 'msg2', 'msg3', 'msg4'})
        synchronizer.get_database_message_ids = MagicMock(return_value={'msg2', 'msg3'})  # Missing msg1, msg4

        # Mock extractor to return email metadata
        mock_email1 = EmailMetadata(
            message_id='msg1', thread_id='thread1', sender_email='test@example.com',
            sender_domain='example.com', sender_hash='hash1', subject='Test 1',
            date_received=datetime.now(), labels=['INBOX'], snippet='Test snippet 1'
        )
        mock_email4 = EmailMetadata(
            message_id='msg4', thread_id='thread4', sender_email='test2@example.com',
            sender_domain='example.com', sender_hash='hash4', subject='Test 4',
            date_received=datetime.now(), labels=['INBOX'], snippet='Test snippet 4'
        )
        mock_extractor.extract_batch.return_value = [mock_email1, mock_email4]

        # Mock database insertions
        mock_db_manager.insert_email.return_value = True

        result = synchronizer.sync()

        # Verify new emails were identified and extracted
        mock_extractor.extract_batch.assert_called_once()
        called_ids = mock_extractor.extract_batch.call_args[0][0]
        assert set(called_ids) == {'msg1', 'msg4'}

        # Verify new emails were inserted
        assert mock_db_manager.insert_email.call_count == 2
        mock_db_manager.insert_email.assert_any_call(mock_email1)
        mock_db_manager.insert_email.assert_any_call(mock_email4)

        assert result['added'] == 2
        assert result['removed'] == 0

    def test_sync_identifies_deleted_emails_to_remove(self):
        """Test that sync correctly identifies emails that were deleted from Gmail."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        # Mock the helper methods
        synchronizer.get_gmail_message_ids = MagicMock(return_value={'msg1', 'msg2'})
        synchronizer.get_database_message_ids = MagicMock(return_value={'msg1', 'msg2', 'msg3', 'msg4'})  # msg3, msg4 deleted from Gmail

        # No new emails to add
        mock_extractor.extract_batch.return_value = []

        # Mock database deletions
        mock_db_manager.delete_email.return_value = True

        result = synchronizer.sync()

        # Verify deleted emails were removed from database
        assert mock_db_manager.delete_email.call_count == 2
        mock_db_manager.delete_email.assert_any_call('msg3')
        mock_db_manager.delete_email.assert_any_call('msg4')

        assert result['added'] == 0
        assert result['removed'] == 2

    def test_sync_handles_both_additions_and_deletions(self):
        """Test that sync correctly handles both adding new emails and removing deleted ones."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        # Gmail has: msg1, msg2, msg5, msg6
        # Database has: msg2, msg3, msg4
        # Should add: msg1, msg5, msg6
        # Should remove: msg3, msg4
        synchronizer.get_gmail_message_ids = MagicMock(return_value={'msg1', 'msg2', 'msg5', 'msg6'})
        synchronizer.get_database_message_ids = MagicMock(return_value={'msg2', 'msg3', 'msg4'})

        # Mock new emails
        mock_email1 = EmailMetadata(
            message_id='msg1', thread_id='thread1', sender_email='test@example.com',
            sender_domain='example.com', sender_hash='hash1', subject='Test 1',
            date_received=datetime.now(), labels=['INBOX'], snippet='Test snippet 1'
        )
        mock_email5 = EmailMetadata(
            message_id='msg5', thread_id='thread5', sender_email='test5@example.com',
            sender_domain='example.com', sender_hash='hash5', subject='Test 5',
            date_received=datetime.now(), labels=['INBOX'], snippet='Test snippet 5'
        )
        mock_email6 = EmailMetadata(
            message_id='msg6', thread_id='thread6', sender_email='test6@example.com',
            sender_domain='example.com', sender_hash='hash6', subject='Test 6',
            date_received=datetime.now(), labels=['INBOX'], snippet='Test snippet 6'
        )
        mock_extractor.extract_batch.return_value = [mock_email1, mock_email5, mock_email6]

        mock_db_manager.insert_email.return_value = True
        mock_db_manager.delete_email.return_value = True

        result = synchronizer.sync()

        # Verify new emails were added
        mock_extractor.extract_batch.assert_called_once()
        called_ids = mock_extractor.extract_batch.call_args[0][0]
        assert set(called_ids) == {'msg1', 'msg5', 'msg6'}

        assert mock_db_manager.insert_email.call_count == 3

        # Verify deleted emails were removed
        assert mock_db_manager.delete_email.call_count == 2
        mock_db_manager.delete_email.assert_any_call('msg3')
        mock_db_manager.delete_email.assert_any_call('msg4')

        assert result['added'] == 3
        assert result['removed'] == 2

    def test_sync_with_progress_callback(self):
        """Test that sync calls progress callback during operation."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        synchronizer.get_gmail_message_ids = MagicMock(return_value={'msg1', 'msg2'})
        synchronizer.get_database_message_ids = MagicMock(return_value={'msg3', 'msg4'})

        mock_email1 = EmailMetadata(
            message_id='msg1', thread_id='thread1', sender_email='test@example.com',
            sender_domain='example.com', sender_hash='hash1', subject='Test 1',
            date_received=datetime.now(), labels=['INBOX'], snippet='Test snippet 1'
        )
        mock_extractor.extract_batch.return_value = [mock_email1]
        mock_db_manager.insert_email.return_value = True
        mock_db_manager.delete_email.return_value = True

        progress_callback = MagicMock()

        result = synchronizer.sync(progress_callback=progress_callback)

        # Verify progress callback was called
        assert progress_callback.called

    def test_sync_handles_extraction_errors_gracefully(self):
        """Test that sync handles extraction errors without crashing."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        synchronizer.get_gmail_message_ids = MagicMock(return_value={'msg1', 'msg2'})
        synchronizer.get_database_message_ids = MagicMock(return_value=set())

        # Mock extraction failure
        mock_extractor.extract_batch.side_effect = Exception("Extraction failed")

        result = synchronizer.sync()

        # Should handle error gracefully
        assert result['added'] == 0
        assert result['removed'] == 0
        assert 'error' in result

    def test_sync_skips_existing_emails(self):
        """Test that sync doesn't try to re-add emails that already exist in database."""
        mock_service = MagicMock()
        mock_db_manager = MagicMock()
        mock_extractor = MagicMock()

        synchronizer = GmailSynchronizer(mock_service, mock_db_manager, mock_extractor)

        # Both Gmail and database have the same emails
        synchronizer.get_gmail_message_ids = MagicMock(return_value={'msg1', 'msg2', 'msg3'})
        synchronizer.get_database_message_ids = MagicMock(return_value={'msg1', 'msg2', 'msg3'})

        result = synchronizer.sync()

        # No extraction should occur since all emails already exist
        mock_extractor.extract_batch.assert_not_called()
        mock_db_manager.insert_email.assert_not_called()
        mock_db_manager.delete_email.assert_not_called()

        assert result['added'] == 0
        assert result['removed'] == 0