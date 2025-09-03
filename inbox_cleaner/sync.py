"""Gmail synchronization module for true bi-directional sync."""

from typing import Set, Dict, Any, List, Optional, Callable
from googleapiclient.errors import HttpError
from .database import DatabaseManager
from .extractor import GmailExtractor


class GmailSynchronizer:
    """Handles true synchronization between Gmail and local database."""

    def __init__(self, service: Any, db_manager: DatabaseManager, extractor: GmailExtractor) -> None:
        """Initialize synchronizer with Gmail service, database manager, and extractor."""
        self.service = service
        self.db_manager = db_manager
        self.extractor = extractor

    def get_gmail_message_ids(self, query: str = "", max_results: Optional[int] = None) -> Set[str]:
        """Get all message IDs from Gmail."""
        message_ids = set()
        page_token = None
        fetched_count = 0

        while True:
            try:
                # Build request parameters
                batch_size = 500  # Maximum allowed by Gmail API
                if max_results and fetched_count + batch_size > max_results:
                    batch_size = max_results - fetched_count

                params = {
                    'userId': 'me',
                    'maxResults': batch_size,
                }
                if query:
                    params['q'] = query
                if page_token:
                    params['pageToken'] = page_token

                # Make API call
                response = self.service.users().messages().list(**params).execute()

                # Extract message IDs
                messages = response.get('messages', [])
                if not messages:
                    break

                message_ids.update(msg['id'] for msg in messages)
                fetched_count += len(messages)

                # Check if we've reached the limit
                if max_results and fetched_count >= max_results:
                    break

                # Check for next page
                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            except HttpError as e:
                if e.resp.status == 404:
                    break  # No more messages
                raise

        return message_ids

    def get_database_message_ids(self) -> Set[str]:
        """Get all message IDs from local database."""
        message_ids = self.db_manager.get_all_message_ids()
        return set(message_ids)

    def sync(self, query: str = "", max_results: Optional[int] = None, progress_callback: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, Any]:
        """
        Perform true sync using Gmail as source of truth.

        Args:
            query: Gmail search query to limit sync scope
            max_results: Maximum number of emails to process from Gmail
            progress_callback: Optional callback for progress updates (operation, current, total)

        Returns:
            Dict with sync results: {'added': int, 'removed': int, 'error': str or None}
        """
        result = {'added': 0, 'removed': 0, 'error': None}

        try:
            # Step 1: Get all message IDs from Gmail and database
            if progress_callback:
                progress_callback("Fetching Gmail message IDs", 0, 100)

            gmail_ids = self.get_gmail_message_ids(query, max_results)

            if progress_callback:
                progress_callback("Fetching database message IDs", 20, 100)

            db_ids = self.get_database_message_ids()

            # Step 2: Identify differences
            if progress_callback:
                progress_callback("Analyzing differences", 40, 100)

            # Messages in Gmail but not in database (need to add)
            new_message_ids = gmail_ids - db_ids

            # Messages in database but not in Gmail (need to remove)
            deleted_message_ids = db_ids - gmail_ids

            # Step 3: Add new emails
            if new_message_ids:
                if progress_callback:
                    progress_callback(f"Adding {len(new_message_ids)} new emails", 60, 100)

                try:
                    # Convert to list for batch processing
                    new_ids_list = list(new_message_ids)

                    # Process in smaller batches to avoid timeouts and provide better progress
                    batch_size = 100  # Process 100 emails at a time
                    for i in range(0, len(new_ids_list), batch_size):
                        batch_ids = new_ids_list[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (len(new_ids_list) + batch_size - 1) // batch_size

                        if progress_callback:
                            progress_callback(f"Extracting batch {batch_num}/{total_batches} ({len(batch_ids)} emails)", 60 + (i * 20) // len(new_ids_list), 100)

                        # Extract this batch
                        batch_emails = self.extractor.extract_batch(batch_ids)

                        # Insert emails from this batch
                        for email in batch_emails:
                            try:
                                if self.db_manager.insert_email(email):
                                    result['added'] += 1
                            except Exception as e:
                                # Log individual email errors but continue
                                if result.get('error') is None:
                                    result['error'] = f"Some emails failed to insert: {str(e)}"

                except Exception as e:
                    result['error'] = f"Failed to extract new emails: {str(e)}"

            # Step 4: Remove deleted emails
            if deleted_message_ids:
                if progress_callback:
                    progress_callback("Removing deleted emails", 80, 100)

                for message_id in deleted_message_ids:
                    try:
                        if self.db_manager.delete_email(message_id):
                            result['removed'] += 1
                    except Exception as e:
                        if result.get('error') is None:
                            result['error'] = f"Some emails failed to delete: {str(e)}"

            if progress_callback:
                progress_callback("Sync complete", 100, 100)

        except Exception as e:
            result['error'] = f"Sync failed: {str(e)}"

        return result

    def validate_sync(self, query: str = "", max_results: Optional[int] = None) -> Dict[str, Any]:
        """
        Validate that the database is properly synced with Gmail.

        Args:
            query: Gmail search query to limit validation scope
            max_results: Maximum number of emails to validate from Gmail

        Returns:
            Dict with validation results: {'in_sync': bool, 'gmail_count': int, 'db_count': int, 'differences': Dict}
        """
        try:
            gmail_ids = self.get_gmail_message_ids(query, max_results)
            db_ids = self.get_database_message_ids()

            missing_from_db = gmail_ids - db_ids
            extra_in_db = db_ids - gmail_ids

            return {
                'in_sync': len(missing_from_db) == 0 and len(extra_in_db) == 0,
                'gmail_count': len(gmail_ids),
                'db_count': len(db_ids),
                'differences': {
                    'missing_from_db': list(missing_from_db),
                    'extra_in_db': list(extra_in_db)
                }
            }
        except Exception as e:
            return {
                'in_sync': False,
                'error': f"Validation failed: {str(e)}"
            }