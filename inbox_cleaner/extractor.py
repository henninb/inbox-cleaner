"""Gmail data extraction module."""

import base64
import hashlib
import re
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from googleapiclient.errors import HttpError

# Constants for improved maintainability
IMPORTANT_LABELS = {'IMPORTANT', 'STARRED', 'PRIORITY'}
PERSONAL_LABELS = {'CATEGORY_PERSONAL'}
WORK_KEYWORDS = ['meeting', 'urgent', 'action required', 'deadline']
LOW_PRIORITY_LABELS = ['CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL']


class ExtractionError(Exception):
    """Custom exception for data extraction failures."""
    pass


@dataclass
class EmailMetadata:
    """Data class for email metadata storage."""
    message_id: str
    thread_id: str
    sender_email: str
    sender_domain: str
    sender_hash: str
    subject: str
    date_received: datetime
    labels: List[str]
    snippet: str
    content: str = ""
    estimated_importance: float = 0.0
    category: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['date_received'] = self.date_received.isoformat()
        return data


class GmailExtractor:
    """Extracts metadata and content from Gmail messages."""
    
    def __init__(self, service: Any, batch_size: int = 1000) -> None:
        """Initialize extractor with Gmail API service."""
        if service is None:
            raise ValueError("Gmail service is required")
        
        self.service = service
        self.batch_size = batch_size
    
    def get_message_list(self, query: str = "", page_token: Optional[str] = None) -> Dict[str, Any]:
        """Get list of message IDs matching query."""
        try:
            request = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=self.batch_size,
                pageToken=page_token
            )
            return request.execute()
        except HttpError as e:
            if "Gmail API has not been used" in str(e) or "disabled" in str(e):
                raise ExtractionError(
                    f"Gmail API not enabled. Please:\n"
                    f"1. Go to https://console.cloud.google.com/\n"
                    f"2. Navigate to APIs & Services → Library\n"
                    f"3. Search 'Gmail API' and click ENABLE\n"
                    f"4. Wait 2-3 minutes and try again\n"
                    f"Original error: {e}"
                )
            elif e.resp.status == 403:
                raise ExtractionError(
                    f"Gmail API access denied. Check:\n"
                    f"• Gmail API is enabled in Google Cloud Console\n"
                    f"• Your email is added as test user in OAuth consent screen\n"
                    f"• You granted proper permissions during authentication\n"
                    f"Original error: {e}"
                )
            else:
                raise ExtractionError(f"Gmail API error: {e}")
        except Exception as e:
            raise ExtractionError(f"Unexpected error accessing Gmail: {e}")
    
    def get_message_detail(self, message_id: str) -> Dict[str, Any]:
        """Get detailed message information."""
        try:
            request = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            )
            return request.execute()
        except HttpError as e:
            raise ExtractionError(f"Failed to retrieve message detail: {e}")
        except Exception as e:
            raise ExtractionError(f"Unexpected error retrieving message detail: {e}")
    
    def extract_email_metadata(self, message: Dict[str, Any]) -> EmailMetadata:
        """Extract metadata from Gmail message."""
        try:
            # Extract basic info
            message_id = message.get('id', '')
            thread_id = message.get('threadId', '')
            labels = message.get('labelIds', [])
            snippet = message.get('snippet', '')
            
            # Extract timestamp
            internal_date = message.get('internalDate', '0')
            date_received = datetime.fromtimestamp(int(internal_date) / 1000)
            
            # Extract headers
            headers = {}
            payload = message.get('payload', {})
            for header in payload.get('headers', []):
                headers[header['name'].lower()] = header['value']
            
            # Extract sender info
            sender_email = headers.get('from', '')
            sender_domain = self._extract_domain(sender_email)
            sender_hash = self._hash_sender_email(sender_email)
            
            # Extract subject
            subject = headers.get('subject', '')
            
            # Extract content
            content = self.extract_content(payload)
            
            return EmailMetadata(
                message_id=message_id,
                thread_id=thread_id,
                sender_email=sender_email,
                sender_domain=sender_domain,
                sender_hash=sender_hash,
                subject=subject,
                date_received=date_received,
                labels=labels,
                snippet=snippet,
                content=content,
                estimated_importance=self._estimate_importance(headers, content, labels)
            )
            
        except Exception as e:
            raise ExtractionError(f"Failed to extract email metadata: {e}")
    
    def extract_content(self, payload: Dict[str, Any]) -> str:
        """Extract text content from message payload."""
        content_parts = []
        
        # Check if payload has direct body content
        if 'body' in payload and 'data' in payload['body']:
            decoded_content = self._decode_base64(payload['body']['data'])
            if decoded_content:
                content_parts.append(decoded_content)
        
        # Check for multipart content
        if 'parts' in payload:
            for part in payload['parts']:
                part_content = self._extract_part_content(part)
                if part_content:
                    content_parts.append(part_content)
        
        return '\n'.join(content_parts)
    
    def _extract_part_content(self, part: Dict[str, Any]) -> str:
        """Extract content from a message part."""
        mime_type = part.get('mimeType', '')
        
        # Prefer plain text over HTML
        if mime_type == 'text/plain':
            body = part.get('body', {})
            if 'data' in body:
                return self._decode_base64(body['data'])
        
        # Fall back to HTML content
        elif mime_type == 'text/html':
            body = part.get('body', {})
            if 'data' in body:
                html_content = self._decode_base64(body['data'])
                # Simple HTML to text conversion (remove tags)
                return re.sub(r'<[^>]+>', '', html_content)
        
        # Handle nested multipart
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
            # Gmail uses URL-safe base64 encoding
            decoded_bytes = base64.urlsafe_b64decode(data)
            return decoded_bytes.decode('utf-8', errors='ignore')
        except Exception:
            return ""
    
    def extract_batch(self, message_ids: List[str]) -> List[EmailMetadata]:
        """Extract metadata for a batch of messages."""
        results = []
        
        for message_id in message_ids:
            try:
                message_detail = self.get_message_detail(message_id)
                metadata = self.extract_email_metadata(message_detail)
                results.append(metadata)
            except ExtractionError:
                # Skip failed messages but continue processing
                continue
        
        return results
    
    def extract_all(self, query: str = "", max_results: Optional[int] = None, 
                   progress_callback: Optional[Callable[[int, int], None]] = None) -> List[EmailMetadata]:
        """Extract all messages matching query."""
        all_results = []
        page_token = None
        processed_count = 0
        total_for_progress = None
        
        while True:
            # Get message list
            try:
                message_list = self.get_message_list(query, page_token)
            except ExtractionError:
                break
            
            messages = message_list.get('messages', [])
            if not messages:
                break
            
            # Set total for progress tracking (only on first iteration)
            if total_for_progress is None:
                if max_results:
                    # Use max_results as total when specified
                    total_for_progress = max_results
                else:
                    # Use Gmail's estimate when extracting all
                    total_for_progress = message_list.get('resultSizeEstimate', len(messages))
            
            # Extract message IDs for batch processing
            message_ids = [msg['id'] for msg in messages]
            
            # Apply max_results limit
            if max_results and processed_count + len(message_ids) > max_results:
                message_ids = message_ids[:max_results - processed_count]
            
            # Extract batch
            batch_results = self.extract_batch(message_ids)
            all_results.extend(batch_results)
            processed_count += len(message_ids)
            
            # Call progress callback
            if progress_callback:
                progress_callback(processed_count, total_for_progress)
            
            # Check if we've reached max_results
            if max_results and processed_count >= max_results:
                break
            
            # Get next page token
            page_token = message_list.get('nextPageToken')
            if not page_token:
                break
        
        return all_results
    
    def _hash_sender_email(self, email: str) -> str:
        """Hash email address for privacy."""
        if not email:
            return ""
        
        # Use SHA-256 for consistent hashing
        return hashlib.sha256(email.encode('utf-8')).hexdigest()
    
    def _extract_domain(self, email: str) -> str:
        """Extract domain from email address."""
        if not email or '@' not in email:
            return ""
        
        # Handle email addresses with names like "John Doe <john@example.com>"
        email_match = re.search(r'<([^>]+)>', email)
        if email_match:
            email = email_match.group(1)
        
        return email.split('@')[-1].strip()
    
    def _estimate_importance(self, headers: Dict[str, str], content: str, labels: List[str]) -> float:
        """Estimate email importance based on various factors."""
        importance = 0.0
        
        # Check for important labels
        if any(label in IMPORTANT_LABELS for label in labels):
            importance += 0.5
        
        # Check for personal indicators
        if 'INBOX' in labels and any(label in PERSONAL_LABELS for label in labels):
            importance += 0.3
        
        # Check for work-related indicators
        if any(keyword in headers.get('subject', '').lower() for keyword in WORK_KEYWORDS):
            importance += 0.2
        
        # Penalize promotional/social emails
        if any(label in LOW_PRIORITY_LABELS for label in labels):
            importance -= 0.3
        
        # Ensure importance is between 0 and 1
        return max(0.0, min(1.0, importance))