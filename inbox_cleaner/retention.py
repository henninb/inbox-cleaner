# inbox_cleaner/retention.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.database import DatabaseManager
from googleapiclient.discovery import build

@dataclass
class RetentionRule:
    domain: Optional[str] = None
    sender: Optional[str] = None
    retention_days: int = 30
    subject_contains: Optional[List[str]] = None
    description: str = ""

    def __post_init__(self):
        if self.domain and self.sender:
            raise ValueError("A rule can have a 'domain' or a 'sender', but not both.")

class RetentionConfig:
    def __init__(self, config: Dict[str, Any], overrides: Dict[str, int] = None):
        self.rules: List[RetentionRule] = []
        raw_rules = config.get('retention_rules', [])
        for rule_data in raw_rules:
            rule = RetentionRule(**rule_data)

            # Apply override
            if overrides:
                key = rule.domain or rule.sender
                if key in overrides:
                    rule.retention_days = overrides[key]

            self.rules.append(rule)

    def get_rules(self) -> List[RetentionRule]:
        return self.rules

    @staticmethod
    def generate_gmail_query(rule: "RetentionRule") -> str:
        parts = []

        if rule.domain:
            parts.append(f"from:{rule.domain}")
        elif rule.sender:
            parts.append(f"from:{rule.sender}")

        if rule.subject_contains:
            subject_parts = [f'subject:"{term}"' for term in rule.subject_contains]
            parts.append(f"({' OR '.join(subject_parts)})")

        parts.append(f"older_than:{rule.retention_days}d")
        parts.append("-in:spam -in:trash")

        return " ".join(parts)


@dataclass
class RetentionAnalysis:
    """Holds the analysis result for a single retention rule."""
    rule: RetentionRule
    messages_found: int = 0
    messages: list = field(default_factory=list)

