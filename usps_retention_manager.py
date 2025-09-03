#!/usr/bin/env python3
"""
USPS Email Retention Manager

This script automatically manages USPS emails retention:
- Keeps only the last 30 days of ALL USPS emails
- Moves older USPS emails to Trash (Gmail auto-deletes after 30 days)
- Can run daily as a scheduled task

Usage:
  python usps_retention_manager.py --analyze    # Show what would be deleted
  python usps_retention_manager.py --cleanup    # Actually delete old USPS emails
  python usps_retention_manager.py --schedule   # Set up daily automation
"""

import yaml
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.database import DatabaseManager

class USPSRetentionManager:
    def __init__(self, retention_days=30):
        self.retention_days = retention_days
        # Use timezone-aware UTC to compare with stored ISO timestamps
        now_utc = datetime.now(timezone.utc)
        self.cutoff_date = now_utc - timedelta(days=retention_days)
        self.service = None
        self.db_path = None
        self.security_old = []
        self.security_recent = []

        # USPS Expected Delivery patterns (based on your actual emails)
        self.expected_delivery_patterns = [
            r"USPS®.*Expected Delivery",  # Matches your exact format
            r"Expected Delivery.*\d{4}.*Between",  # Year and Between pattern
            r"Expected Delivery.*arriving by.*[ap]m",  # arriving by pattern
            r"\d{19}",  # 19-digit tracking numbers from your emails
        ]

    def setup_services(self):
        """Initialize Gmail API and database using the same pattern as CLI."""
        config_path = Path("config.yaml")
        if not config_path.exists():
            raise Exception("config.yaml not found")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        self.db_path = config['database']['path']

        # Use the exact same authentication pattern as the working CLI
        authenticator = GmailAuthenticator(gmail_config)

        print("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except Exception as e:
            raise Exception(f"Authentication failed: {e}")

        # Build Gmail service with proper scopes
        self.service = build('gmail', 'v1', credentials=credentials)

        print("✅ Gmail service and database ready")

    def _parse_email_datetime(self, value):
        """Parse an ISO timestamp into a timezone-aware UTC datetime.

        Falls back to a very old UTC datetime if parsing fails.
        Accepts values with 'Z', with explicit offsets, or naive; naive is treated as UTC.
        """
        try:
            if not value:
                return datetime.min.replace(tzinfo=timezone.utc)
            s = str(value).strip()
            # Normalize common UTC suffix
            s = s.replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    def is_expected_delivery_email(self, email_data):
        """Check if email is a USPS Expected Delivery notification."""
        subject = email_data.get('subject', '')
        sender = email_data.get('sender_email', '')
        sender_domain = email_data.get('sender_domain', '')

        # Must be from USPS (check both sender fields)
        is_usps = ('usps.com' in sender.lower() if sender else False) or \
                  ('usps.com' in sender_domain.lower() if sender_domain else False)

        if not is_usps:
            # As backup, check if subject contains USPS patterns
            is_usps = 'USPS®' in subject or 'usps' in subject.lower()

        if not is_usps:
            return False

        # Check if subject matches Expected Delivery patterns
        for pattern in self.expected_delivery_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                return True

        return False

    def find_usps_emails(self):
        """Find all USPS emails in database."""
        with DatabaseManager(self.db_path) as db:
            # Search for USPS emails
            usps_emails = db.search_emails("usps.com")

            # Separate Expected Delivery from other USPS emails
            expected_delivery_emails = []
            other_usps_emails = []

            for email in usps_emails:
                if self.is_expected_delivery_email(email):
                    expected_delivery_emails.append(email)
                else:
                    other_usps_emails.append(email)

            return expected_delivery_emails, other_usps_emails

    def is_google_security_alert(self, email_data) -> bool:
        """Detect Google Account security alert emails to prune after 30 days."""
        subject = (email_data.get('subject') or '').lower()
        sender = (email_data.get('sender_email') or '').lower()
        sender_domain = (email_data.get('sender_domain') or '').lower()

        from_google_accounts = (
            'accounts.google.com' in sender_domain or
            'no-reply@accounts.google.com' in sender
        )
        security_keywords = [
            'security alert',
            'critical security alert',
            'new sign-in',
            'suspicious sign-in',
        ]
        has_security_subject = any(k in subject for k in security_keywords)
        return from_google_accounts and has_security_subject

    def find_google_security_emails(self):
        """Find Google security alert emails in database."""
        with DatabaseManager(self.db_path) as db:
            candidates = db.search_emails("accounts.google.com")
            return [e for e in candidates if self.is_google_security_alert(e)]

    def analyze_retention(self):
        """Analyze which USPS emails are older than retention and should be deleted.

        Policy: Keep ALL USPS emails newer than retention_days; delete ALL USPS
        emails older than retention_days (not just Expected Delivery).
        """
        print(f"🔍 Analyzing retained email types for {self.retention_days}-day retention...")

        expected_delivery, other_usps = self.find_usps_emails()
        all_usps = expected_delivery + other_usps

        # Google security alerts
        security_alerts = self.find_google_security_emails()

        old_usps = []
        recent_usps = []
        old_security = []
        recent_security = []

        for email in all_usps:
            # Parse ISO date; tolerate naive timestamps and missing 'Z'
            email_dt = self._parse_email_datetime(email.get('date_received'))

            if email_dt < self.cutoff_date:
                old_usps.append(email)
            else:
                recent_usps.append(email)

        # Classify security alerts
        for email in security_alerts:
            email_dt = self._parse_email_datetime(email.get('date_received'))
            if email_dt < self.cutoff_date:
                old_security.append(email)
            else:
                recent_security.append(email)

        # Save for later use in cleanup and printing
        self.security_old = old_security
        self.security_recent = recent_security

        print(f"\n📊 Retention Analysis:")
        print("=" * 40)
        print(f"📧 Total USPS emails found: {len(all_usps)}")
        print(f"📦 Expected Delivery emails: {len(expected_delivery)}")
        print(f"📮 Other USPS emails: {len(other_usps)}")
        print(f"   • Recent (keep): {len(recent_usps)}")
        print(f"   • Old (delete): {len(old_usps)}")
        print()
        print(f"🔐 Google Security Alerts: {len(security_alerts)}")
        print(f"   • Recent (keep): {len(recent_security)}")
        print(f"   • Old (delete): {len(old_security)}")

        if old_usps:
            print(f"\n🗑️  OLD USPS Emails (would delete):")
            for i, email in enumerate(old_usps[:5], 1):  # Show first 5
                email_date = (email.get('date_received') or '')[:10]
                subject = email.get('subject', '')
                subject = subject[:50] + "..." if len(subject) > 50 else subject
                print(f"   {i}. {email_date}: {subject}")

            if len(old_usps) > 5:
                print(f"   ... and {len(old_usps) - 5} more")

        if old_security:
            print(f"\n🗑️  OLD Google Security Alerts (would delete):")
            for i, email in enumerate(old_security[:5], 1):
                email_date = (email.get('date_received') or '')[:10]
                subject = email.get('subject', '')
                subject = subject[:50] + "..." if len(subject) > 50 else subject
                print(f"   {i}. {email_date}: {subject}")

            if len(old_security) > 5:
                print(f"   ... and {len(old_security) - 5} more")

        return old_usps, recent_usps, expected_delivery, other_usps

    def cleanup_old_expected_delivery(self, dry_run=True):
        """Backward-compatible wrapper. Deletes old USPS emails (all types)."""
        return self.cleanup_old_usps_emails(dry_run=dry_run)

    def cleanup_old_usps_emails(self, dry_run=True):
        """Delete old USPS emails (older than retention cutoff), keep recent ones."""
        old_emails, recent_emails, expected_delivery, other_emails = self.analyze_retention()
        # Combine with security alerts for deletion
        all_old = list(old_emails) + list(self.security_old)

        if not all_old:
            print("✅ No old USPS emails to clean up!")
            return 0, recent_emails + self.security_recent

        if dry_run:
            print(f"\n💡 DRY RUN: Would delete {len(all_old)} old emails (USPS + Security Alerts)")
            return len(all_old), recent_emails + self.security_recent

        print(f"\n🗑️  MOVING {len(all_old)} old emails to trash (USPS + Security Alerts)...")
        print(f"   (Gmail automatically deletes trashed emails after 30 days)")

        deleted_count = 0
        with DatabaseManager(self.db_path) as db:
            for email in all_old:
                message_id = email['message_id']

                try:
                    # Move to trash (Gmail API allows this with gmail.modify scope)
                    # Note: Emails in trash are automatically permanently deleted after 30 days
                    self.service.users().messages().trash(
                        userId='me',
                        id=message_id
                    ).execute()

                    # Delete from database
                    db.delete_email(message_id)
                    deleted_count += 1

                    if deleted_count % 10 == 0:
                        print(f"   Moved to trash {deleted_count}/{len(all_old)}...")

                except Exception as e:
                    # Better error handling
                    error_msg = str(e)
                    if "insufficientPermissions" in error_msg:
                        print(f"❌ AUTHENTICATION ERROR: Insufficient permissions to move emails to trash")
                        print(f"   This usually means you need to re-authenticate with proper scopes.")
                        print(f"   Run: python -m inbox_cleaner.cli auth --setup")
                        break
                    else:
                        print(f"⚠️  Failed to move to trash {message_id}: {e}")

        if deleted_count == 0 and all_old:
            print(f"\n❌ FAILED TO MOVE ANY EMAILS TO TRASH")
            print(f"   This is likely an authentication scope issue.")
            print(f"   Try running: python -m inbox_cleaner.cli auth --setup")
            print(f"   Then re-run this script.")

        print(f"✅ Successfully moved {deleted_count} old emails to trash")
        print(f"📦 Kept {len(recent_emails)} recent USPS emails (< {self.retention_days} days)")
        print(f"📮 Of which Expected Delivery: {len([e for e in recent_emails if self.is_expected_delivery_email(e)])}")
        print(f"📮 Of which Other USPS: {len([e for e in recent_emails if not self.is_expected_delivery_email(e)])}")
        print(f"🔐 Kept {len(self.security_recent)} recent Google security alerts (< {self.retention_days} days)")

        return deleted_count, recent_emails + self.security_recent

    def create_usps_filter(self):
        """Create a Gmail filter to label USPS Expected Delivery emails."""
        print("🏷️  Creating USPS Expected Delivery filter...")

        try:
            filter_body = {
                'criteria': {
                    'from': 'auto-reply@usps.com',
                    'query': 'subject:"Expected Delivery"'
                },
                'action': {
                    'addLabelIds': ['STARRED'],  # Star for easy identification
                    'removeLabelIds': ['INBOX']  # Archive automatically
                }
            }

            result = self.service.users().settings().filters().create(
                userId='me',
                body=filter_body
            ).execute()

            filter_id = result.get('id', 'Unknown')[:8]
            print(f"✅ Created USPS filter (ID: {filter_id})")
            print("   • Stars Expected Delivery emails")
            print("   • Archives them automatically")

        except Exception as e:
            print(f"❌ Failed to create filter: {e}")

    def setup_daily_cleanup(self):
        """Generate instructions for daily automated cleanup."""
        print("⏰ Setting up daily automated cleanup...")

        # Create a simple cron-compatible script
        script_content = f'''#!/bin/bash
# Daily USPS Expected Delivery cleanup
cd {Path.cwd()}
/usr/bin/python3 usps_retention_manager.py --cleanup
'''

        with open('daily_usps_cleanup.sh', 'w') as f:
            f.write(script_content)

        # Make it executable
        import os
        os.chmod('daily_usps_cleanup.sh', 0o755)

        print("✅ Created daily cleanup script: daily_usps_cleanup.sh")
        print("\n📅 To set up daily automation:")
        print("1. Run: crontab -e")
        print("2. Add this line for daily cleanup at 2 AM:")
        print(f"   0 2 * * * {Path.cwd()}/daily_usps_cleanup.sh")
        print("\n💡 Or run manually whenever you want:")
        print("   python usps_retention_manager.py --cleanup")

def force_reauth():
    """Force re-authentication to ensure proper scopes."""
    print("🔄 Forcing re-authentication to refresh scopes...")

    config_path = Path("config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    gmail_config = config['gmail']
    authenticator = GmailAuthenticator(gmail_config)

    try:
        # This will force a new authentication flow
        credentials = authenticator.authenticate()
        print("✅ Re-authentication complete!")
        return True
    except Exception as e:
        print(f"❌ Re-authentication failed: {e}")
        return False

def _format_email_line(email: dict) -> str:
    """Format a single email's key details for output."""
    date_str = (email.get('date_received') or '')[:10]
    sender = email.get('sender_email') or email.get('sender_domain') or 'unknown@usps.com'
    subject = email.get('subject', '')
    subject = (subject[:97] + '...') if len(subject) > 100 else subject
    return f"{date_str} | {sender} | {subject}"

def print_kept_emails(title: str, emails: list) -> None:
    """Print details of emails being kept to stdout."""
    print("\n📥 Kept USPS emails (most recent under retention):")
    print("-" * 60)
    if not emails:
        print("(none)")
        return
    for e in emails:
        print(_format_email_line(e))
    print(f"\nTotal kept: {len(emails)}")

def main():
    import sys

    if len(sys.argv) < 2:
        print("📦 USPS Email Retention Manager")
        print("=" * 35)
        print("Automatically manages USPS emails retention")
        print("Keeps only last 30 days of all USPS emails")
        print()
        print("Usage:")
        print("  --analyze   Show what would be deleted")
        print("  --cleanup   Actually delete old emails (DB-based)")
        print("  --dry-run   Same as --analyze")
        print("  --filter    Create Gmail filter for USPS emails")
        print("  --schedule  Set up daily automation")
        return

    command = sys.argv[1]
    manager = USPSRetentionManager(retention_days=30)

    try:
        manager.setup_services()

        if command in ['--analyze', '--dry-run']:
            old_emails, recent_emails, expected_delivery, other_emails = manager.analyze_retention()
            print_kept_emails('Kept USPS emails', recent_emails)
            print_kept_emails('Kept Google security alerts', manager.security_recent)
            print(f"\n💡 To actually delete old emails:")
            print(f"   python {sys.argv[0]} --cleanup")

        elif command == '--cleanup':
            deleted, recent_emails = manager.cleanup_old_expected_delivery(dry_run=False)
            print_kept_emails('Kept emails', recent_emails)
            if deleted > 0:
                print(f"\n🎉 Cleanup complete! Freed up space from {deleted} old emails")

        elif command == '--cleanup-live':
            # Live Gmail-based cleanup using search queries (does not require full DB sync)
            def gmail_collect_ids(q, service, max_per_page=500):
                user_id = 'me'
                token = None
                collected = []
                while True:
                    params = {'userId': user_id, 'q': q, 'maxResults': min(500, max_per_page)}
                    if token:
                        params['pageToken'] = token
                    resp = service.users().messages().list(**params).execute()
                    msgs = resp.get('messages', [])
                    if not msgs:
                        break
                    collected.extend(m['id'] for m in msgs)
                    token = resp.get('nextPageToken')
                    if not token:
                        break
                return collected

            manager.setup_services()
            svc = manager.service
            days = manager.retention_days
            q_usps_old = f"from:usps.com older_than:{days}d -in:spam -in:trash"
            q_sec_old = f"(from:no-reply@accounts.google.com OR from:accounts.google.com) subject:(security alert) older_than:{days}d -in:spam -in:trash"
            q_hulu_old = f"from:hulumail.com older_than:{days}d -in:spam -in:trash"
            q_priv_old = f"from:support@privacy.com older_than:{days}d -in:spam -in:trash"
            q_spotify_old = f"from:no-reply@spotify.com older_than:{days}d -in:spam -in:trash"
            print('🔎 Searching Gmail for old USPS emails...')
            usps_ids = gmail_collect_ids(q_usps_old, svc)
            print(f"   • USPS old: {len(usps_ids)}")
            print('🔎 Searching Gmail for old Google security alerts...')
            sec_ids = gmail_collect_ids(q_sec_old, svc)
            print(f"   • Security alerts old: {len(sec_ids)}")
            print('🔎 Searching Gmail for old Hulu (hulumail.com) emails...')
            hulu_ids = gmail_collect_ids(q_hulu_old, svc)
            print(f"   • Hulu old: {len(hulu_ids)}")
            print('🔎 Searching Gmail for old Privacy.com support emails...')
            privacy_ids = gmail_collect_ids(q_priv_old, svc)
            print(f"   • Privacy.com old: {len(privacy_ids)}")
            print('🔎 Searching Gmail for old Spotify (no-reply@spotify.com) emails...')
            spotify_ids = gmail_collect_ids(q_spotify_old, svc)
            print(f"   • Spotify old: {len(spotify_ids)}")
            all_ids = usps_ids + sec_ids + hulu_ids + privacy_ids + spotify_ids
            if not all_ids:
                print('✅ No old emails found via live search.')
            else:
                print(f"\n🗑️  Moving {len(all_ids)} messages to Trash (live search)...")
                moved = 0
                for i in range(0, len(all_ids), 500):
                    batch = all_ids[i:i+500]
                    try:
                        svc.users().messages().batchModify(userId='me', body={'ids': batch, 'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX', 'UNREAD']}).execute()
                        moved += len(batch)
                    except Exception as e:
                        if 'insufficientPermissions' in str(e) or '403' in str(e):
                            print('❌ Permission error: missing gmail.modify scope. Re-auth: python -m inbox_cleaner.cli auth --setup')
                            break
                        print(f"⚠️  Failed a batch: {e}")
                print(f"✅ Moved {moved} messages to Trash via live search.")
                print('ℹ️  These will be auto-deleted by Gmail after 30 days.')
                print('💡 Re-run --analyze to confirm no old USPS/Security/Hulu/Privacy/Spotify emails remain.')

        elif command == '--filter':
            manager.create_usps_filter()

        elif command == '--schedule':
            manager.setup_daily_cleanup()

        else:
            print(f"❌ Unknown command: {command}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
