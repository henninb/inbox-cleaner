"""Email deletion functionality for Gmail and local database."""

import sqlite3
from typing import List, Dict, Any, Optional, Union
from .database import DatabaseManager


class EmailDeletionError(Exception):
    """Custom exception for email deletion failures."""
    pass


class EmailDeletionManager:
    """Manages deletion of emails from Gmail and local database."""

    def __init__(self, gmail_service = None, db_path: str = None):
        """Initialize deletion manager."""
        self.gmail_service = gmail_service
        self.db_path = db_path

    def delete_from_gmail(self, message_id: str) -> bool:
        """Delete a single email from Gmail."""
        if not self.gmail_service:
            return False
            
        try:
            self.gmail_service.users().messages().delete(
                userId='me',
                id=message_id
            ).execute()
            return True
        except Exception:
            return False

    def delete_from_database(self, message_id: str) -> bool:
        """Delete a single email from local database."""
        if not self.db_path:
            return False
            
        try:
            with DatabaseManager(self.db_path) as db:
                return db.delete_email(message_id)
        except Exception:
            return False

    def delete_email_completely(self, message_id: str) -> Dict[str, bool]:
        """Delete email from both Gmail and database."""
        results = {
            "gmail_deleted": False,
            "database_deleted": False
        }
        
        # Delete from Gmail first
        if self.gmail_service:
            results["gmail_deleted"] = self.delete_from_gmail(message_id)
        
        # Delete from database
        if self.db_path:
            results["database_deleted"] = self.delete_from_database(message_id)
        
        return results

    def get_emails_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all emails from a specific domain."""
        if not self.db_path:
            return []
            
        try:
            with DatabaseManager(self.db_path) as db:
                return db.get_emails_by_domain(domain)
        except Exception:
            return []

    def delete_emails_by_domain(self, domain: str, dry_run: bool = True) -> Dict[str, Any]:
        """Delete all emails from a specific domain."""
        results = {
            "domain": domain,
            "total_found": 0,
            "gmail_deleted": 0,
            "database_deleted": 0,
            "failed": [],
            "dry_run": dry_run
        }
        
        # Get emails from domain
        emails = self.get_emails_by_domain(domain)
        results["total_found"] = len(emails)
        
        if dry_run:
            # In dry run mode, just return what would be deleted
            results["would_delete"] = [
                {
                    "message_id": email["message_id"],
                    "subject": email.get("subject", ""),
                    "date_received": email.get("date_received", "")
                }
                for email in emails
            ]
            return results
        
        # Actually delete emails
        for email in emails:
            message_id = email["message_id"]
            
            try:
                deletion_result = self.delete_email_completely(message_id)
                
                if deletion_result["gmail_deleted"]:
                    results["gmail_deleted"] += 1
                    
                if deletion_result["database_deleted"]:
                    results["database_deleted"] += 1
                
                # If neither succeeded, add to failed list
                if not deletion_result["gmail_deleted"] and not deletion_result["database_deleted"]:
                    results["failed"].append({
                        "message_id": message_id,
                        "error": "Failed to delete from both Gmail and database"
                    })
                    
            except Exception as e:
                results["failed"].append({
                    "message_id": message_id,
                    "error": str(e)
                })
        
        return results

    def delete_emails_by_rule(self, rule: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        """Delete emails that match a spam rule."""
        results = {
            "rule_id": rule.get("rule_id"),
            "rule_type": rule.get("type"),
            "total_found": 0,
            "gmail_deleted": 0,
            "database_deleted": 0,
            "failed": [],
            "dry_run": dry_run
        }
        
        # Get matching emails based on rule type
        matching_emails = []
        
        if rule["type"] == "domain":
            matching_emails = self.get_emails_by_domain(rule["domain"])
            
        elif rule["type"] == "subject" or rule["type"] == "sender":
            # For pattern-based rules, we need to query all emails and filter
            matching_emails = self._get_emails_matching_pattern(rule)
        
        results["total_found"] = len(matching_emails)
        
        if dry_run:
            results["would_delete"] = [
                {
                    "message_id": email["message_id"],
                    "sender_domain": email.get("sender_domain", ""),
                    "subject": email.get("subject", ""),
                    "date_received": email.get("date_received", "")
                }
                for email in matching_emails
            ]
            return results
        
        # Actually delete emails
        for email in matching_emails:
            message_id = email["message_id"]
            
            try:
                deletion_result = self.delete_email_completely(message_id)
                
                if deletion_result["gmail_deleted"]:
                    results["gmail_deleted"] += 1
                    
                if deletion_result["database_deleted"]:
                    results["database_deleted"] += 1
                    
            except Exception as e:
                results["failed"].append({
                    "message_id": message_id,
                    "error": str(e)
                })
        
        return results

    def _get_emails_matching_pattern(self, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get emails matching a pattern-based rule."""
        if not self.db_path:
            return []
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            if rule["type"] == "subject":
                # For subject patterns, we need to use LIKE for basic matching
                # Note: SQLite doesn't have full regex support, so this is simplified
                cursor = conn.execute("""
                    SELECT message_id, sender_domain, subject, date_received
                    FROM emails_metadata
                    WHERE subject LIKE ?
                """, (f"%{rule['pattern']}%",))
                
            elif rule["type"] == "sender":
                cursor = conn.execute("""
                    SELECT message_id, sender_domain, subject, date_received
                    FROM emails_metadata  
                    WHERE sender_domain LIKE ?
                """, (f"%{rule['pattern']}%",))
            
            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
            
            conn.close()
            return results
            
        except Exception:
            return []

    def get_deletion_preview(self, rule_or_domain: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Get a preview of what would be deleted without actually deleting."""
        if isinstance(rule_or_domain, str):
            # It's a domain
            return self.delete_emails_by_domain(rule_or_domain, dry_run=True)
        else:
            # It's a rule
            return self.delete_emails_by_rule(rule_or_domain, dry_run=True)

    def bulk_delete_by_domains(self, domains: List[str], dry_run: bool = True) -> Dict[str, Any]:
        """Delete emails from multiple domains."""
        results = {
            "domains": domains,
            "total_domains": len(domains),
            "total_found": 0,
            "gmail_deleted": 0,
            "database_deleted": 0,
            "failed": [],
            "dry_run": dry_run,
            "domain_results": {}
        }
        
        for domain in domains:
            domain_result = self.delete_emails_by_domain(domain, dry_run=dry_run)
            results["domain_results"][domain] = domain_result
            
            results["total_found"] += domain_result["total_found"]
            results["gmail_deleted"] += domain_result.get("gmail_deleted", 0)
            results["database_deleted"] += domain_result.get("database_deleted", 0)
            results["failed"].extend(domain_result.get("failed", []))
        
        return results

    def get_deletion_statistics(self) -> Dict[str, Any]:
        """Get statistics about potential deletions."""
        if not self.db_path:
            return {"error": "No database configured"}
            
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get domain statistics
            cursor = conn.execute("""
                SELECT sender_domain, COUNT(*) as count
                FROM emails_metadata
                GROUP BY sender_domain
                ORDER BY count DESC
            """)
            
            domain_stats = {}
            total_emails = 0
            
            for domain, count in cursor.fetchall():
                domain_stats[domain] = count
                total_emails += count
            
            # Get label statistics for deletion candidates
            cursor = conn.execute("""
                SELECT labels, COUNT(*) as count
                FROM emails_metadata
                WHERE labels LIKE '%CATEGORY_PROMOTIONS%'
                OR labels LIKE '%CATEGORY_SOCIAL%'
                GROUP BY labels
            """)
            
            promotional_social_count = sum(count for _, count in cursor.fetchall())
            
            conn.close()
            
            return {
                "total_emails": total_emails,
                "total_domains": len(domain_stats),
                "top_domains": dict(list(domain_stats.items())[:20]),
                "promotional_social_emails": promotional_social_count,
                "deletion_candidates_percentage": round((promotional_social_count / total_emails) * 100, 2) if total_emails > 0 else 0
            }
            
        except Exception as e:
            return {"error": str(e)}