class GmailRetentionManager:
    def __init__(self, config: RetentionConfig, gmail_config: Dict[str, Any], service=None):
        self.config = config
        self.gmail_config = gmail_config
        self.service = service
        if not self.service:
            self._create_service()

    def _create_service(self):
        authenticator = GmailAuthenticator(self.gmail_config)
        credentials = authenticator.get_valid_credentials()
        self.service = build('gmail', 'v1', credentials=credentials)

    def analyze_retention(self) -> Dict[str, RetentionAnalysis]:
        analysis_results = {}
        for rule in self.config.get_rules():
            query = self.config.generate_gmail_query(rule)
            response = self.service.users().messages().list(userId='me', q=query).execute()
            messages = response.get('messages', [])

            # For now, let's use the domain or sender as the key.
            # This might need to be more robust later.
            key = rule.domain or rule.sender
            if key:
                analysis_results[key] = RetentionAnalysis(
                    rule=rule,
                    messages_found=len(messages),
                    messages=messages
                )
        return analysis_results

    def analyze_retained_emails(self) -> Dict[str, RetentionAnalysis]:
        """Analyze emails that are being RETAINED (not cleaned up) based on rules."""
        retained_results = {}
        for rule in self.config.get_rules():
            # Query for emails that are NEWER than retention days (kept emails)
            parts = []

            if rule.domain:
                parts.append(f"from:{rule.domain}")
            elif rule.sender:
                parts.append(f"from:{rule.sender}")

            if rule.subject_contains:
                subject_parts = [f'subject:"{term}"' for term in rule.subject_contains]
                parts.append(f"({' OR '.join(subject_parts)})")

            # Key difference: look for NEWER emails (retained ones)
            parts.append(f"newer_than:{rule.retention_days}d")
            parts.append("-in:spam -in:trash")

            query = " ".join(parts)
            response = self.service.users().messages().list(userId='me', q=query).execute()
            messages = response.get('messages', [])

            key = rule.domain or rule.sender
            if key:
                retained_results[key] = RetentionAnalysis(
                    rule=rule,
                    messages_found=len(messages),
                    messages=messages
                )
        return retained_results

    def cleanup_old_emails(self, analysis_results: Dict[str, RetentionAnalysis], dry_run: bool = False) -> Dict[str, int]:
        """
        Moves old emails to trash based on the analysis results.

        Args:
            analysis_results: The results from the analyze_retention method.
            dry_run: If True, no actual modifications will be made.

        Returns:
            A dictionary summarizing the number of emails cleaned up per rule.
        """
        cleanup_summary = {}
        all_message_ids = []

        for key, analysis in analysis_results.items():
            message_ids = [msg['id'] for msg in analysis.messages]
            if not message_ids:
                continue

            all_message_ids.extend(message_ids)
            cleanup_summary[key] = len(message_ids)

        if dry_run:
            print(f"[DRY RUN] Would have moved {len(all_message_ids)} emails to trash.")
            return cleanup_summary

        if not all_message_ids:
            return {}

        # Gmail API has a limit of 1000 IDs per batchModify request
        for i in range(0, len(all_message_ids), 1000):
            batch_ids = all_message_ids[i:i + 1000]
            self.service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch_ids,
                    'addLabelIds': ['TRASH']
                }
            ).execute()

        return cleanup_summary

    def _format_email_line(self, email_data: Dict[str, Any]) -> str:
        """Format a single email's key details for output."""
        # Handle both message metadata and simple dict formats
        if isinstance(email_data, dict):
            if 'id' in email_data:
                # This is from Gmail API response, need to fetch details
                message_id = email_data['id']
                try:
                    message = self.service.users().messages().get(userId='me', id=message_id).execute()
                    headers = message.get('payload', {}).get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                    date = next((h['value'] for h in headers if h['name'].lower() == 'date'), 'Unknown Date')
                except Exception:
                    subject = 'Unable to fetch subject'
                    sender = 'Unable to fetch sender'
                    date = 'Unknown Date'
            else:
                # This is already formatted data
                subject = email_data.get('subject', 'No Subject')
                sender = email_data.get('sender', 'Unknown Sender')
                date = email_data.get('date_received', 'Unknown Date')
        else:
            subject = 'Invalid email data'
            sender = 'Unknown'
            date = 'Unknown'

        # Truncate subject if too long
        if len(subject) > 100:
            subject = subject[:97] + '...'

        # Format date (take first 10 chars if it's ISO format)
        date_str = str(date)[:10] if date else 'Unknown'

        return f"{date_str} | {sender} | {subject}"

    def print_retained_emails(self, analysis_results: Dict[str, RetentionAnalysis]) -> None:
        """Print a detailed summary of retained (recent) emails by category."""
        if not analysis_results:
            print("No retention analysis results to display.")
            return

        total_retained = 0

        for key, analysis in analysis_results.items():
            rule = analysis.rule
            messages = analysis.messages
            message_count = len(messages)
            total_retained += message_count

            # Create category description
            if rule.domain:
                category_desc = f"Emails from {rule.domain} (retained under {rule.retention_days}-day policy)"
            elif rule.sender:
                category_desc = f"Emails from {rule.sender} (retained under {rule.retention_days}-day policy)"
            else:
                category_desc = f"Emails matching rule (retained under {rule.retention_days}-day policy)"

            if rule.description:
                category_desc = f"{rule.description} - {category_desc}"

            print(f"\n📥 {category_desc}:")
            print("-" * 80)

            if message_count == 0:
                print("(none)")
            else:
                # Show up to 10 most recent emails for each category
                display_count = min(10, message_count)
                for i, email in enumerate(messages[:display_count]):
                    print(f"  {i+1:2d}. {self._format_email_line(email)}")

                if message_count > 10:
                    print(f"     ... and {message_count - 10} more {key} emails")

            print(f"Total retained for {key}: {message_count} emails")

        print(f"\n🎯 SUMMARY: Total retained across all rules: {total_retained} emails")
        if total_retained > 0:
            print("💡 These emails meet retention criteria and will be preserved.")
            print("💡 Run analyze_retention() to see which emails would be cleaned up.")

    def sync_with_database(self, database_manager, verbose: bool = True) -> int:
        """
        Sync the local database with Gmail by removing emails that no longer exist.

        Args:
            database_manager: DatabaseManager instance to use for database operations
            verbose: Whether to print progress information

        Returns:
            Number of orphaned emails removed from database
        """
        if not database_manager:
            if verbose:
                print("❌ No database manager provided")
            return 0

        # Get all emails from database that might be affected by retention rules
        all_emails = []
        for rule in self.config.get_rules():
            if rule.domain:
                query_term = rule.domain
            elif rule.sender:
                query_term = rule.sender
            else:
                continue

            try:
                # Search for emails matching this rule in the database
                emails = database_manager.search_emails(query_term, per_page=100000)
                all_emails.extend(emails)
            except Exception as e:
                if verbose:
                    print(f"⚠️  Error searching database for {query_term}: {e}")
                continue

        if not all_emails:
            if verbose:
                print("✅ No emails found in database to check.")
            return 0

        if verbose:
            print(f"🔍 Checking {len(all_emails)} emails in database against Gmail...")

        orphaned_count = 0
        checked_count = 0

        for email in all_emails:
            msg_id = email.get('message_id', '')
            if not msg_id:
                continue

            try:
                # Try to get the message from Gmail
                self.service.users().messages().get(userId='me', id=msg_id).execute()
                # If we get here, the email still exists in Gmail
            except Exception as e:
                error_str = str(e).lower()
                if 'not found' in error_str or '404' in error_str:
                    # Email doesn't exist in Gmail anymore, remove from database
                    try:
                        database_manager.delete_email(msg_id)
                        orphaned_count += 1
                        if verbose and orphaned_count % 10 == 0:
                            print(f"   Cleaned up {orphaned_count} orphaned emails...")
                    except Exception as delete_error:
                        if verbose:
                            print(f"⚠️  Failed to delete email {msg_id} from database: {delete_error}")
                elif verbose:
                    print(f"⚠️  Error checking email {msg_id}: {e}")

            checked_count += 1

        if verbose:
            if orphaned_count > 0:
                print(f"🧹 Cleaned up {orphaned_count} orphaned emails from database.")
                print(f"📊 Checked {checked_count} total emails.")
                print("💡 Database is now in sync with Gmail.")
            else:
                print(f"✅ Database is already in sync with Gmail (checked {checked_count} emails).")

        return orphaned_count
