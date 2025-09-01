"""Email cleanup automation engine."""

import time
from typing import List, Dict, Any, Optional
from googleapiclient.errors import HttpError
from .database import DatabaseManager


class EmailCleanupEngine:
    """Automates email cleanup operations via Gmail API."""
    
    def __init__(self, service: Any, db_manager: DatabaseManager):
        """Initialize cleanup engine."""
        self.service = service
        self.db = db_manager
        
    def search_emails_by_domain(self, domain: str, max_results: int = 1000) -> List[str]:
        """Search for email message IDs from a specific domain."""
        try:
            query = f"from:{domain}"
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = result.get('messages', [])
            return [msg['id'] for msg in messages]
            
        except HttpError as e:
            print(f"❌ Failed to search emails from {domain}: {e}")
            return []
    
    def delete_emails_by_domain(self, domain: str, dry_run: bool = True) -> Dict[str, Any]:
        """Delete all emails from a specific domain."""
        print(f"🎯 {'DRY RUN: ' if dry_run else ''}Deleting emails from {domain}")
        
        # Get message IDs from domain
        message_ids = self.search_emails_by_domain(domain)
        
        if not message_ids:
            return {"domain": domain, "deleted_count": 0, "error": "No emails found"}
        
        print(f"📧 Found {len(message_ids)} emails from {domain}")
        
        if dry_run:
            return {
                "domain": domain,
                "found_count": len(message_ids),
                "action": "DRY RUN - No emails deleted",
                "message_ids": message_ids[:5]  # Sample of IDs
            }
        
        # Delete emails in batches
        deleted_count = 0
        batch_size = 50  # Gmail API batch limit
        
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]
            
            try:
                # Delete batch
                for msg_id in batch:
                    self.service.users().messages().delete(
                        userId='me',
                        id=msg_id
                    ).execute()
                    deleted_count += 1
                    
                print(f"   Deleted batch {i//batch_size + 1}: {len(batch)} emails")
                
                # Rate limiting - pause between batches
                time.sleep(0.1)
                
            except HttpError as e:
                print(f"❌ Failed to delete batch: {e}")
                break
        
        return {
            "domain": domain,
            "found_count": len(message_ids),
            "deleted_count": deleted_count,
            "success": deleted_count > 0
        }
    
    def archive_emails_by_criteria(self, criteria: str, dry_run: bool = True) -> Dict[str, Any]:
        """Archive emails matching criteria (e.g., older than 6 months)."""
        print(f"🎯 {'DRY RUN: ' if dry_run else ''}Archiving emails: {criteria}")
        
        try:
            result = self.service.users().messages().list(
                userId='me',
                q=criteria,
                maxResults=1000
            ).execute()
            
            messages = result.get('messages', [])
            message_ids = [msg['id'] for msg in messages]
            
            if not message_ids:
                return {"criteria": criteria, "archived_count": 0, "error": "No emails found"}
            
            print(f"📧 Found {len(message_ids)} emails matching criteria")
            
            if dry_run:
                return {
                    "criteria": criteria,
                    "found_count": len(message_ids),
                    "action": "DRY RUN - No emails archived"
                }
            
            # Archive emails by removing INBOX label
            archived_count = 0
            for msg_id in message_ids:
                try:
                    self.service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['INBOX']}
                    ).execute()
                    archived_count += 1
                    
                    if archived_count % 50 == 0:
                        print(f"   Archived {archived_count} emails...")
                        time.sleep(0.1)  # Rate limiting
                        
                except HttpError as e:
                    print(f"❌ Failed to archive email {msg_id}: {e}")
                    continue
            
            return {
                "criteria": criteria,
                "found_count": len(message_ids),
                "archived_count": archived_count,
                "success": archived_count > 0
            }
            
        except HttpError as e:
            return {"criteria": criteria, "error": str(e)}
    
    def bulk_cleanup_recommendations(self) -> List[Dict[str, Any]]:
        """Generate bulk cleanup recommendations based on database analysis."""
        domain_stats = self.db.get_domain_statistics()
        recommendations = []
        
        # High-volume promotional domains (likely spam)
        high_volume_domains = [
            (domain, count) for domain, count in domain_stats.items() 
            if count > 100  # More than 100 emails from one domain
        ]
        
        for domain, count in high_volume_domains:
            # Check if domain is promotional/commercial
            commercial_indicators = [
                'email.', 't.', 'info.', 'noreply', 'marketing', 
                'promo', 'deals', 'offers', 'shop'
            ]
            
            is_likely_commercial = any(indicator in domain.lower() for indicator in commercial_indicators)
            
            if is_likely_commercial or count > 200:
                recommendations.append({
                    "action": "delete_domain",
                    "domain": domain,
                    "email_count": count,
                    "reason": f"High volume promotional emails ({count} emails)",
                    "confidence": "high" if count > 300 else "medium"
                })
        
        # Bulk archive recommendations
        stats = self.db.get_statistics()
        promo_count = stats.get('labels', {}).get('CATEGORY_PROMOTIONS', 0)
        
        if promo_count > 500:
            recommendations.append({
                "action": "archive_old_promotions",
                "criteria": "category:promotions older_than:6m",
                "estimated_count": promo_count // 2,
                "reason": "Archive old promotional emails",
                "confidence": "high"
            })
        
        social_count = stats.get('labels', {}).get('CATEGORY_SOCIAL', 0)
        if social_count > 100:
            recommendations.append({
                "action": "archive_old_social",
                "criteria": "category:social older_than:3m", 
                "estimated_count": social_count // 3,
                "reason": "Archive old social media notifications",
                "confidence": "medium"
            })
        
        return recommendations
    
    def execute_cleanup_plan(self, plan: List[Dict[str, Any]], dry_run: bool = True) -> List[Dict[str, Any]]:
        """Execute a cleanup plan with multiple actions."""
        results = []
        
        print(f"🧹 {'DRY RUN: ' if dry_run else ''}Executing cleanup plan...")
        print(f"📋 {len(plan)} actions to perform")
        
        for i, action in enumerate(plan, 1):
            print(f"\n📌 Action {i}/{len(plan)}: {action['action']}")
            
            if action['action'] == 'delete_domain':
                result = self.delete_emails_by_domain(
                    action['domain'], 
                    dry_run=dry_run
                )
                
            elif action['action'] in ['archive_old_promotions', 'archive_old_social']:
                result = self.archive_emails_by_criteria(
                    action['criteria'],
                    dry_run=dry_run
                )
                
            else:
                result = {"error": f"Unknown action: {action['action']}"}
            
            results.append(result)
            
            # Pause between actions to respect rate limits
            if not dry_run:
                time.sleep(1)
        
        return results
    
    def generate_cleanup_report(self, results: List[Dict[str, Any]]) -> str:
        """Generate a human-readable cleanup report."""
        report_lines = [
            "📊 EMAIL CLEANUP RESULTS",
            "=" * 40,
            ""
        ]
        
        total_deleted = 0
        total_archived = 0
        
        for result in results:
            if 'domain' in result:
                # Domain deletion result
                deleted = result.get('deleted_count', 0)
                found = result.get('found_count', 0)
                domain = result.get('domain', 'unknown')
                
                if 'error' in result:
                    report_lines.append(f"❌ {domain}: {result['error']}")
                else:
                    action = result.get('action', f"Deleted {deleted}")
                    report_lines.append(f"🗑️  {domain}: {action}")
                    total_deleted += deleted
                    
            elif 'criteria' in result:
                # Archive result  
                archived = result.get('archived_count', 0)
                criteria = result.get('criteria', 'unknown')
                
                if 'error' in result:
                    report_lines.append(f"❌ Archive {criteria}: {result['error']}")
                else:
                    action = result.get('action', f"Archived {archived}")
                    report_lines.append(f"📦 Archive {criteria}: {action}")
                    total_archived += archived
        
        report_lines.extend([
            "",
            f"📈 SUMMARY:",
            f"   🗑️  Total deleted: {total_deleted} emails",
            f"   📦 Total archived: {total_archived} emails", 
            f"   🎯 Total cleaned: {total_deleted + total_archived} emails"
        ])
        
        return "\n".join(report_lines)