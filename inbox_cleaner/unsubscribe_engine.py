"""Unsubscribe and Gmail filter management engine."""

import re
import time
from typing import List, Dict, Any, Optional
from googleapiclient.errors import HttpError
from .database import DatabaseManager


class UnsubscribeEngine:
    """Handles unsubscription and Gmail filter creation for spam prevention."""

    def __init__(self, service: Any, db_manager: DatabaseManager):
        """Initialize unsubscribe engine."""
        self.service = service
        self.db = db_manager

    def find_unsubscribe_links(self, domain: str, sample_size: int = 5) -> List[Dict[str, Any]]:
        """Find unsubscribe links in recent emails from domain."""
        print(f"🔍 Searching for unsubscribe links in {domain} emails...")

        try:
            # Get recent emails from domain
            query = f"from:{domain}"
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=sample_size
            ).execute()

            messages = result.get('messages', [])
            if not messages:
                return []

            unsubscribe_info = []

            for msg in messages:
                # Get full message
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                # Extract unsubscribe info
                unsub_data = self._extract_unsubscribe_info(message, domain)
                if unsub_data:
                    unsubscribe_info.append(unsub_data)

            return unsubscribe_info

        except HttpError as e:
            print(f"❌ Failed to search emails from {domain}: {e}")
            return []

    def _extract_unsubscribe_info(self, message: Dict[str, Any], domain: str) -> Optional[Dict[str, Any]]:
        """Extract unsubscribe information from email."""
        # Check headers for List-Unsubscribe
        headers = {}
        payload = message.get('payload', {})

        for header in payload.get('headers', []):
            headers[header['name'].lower()] = header['value']

        unsubscribe_header = headers.get('list-unsubscribe', '')

        # Extract email content to find unsubscribe links
        content = self._extract_email_content(payload)

        # Look for unsubscribe patterns in content
        unsubscribe_patterns = [
            r'https?://[^\s]+unsubscribe[^\s]*',
            r'https?://[^\s]+opt[_-]?out[^\s]*',
            r'https?://[^\s]+remove[^\s]*',
            r'unsubscribe[^\s]*@[^\s]+',
            r'optout[^\s]*@[^\s]+'
        ]

        found_links = []

        # Check header
        if unsubscribe_header:
            # Extract URLs from List-Unsubscribe header
            urls = re.findall(r'<(https?://[^>]+)>', unsubscribe_header)
            emails = re.findall(r'<(mailto:[^>]+)>', unsubscribe_header)
            found_links.extend(urls)
            found_links.extend(emails)

        # Check content
        for pattern in unsubscribe_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found_links.extend(matches)

        if found_links:
            subject = headers.get('subject', '')
            return {
                'domain': domain,
                'message_id': message.get('id'),
                'subject': subject[:100],
                'unsubscribe_links': list(set(found_links)),  # Remove duplicates
                'list_unsubscribe_header': unsubscribe_header
            }

        return None

    def _extract_email_content(self, payload: Dict[str, Any]) -> str:
        """Extract text content from email payload."""
        content_parts = []

        # Check if payload has direct body content
        if 'body' in payload and 'data' in payload['body']:
            decoded = self._decode_base64(payload['body']['data'])
            if decoded:
                content_parts.append(decoded)

        # Check for multipart content
        if 'parts' in payload:
            for part in payload['parts']:
                part_content = self._extract_part_content(part)
                if part_content:
                    content_parts.append(part_content)

        return '\n'.join(content_parts)

    def _extract_part_content(self, part: Dict[str, Any]) -> str:
        """Extract content from message part."""
        mime_type = part.get('mimeType', '')

        if mime_type == 'text/plain':
            body = part.get('body', {})
            if 'data' in body:
                return self._decode_base64(body['data'])

        elif mime_type == 'text/html':
            body = part.get('body', {})
            if 'data' in body:
                html_content = self._decode_base64(body['data'])
                # Simple HTML to text conversion
                return re.sub(r'<[^>]+>', '', html_content)

        elif 'parts' in part:
            content_parts = []
            for nested_part in part['parts']:
                nested_content = self._extract_part_content(nested_part)
                if nested_content:
                    content_parts.append(nested_content)
            return '\n'.join(content_parts)

        return ""

    def _decode_base64(self, data: str) -> str:
        """Decode base64 URL-safe data."""
        try:
            import base64
            # Gmail uses URL-safe base64 without padding
            missing_padding = len(data) % 4
            if missing_padding:
                data += '=' * (4 - missing_padding)

            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        except Exception:
            return ""

    def create_delete_filter(self, domain: str, dry_run: bool = True) -> Dict[str, Any]:
        """Create Gmail filter to automatically delete emails from domain."""
        print(f"🛡️ {'DRY RUN: ' if dry_run else ''}Creating delete filter for {domain}")

        # Filter criteria
        filter_criteria = {
            'from': domain
        }

        # Filter actions
        filter_actions = {
            'addLabelIds': ['TRASH'],
            'removeLabelIds': ['INBOX', 'UNREAD']
        }

        filter_body = {
            'criteria': filter_criteria,
            'action': filter_actions
        }

        if dry_run:
            return {
                'domain': domain,
                'action': 'DRY RUN - Filter not created',
                'filter_criteria': filter_criteria,
                'filter_actions': filter_actions
            }

        try:
            # Create the filter
            filter_result = self.service.users().settings().filters().create(
                userId='me',
                body=filter_body
            ).execute()

            return {
                'domain': domain,
                'filter_id': filter_result.get('id'),
                'action': 'Filter created successfully',
                'filter_criteria': filter_criteria,
                'success': True
            }

        except HttpError as e:
            return {
                'domain': domain,
                'error': str(e),
                'action': 'Filter creation failed'
            }

    def delete_existing_emails(self, domain: str, dry_run: bool = True) -> Dict[str, Any]:
        """Move existing emails from domain to trash."""
        print(f"🗑️ {'DRY RUN: ' if dry_run else ''}Moving existing emails from {domain} to trash")

        try:
            # Search for emails from domain
            query = f"from:{domain}"
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=1000
            ).execute()

            messages = result.get('messages', [])
            if not messages:
                return {'domain': domain, 'deleted_count': 0, 'message': 'No emails found'}

            message_ids = [msg['id'] for msg in messages]

            if dry_run:
                return {
                    'domain': domain,
                    'found_count': len(message_ids),
                    'action': 'DRY RUN - No emails moved to trash'
                }

            # Delete emails in batches
            deleted_count = 0
            batch_size = 50

            for i in range(0, len(message_ids), batch_size):
                batch = message_ids[i:i + batch_size]

                for msg_id in batch:
                    try:
                        # Move to trash instead of permanent deletion (safer and works with gmail.modify scope)
                        self.service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={
                                'addLabelIds': ['TRASH'],
                                'removeLabelIds': ['INBOX', 'UNREAD']
                            }
                        ).execute()
                        deleted_count += 1
                    except HttpError as e:
                        print(f"   ⚠️ Failed to move message to trash: {e}")
                        continue

                print(f"   Deleted batch {i//batch_size + 1}: {len(batch)} emails")
                time.sleep(0.1)  # Rate limiting

            return {
                'domain': domain,
                'found_count': len(message_ids),
                'deleted_count': deleted_count,
                'success': deleted_count > 0
            }

        except HttpError as e:
            return {'domain': domain, 'error': str(e)}

    def unsubscribe_and_block_domain(self, domain: str, dry_run: bool = True) -> Dict[str, Any]:
        """Complete unsubscribe and block workflow for domain."""
        print(f"\n🎯 {'DRY RUN: ' if dry_run else ''}Processing {domain}")

        results = {
            'domain': domain,
            'steps': []
        }

        # Step 1: Find unsubscribe links
        print("   Step 1: Finding unsubscribe links...")
        unsubscribe_info = self.find_unsubscribe_links(domain, sample_size=3)

        if unsubscribe_info:
            print(f"   ✅ Found unsubscribe links in {len(unsubscribe_info)} emails")
            results['steps'].append({
                'step': 'find_unsubscribe',
                'success': True,
                'unsubscribe_links': unsubscribe_info[0]['unsubscribe_links'][:3]  # First 3 links
            })
        else:
            print("   ⚠️ No unsubscribe links found")
            results['steps'].append({
                'step': 'find_unsubscribe',
                'success': False,
                'message': 'No unsubscribe links found'
            })

        # Step 2: Create Gmail filter to auto-delete future emails
        print("   Step 2: Creating Gmail filter...")
        filter_result = self.create_delete_filter(domain, dry_run=dry_run)
        results['steps'].append({
            'step': 'create_filter',
            'success': filter_result.get('success', False),
            'result': filter_result
        })

        # Step 3: Delete existing emails
        print("   Step 3: Deleting existing emails...")
        delete_result = self.delete_existing_emails(domain, dry_run=dry_run)
        results['steps'].append({
            'step': 'delete_existing',
            'success': delete_result.get('success', False),
            'result': delete_result
        })

        return results

    def list_existing_filters(self) -> List[Dict[str, Any]]:
        """List existing Gmail filters."""
        try:
            filters = self.service.users().settings().filters().list(userId='me').execute()
            return filters.get('filter', [])
        except HttpError as e:
            print(f"❌ Failed to list filters: {e}")
            return []

    def delete_filter(self, filter_id: str) -> bool:
        """Delete a Gmail filter by ID."""
        try:
            self.service.users().settings().filters().delete(
                userId='me',
                id=filter_id
            ).execute()
            return True
        except HttpError as e:
            print(f"❌ Failed to delete filter: {e}")
            return False