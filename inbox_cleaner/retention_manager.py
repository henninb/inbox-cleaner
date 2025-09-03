"""Retention management for selected senders and categories.

This module centralizes retention logic that was previously in the root-level
usps_retention_manager.py script and exposes a class usable from the CLI.

Retention policy:
- Keep messages newer than `retention_days`.
- Move older messages to Trash (Gmail auto-deletes after 30 days).

Categories covered:
- USPS: from:usps.com (Expected Delivery and others)
- Google security alerts: accounts.google.com, subject contains security alert terms
- Hulu marketing: from:hulumail.com
- Privacy.com support: from:support@privacy.com
- Spotify notifications: from:no-reply@spotify.com
- Acorns notifications: from:info@notifications.acorns.com
- Veterans Affairs: from:veteransaffairs@messages.va.gov
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import re
import yaml
from googleapiclient.discovery import build

from .auth import GmailAuthenticator, AuthenticationError
from .database import DatabaseManager


USPS_EXPECTED_PATTERNS = [
    r"USPS®.*Expected Delivery",
    r"Expected Delivery.*\d{4}.*Between",
    r"Expected Delivery.*arriving by.*[ap]m",
    r"\d{19}",
]


@dataclass
class CategoryResult:
    recent: List[Dict[str, Any]]
    old: List[Dict[str, Any]]


class RetentionManager:
    def __init__(self, retention_days: int = 30) -> None:
        self.retention_days = retention_days
        now_utc = datetime.now(timezone.utc)
        self.cutoff_date = now_utc - timedelta(days=retention_days)
        self.service = None
        self.db_path: str | None = None

    # ---------- Setup ----------
    def setup_services(self) -> None:
        config_path = Path("config.yaml")
        if not config_path.exists():
            raise RuntimeError("config.yaml not found")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        gmail_config = config["gmail"]
        self.db_path = config["database"]["path"]

        authenticator = GmailAuthenticator(gmail_config)
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            raise RuntimeError(f"Authentication failed: {e}")

        self.service = build("gmail", "v1", credentials=credentials)

    # ---------- Helpers ----------
    def _parse_dt(self, value: str | None) -> datetime:
        try:
            if not value:
                return datetime.min.replace(tzinfo=timezone.utc)
            s = value.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    def _split_recent_old(self, emails: List[Dict[str, Any]]) -> CategoryResult:
        recent: List[Dict[str, Any]] = []
        old: List[Dict[str, Any]] = []
        for e in emails:
            if self._parse_dt(e.get("date_received")) < self.cutoff_date:
                old.append(e)
            else:
                recent.append(e)
        return CategoryResult(recent=recent, old=old)

    def _is_usps_expected(self, email: Dict[str, Any]) -> bool:
        subject = email.get("subject", "")
        sender = (email.get("sender_email") or "").lower()
        sender_domain = (email.get("sender_domain") or "").lower()
        if "usps.com" not in sender and "usps.com" not in sender_domain:
            if "USPS®" not in subject and "usps" not in subject.lower():
                return False
        for pat in USPS_EXPECTED_PATTERNS:
            if re.search(pat, subject, re.IGNORECASE):
                return True
        return False

    # ---------- DB finders ----------
    def _db_find(self, query: str) -> List[Dict[str, Any]]:
        if not self.db_path:
            return []
        with DatabaseManager(self.db_path) as db:
            return db.search_emails(query, per_page=100000)

    def find_usps(self) -> List[Dict[str, Any]]:
        return self._db_find("usps.com")

    def find_security_alerts(self) -> List[Dict[str, Any]]:
        candidates = self._db_find("accounts.google.com")
        out: List[Dict[str, Any]] = []
        for e in candidates:
            subj = (e.get("subject") or "").lower()
            sender = (e.get("sender_email") or "").lower()
            domain = (e.get("sender_domain") or "").lower()
            if ("accounts.google.com" in domain or sender == "no-reply@accounts.google.com") and any(
                k in subj for k in ["security alert", "critical security alert", "new sign-in", "suspicious sign-in"]
            ):
                out.append(e)
        return out

    def find_hulu(self) -> List[Dict[str, Any]]:
        candidates = self._db_find("hulumail.com")
        return [e for e in candidates if "hulumail.com" in (e.get("sender_email") or "").lower() or "hulumail.com" in (e.get("sender_domain") or "").lower()]

    def find_privacy(self) -> List[Dict[str, Any]]:
        candidates = self._db_find("privacy.com")
        return [e for e in candidates if (e.get("sender_email") or "").lower() == "support@privacy.com"]

    def find_spotify(self) -> List[Dict[str, Any]]:
        candidates = self._db_find("spotify.com")
        return [e for e in candidates if (e.get("sender_email") or "").lower() == "no-reply@spotify.com"]

    def find_acorns(self) -> List[Dict[str, Any]]:
        candidates = self._db_find("acorns.com")
        return [e for e in candidates if (e.get("sender_email") or "").lower() == "info@notifications.acorns.com"]

    def find_va(self) -> List[Dict[str, Any]]:
        candidates = self._db_find("va.gov")
        return [e for e in candidates if (e.get("sender_email") or "").lower() == "veteransaffairs@messages.va.gov"]

    # ---------- Analysis ----------
    def analyze(self) -> Dict[str, CategoryResult]:
        usps = self.find_usps()
        security = self.find_security_alerts()
        hulu = self.find_hulu()
        privacy = self.find_privacy()
        spotify = self.find_spotify()
        acorns = self.find_acorns()
        va = self.find_va()

        results = {
            "usps": self._split_recent_old(usps),
            "security": self._split_recent_old(security),
            "hulu": self._split_recent_old(hulu),
            "privacy": self._split_recent_old(privacy),
            "spotify": self._split_recent_old(spotify),
            "acorns": self._split_recent_old(acorns),
            "va": self._split_recent_old(va),
        }
        return results

    # ---------- Cleanup (DB-based) ----------
    def cleanup_db(self, dry_run: bool = True) -> Tuple[int, Dict[str, CategoryResult]]:
        results = self.analyze()
        all_old = []
        for key in ["usps", "security", "hulu", "privacy", "spotify", "acorns", "va"]:
            all_old.extend(results[key].old)

        if dry_run:
            return len(all_old), results

        deleted = 0
        with DatabaseManager(self.db_path or "./inbox_cleaner.db") as db:
            for email in all_old:
                try:
                    self.service.users().messages().trash(userId="me", id=email["message_id"]).execute()
                    db.delete_email(email["message_id"])
                    deleted += 1
                except Exception:
                    continue
        return deleted, results

    # ---------- Cleanup (live Gmail search) ----------
    def cleanup_live(self, dry_run: bool = False, verbose: bool = True) -> Dict[str, int]:
        def collect(q: str) -> List[str]:
            ids: List[str] = []
            token = None
            while True:
                params = {"userId": "me", "q": q, "maxResults": 500}
                if token:
                    params["pageToken"] = token
                resp = self.service.users().messages().list(**params).execute()
                msgs = resp.get("messages", [])
                if not msgs:
                    break
                ids.extend(m["id"] for m in msgs)
                token = resp.get("nextPageToken")
                if not token:
                    break
            return ids

        d = self.retention_days
        queries = {
            "usps": ("🔎 Searching Gmail for old USPS emails...", f"from:usps.com older_than:{d}d -in:spam -in:trash"),
            "security": ("🔎 Searching Gmail for old Google security alerts...", f"(from:no-reply@accounts.google.com OR from:accounts.google.com) subject:(security alert) older_than:{d}d -in:spam -in:trash"),
            "hulu": ("🔎 Searching Gmail for old Hulu (hulumail.com) emails...", f"from:hulumail.com older_than:{d}d -in:spam -in:trash"),
            "privacy": ("🔎 Searching Gmail for old Privacy.com support emails...", f"from:support@privacy.com older_than:{d}d -in:spam -in:trash"),
            "spotify": ("🔎 Searching Gmail for old Spotify (no-reply@spotify.com) emails...", f"from:no-reply@spotify.com older_than:{d}d -in:spam -in:trash"),
            "acorns": ("🔎 Searching Gmail for old Acorns (info@notifications.acorns.com) emails...", f"from:info@notifications.acorns.com older_than:{d}d -in:spam -in:trash"),
            "va": ("🔎 Searching Gmail for old Veterans Affairs emails...", f"from:veteransaffairs@messages.va.gov older_than:{d}d -in:spam -in:trash"),
        }

        counts: Dict[str, int] = {}
        ids_all: List[str] = []
        
        for key, (message, q) in queries.items():
            if verbose:
                print(message)
            ids = collect(q)
            counts[key] = len(ids)
            ids_all.extend(ids)
            if verbose:
                print(f"   • {key.title()} old: {len(ids)}")

        if not ids_all:
            if verbose:
                print('✅ No old emails found via live search.')
            counts["total"] = 0
            return counts
            
        if dry_run:
            counts["total"] = len(ids_all)
            return counts

        if verbose:
            print(f"\n🗑️  Moving {len(ids_all)} messages to Trash (live search)...")
        moved = 0
        for i in range(0, len(ids_all), 500):
            batch = ids_all[i : i + 500]
            try:
                self.service.users().messages().batchModify(
                    userId="me",
                    body={"ids": batch, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX", "UNREAD"]},
                ).execute()
                moved += len(batch)
            except Exception as e:
                if verbose and ('insufficientPermissions' in str(e) or '403' in str(e)):
                    print('❌ Permission error: missing gmail.modify scope. Re-auth: python -m inbox_cleaner.cli auth --setup')
                    break
                elif verbose:
                    print(f"⚠️  Failed a batch: {e}")
                    
        if verbose:
            print(f"✅ Moved {moved} messages to Trash via live search.")
            print('ℹ️  These will be auto-deleted by Gmail after 30 days.')
        
        counts["total"] = moved
        return counts

    def _format_email_line(self, email: Dict[str, Any]) -> str:
        """Format a single email's key details for output."""
        date_str = (email.get('date_received') or '')[:10]
        sender = email.get('sender_email') or email.get('sender_domain') or 'unknown'
        subject = email.get('subject', '')
        subject = (subject[:97] + '...') if len(subject) > 100 else subject
        return f"{date_str} | {sender} | {subject}"

    def print_kept_summary(self) -> None:
        """Print a detailed summary of kept (recent) emails by category."""
        results = self.analyze()
        
        category_info = {
            "usps": "USPS emails (most recent under retention)",
            "security": "Google Security Alert emails (most recent under retention)", 
            "hulu": "Hulu emails (most recent under retention)",
            "privacy": "Privacy.com emails (most recent under retention)",
            "spotify": "Spotify emails (most recent under retention)",
            "acorns": "Acorns emails (most recent under retention)",
            "va": "Veterans Affairs emails (most recent under retention)"
        }
        
        total_kept = 0
        for key in ["usps", "security", "hulu", "privacy", "spotify", "acorns", "va"]:
            recent_emails = results[key].recent
            recent_count = len(recent_emails)
            total_kept += recent_count
            
            print(f"\n📥 Kept {category_info[key]}:")
            print("-" * 60)
            
            if recent_count == 0:
                print("(none)")
            else:
                # Show up to 10 most recent emails for each category
                for email in recent_emails[:10]:
                    print(self._format_email_line(email))
                
                if recent_count > 10:
                    print(f"... and {recent_count - 10} more {key} emails")
            
            print(f"Kept {key} total: {recent_count}")
        
        print(f"\n🎯 SUMMARY: Total kept across all categories: {total_kept} emails")
        print(f"💡 These emails are under {self.retention_days}-day retention and will be preserved.")
        if total_kept > 0:
            print(f"💡 Re-run --analyze to see detailed breakdown of kept vs old emails.")

    def cleanup_orphaned_emails(self, verbose: bool = True) -> int:
        """Remove emails from database that no longer exist in Gmail."""
        if not self.db_path:
            return 0
            
        results = self.analyze()
        orphaned_count = 0
        
        # Check all old emails to see if they still exist in Gmail
        all_old_emails = []
        for key in ["usps", "security", "hulu", "privacy", "spotify", "acorns", "va"]:
            all_old_emails.extend(results[key].old)
        
        if not all_old_emails:
            if verbose:
                print("✅ No old emails found in database to check.")
            return 0
            
        if verbose:
            print(f"🧹 Checking {len(all_old_emails)} old emails in database against Gmail...")
        
        with DatabaseManager(self.db_path) as db:
            for email in all_old_emails:
                msg_id = email.get('message_id', '')
                if not msg_id:
                    continue
                    
                try:
                    # Try to get the message from Gmail
                    self.service.users().messages().get(userId='me', id=msg_id).execute()
                except Exception as e:
                    if 'Not Found' in str(e) or '404' in str(e):
                        # Email doesn't exist in Gmail anymore, remove from database
                        try:
                            db.delete_email(msg_id)
                            orphaned_count += 1
                            if verbose and orphaned_count % 10 == 0:
                                print(f"   Cleaned up {orphaned_count} orphaned emails...")
                        except Exception:
                            pass
        
        if verbose:
            if orphaned_count > 0:
                print(f"🧹 Cleaned up {orphaned_count} orphaned emails from database.")
                print("💡 Database is now in sync with Gmail.")
            else:
                print("✅ Database is already in sync with Gmail.")
        
        return orphaned_count
