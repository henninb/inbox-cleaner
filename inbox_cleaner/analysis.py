"""Simplified email analysis module for detecting spam, phishing, and generating insights."""

import re
import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter


class EmailAnalyzer:
    """Analyzes emails for spam, phishing, and generates insights."""

    # Spam/phishing indicators
    SPAM_KEYWORDS = [
        'urgent', 'act now', 'limited time', 'click here', 'free', 'winner',
        'congratulations', 'suspended', 'verify account', 'update payment',
        'confirm identity', 'immediate action required', 'expires today',
        'cash prize', 'guaranteed', 'no obligation', 'risk free'
    ]
    
    SUSPICIOUS_DOMAINS = [
        'suspicious-bank.com', 'fake-paypal.com', 'phishing-site.com',
        'secure-update.com', 'account-verify.net', 'banking-alert.org'
    ]
    
    PHISHING_PATTERNS = [
        r'click\s+here\s+immediately',
        r'verify\s+your\s+account',
        r'suspended.*account',
        r'update.*payment.*method',
        r'confirm.*identity'
    ]

    def __init__(self, db_path: str):
        """Initialize analyzer with database path."""
        self.db_path = db_path

    def _execute_query(self, query: str, params: tuple = ()) -> List[tuple]:
        """Helper method to execute queries safely."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()

    def detect_suspicious_emails(self) -> List[Dict[str, Any]]:
        """Detect potentially spam or phishing emails."""
        query = """
            SELECT message_id, sender_domain, subject, snippet, labels
            FROM emails_metadata
            ORDER BY date_received DESC
        """
        
        rows = self._execute_query(query)
        suspicious = []
        
        for row in rows:
            message_id, sender_domain, subject, snippet, labels_json = row
            
            # Parse labels safely
            try:
                labels = json.loads(labels_json) if labels_json else []
            except (json.JSONDecodeError, TypeError):
                labels = []
            
            risk_score = 0
            indicators = []
            
            # Check for suspicious domain
            if sender_domain in self.SUSPICIOUS_DOMAINS:
                risk_score += 50
                indicators.append("suspicious_domain")
            
            # Check for spam keywords in subject
            subject_lower = (subject or "").lower()
            spam_count = sum(1 for keyword in self.SPAM_KEYWORDS 
                           if keyword in subject_lower)
            if spam_count > 0:
                risk_score += spam_count * 10
                indicators.append(f"spam_keywords_{spam_count}")
            
            # Check for phishing patterns
            text_to_check = f"{subject} {snippet}".lower()
            for pattern in self.PHISHING_PATTERNS:
                if re.search(pattern, text_to_check, re.IGNORECASE):
                    risk_score += 30
                    indicators.append("phishing_pattern")
                    break
            
            # Check for excessive punctuation/caps
            if subject:
                exclamation_count = subject.count('!')
                if exclamation_count >= 3:
                    risk_score += 20
                    indicators.append("excessive_punctuation")
                
                caps_ratio = sum(1 for c in subject if c.isupper()) / len(subject)
                if caps_ratio > 0.7:
                    risk_score += 15
                    indicators.append("excessive_caps")
            
            # If risk score is high enough, mark as suspicious
            if risk_score >= 30:
                suspicious.append({
                    "message_id": message_id,
                    "sender_domain": sender_domain,
                    "subject": subject,
                    "risk_score": risk_score,
                    "indicators": indicators,
                    "labels": labels
                })
        
        return sorted(suspicious, key=lambda x: x["risk_score"], reverse=True)

    def get_spam_indicators(self) -> Dict[str, Any]:
        """Get spam indicator statistics."""
        query = "SELECT sender_domain, subject, snippet FROM emails_metadata"
        rows = self._execute_query(query)
        
        indicators = {
            "urgent_language": 0,
            "suspicious_domains": 0,
            "phishing_patterns": 0,
            "excessive_punctuation": 0,
            "total_analyzed": len(rows)
        }
        
        for sender_domain, subject, snippet in rows:
            if sender_domain in self.SUSPICIOUS_DOMAINS:
                indicators["suspicious_domains"] += 1
            
            text_to_check = f"{subject} {snippet}".lower()
            
            # Check for urgent language
            if any(keyword in text_to_check for keyword in 
                  ['urgent', 'immediate', 'act now', 'expires']):
                indicators["urgent_language"] += 1
            
            # Check for phishing patterns
            if any(re.search(pattern, text_to_check, re.IGNORECASE) 
                  for pattern in self.PHISHING_PATTERNS):
                indicators["phishing_patterns"] += 1
            
            # Check for excessive punctuation
            if subject and subject.count('!') >= 3:
                indicators["excessive_punctuation"] += 1
        
        return indicators

    def get_domain_distribution(self) -> Dict[str, Dict[str, Any]]:
        """Get email distribution by domain."""
        query = """
            SELECT sender_domain, COUNT(*) as count,
                   MAX(date_received) as latest_email,
                   MIN(date_received) as earliest_email
            FROM emails_metadata
            GROUP BY sender_domain
            ORDER BY count DESC
        """
        
        rows = self._execute_query(query)
        distribution = {}
        
        for domain, count, latest, earliest in rows:
            distribution[domain] = {
                "count": count,
                "latest_email": latest,
                "earliest_email": earliest
            }
        
        return distribution

    def get_category_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Analyze emails by category."""
        query = """
            SELECT category, sender_domain, labels
            FROM emails_metadata
            WHERE category IS NOT NULL
        """
        
        rows = self._execute_query(query)
        categories = defaultdict(lambda: {"count": 0, "domains": Counter()})
        
        for category, domain, labels_json in rows:
            # Parse labels safely
            try:
                labels = json.loads(labels_json) if labels_json else []
            except (json.JSONDecodeError, TypeError):
                labels = []
            
            categories[category]["count"] += 1
            categories[category]["domains"][domain] += 1
            
            # Add label analysis
            if "labels" not in categories[category]:
                categories[category]["labels"] = Counter()
            for label in labels:
                categories[category]["labels"][label] += 1
        
        # Convert Counter objects to regular dicts for JSON serialization
        for category in categories:
            categories[category]["domains"] = dict(categories[category]["domains"])
            if "labels" in categories[category]:
                categories[category]["labels"] = dict(categories[category]["labels"])
        
        return dict(categories)

    def get_cleanup_recommendations(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate automated cleanup recommendations."""
        recommendations = {
            "expired_emails": [],
            "spam_candidates": [],
            "bulk_promotional": [],
            "old_social": []
        }
        
        # Get expired USPS emails (older than 30 days)
        expired_usps = self.get_expired_usps_emails(days_to_keep=30)
        recommendations["expired_emails"] = expired_usps
        
        # Get spam candidates
        suspicious = self.detect_suspicious_emails()
        recommendations["spam_candidates"] = suspicious[:20]  # Top 20 most suspicious
        
        # Get bulk promotional emails
        promo_query = """
            SELECT message_id, sender_domain, subject, date_received, labels
            FROM emails_metadata
            WHERE labels LIKE '%CATEGORY_PROMOTIONS%'
            ORDER BY date_received DESC
            LIMIT 50
        """
        
        promo_rows = self._execute_query(promo_query)
        for message_id, domain, subject, date_received, labels_json in promo_rows:
            try:
                labels = json.loads(labels_json) if labels_json else []
            except (json.JSONDecodeError, TypeError):
                labels = []
            
            recommendations["bulk_promotional"].append({
                "message_id": message_id,
                "sender_domain": domain,
                "subject": subject,
                "date_received": date_received,
                "labels": labels
            })
        
        # Get old social emails (older than 7 days)
        cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
        social_query = """
            SELECT message_id, sender_domain, subject, date_received, labels
            FROM emails_metadata
            WHERE labels LIKE '%CATEGORY_SOCIAL%'
            AND date_received < ?
            ORDER BY date_received ASC
            LIMIT 30
        """
        
        social_rows = self._execute_query(social_query, (cutoff_date,))
        for message_id, domain, subject, date_received, labels_json in social_rows:
            try:
                labels = json.loads(labels_json) if labels_json else []
            except (json.JSONDecodeError, TypeError):
                labels = []
            
            recommendations["old_social"].append({
                "message_id": message_id,
                "sender_domain": domain,
                "subject": subject,
                "date_received": date_received,
                "labels": labels
            })
        
        return recommendations

    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get comprehensive email statistics."""
        stats = {}
        
        # Total emails
        total_query = "SELECT COUNT(*) FROM emails_metadata"
        stats["total_emails"] = self._execute_query(total_query)[0][0]
        
        # Label distribution
        labels_query = "SELECT labels FROM emails_metadata"
        labels_rows = self._execute_query(labels_query)
        
        label_stats = Counter()
        for (labels_json,) in labels_rows:
            try:
                labels = json.loads(labels_json) if labels_json else []
                for label in labels:
                    label_stats[label] += 1
            except (json.JSONDecodeError, TypeError):
                continue
        stats["label_distribution"] = dict(label_stats.most_common(10))
        
        # Domain distribution
        domain_dist = self.get_domain_distribution()
        stats["domain_distribution"] = dict(sorted(
            domain_dist.items(), 
            key=lambda x: x[1]["count"], 
            reverse=True
        )[:10])
        
        # Category breakdown
        stats["category_breakdown"] = self.get_category_analysis()
        
        # Time distribution (emails per month)
        time_query = """
            SELECT DATE(date_received, 'start of month') as month, COUNT(*)
            FROM emails_metadata
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        """
        time_rows = self._execute_query(time_query)
        stats["time_distribution"] = dict(time_rows)
        
        # Suspicious email count
        suspicious = self.detect_suspicious_emails()
        stats["suspicious_count"] = len(suspicious)
        
        return stats

    def get_expired_usps_emails(self, days_to_keep: int = 30) -> List[Dict[str, Any]]:
        """Get USPS emails older than specified days."""
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
        
        query = """
            SELECT message_id, sender_domain, subject, date_received, labels
            FROM emails_metadata
            WHERE sender_domain LIKE '%usps.com'
            AND date_received < ?
            ORDER BY date_received ASC
        """
        
        rows = self._execute_query(query, (cutoff_date,))
        expired = []
        
        for message_id, domain, subject, date_received, labels_json in rows:
            try:
                labels = json.loads(labels_json) if labels_json else []
            except (json.JSONDecodeError, TypeError):
                labels = []
            
            expired.append({
                "message_id": message_id,
                "sender_domain": domain,
                "subject": subject,
                "date_received": date_received,
                "labels": labels,
                "days_old": (datetime.now() - datetime.fromisoformat(date_received)).days
            })
        
        return expired

    def analyze_promotional_emails(self) -> Dict[str, Any]:
        """Analyze promotional emails and provide insights."""
        analysis = {
            "total_promotional": 0,
            "top_domains": {},
            "recommendations": []
        }
        
        # Count promotional emails
        count_query = """
            SELECT COUNT(*) FROM emails_metadata
            WHERE labels LIKE '%CATEGORY_PROMOTIONS%' 
            OR category = 'promotional'
        """
        analysis["total_promotional"] = self._execute_query(count_query)[0][0]
        
        # Top promotional domains
        domains_query = """
            SELECT sender_domain, COUNT(*) as count
            FROM emails_metadata
            WHERE labels LIKE '%CATEGORY_PROMOTIONS%' 
            OR category = 'promotional'
            GROUP BY sender_domain
            ORDER BY count DESC
            LIMIT 10
        """
        domain_rows = self._execute_query(domains_query)
        analysis["top_domains"] = dict(domain_rows)
        
        # Generate recommendations
        if analysis["total_promotional"] > 100:
            analysis["recommendations"].append(
                "Consider unsubscribing from domains with excessive promotional emails"
            )
        if analysis["total_promotional"] > 500:
            analysis["recommendations"].append(
                "Set up automatic deletion for promotional emails older than 7 days"
            )
        
        return analysis

    def analyze_social_emails(self) -> Dict[str, Any]:
        """Analyze social media emails."""
        analysis = {
            "total_social": 0,
            "platforms": {},
            "recent_activity": 0
        }
        
        # Count social emails
        count_query = """
            SELECT COUNT(*) FROM emails_metadata
            WHERE labels LIKE '%CATEGORY_SOCIAL%' 
            OR category = 'social'
        """
        analysis["total_social"] = self._execute_query(count_query)[0][0]
        
        # Platform breakdown
        platforms_query = """
            SELECT sender_domain, COUNT(*) as count
            FROM emails_metadata
            WHERE labels LIKE '%CATEGORY_SOCIAL%' 
            OR category = 'social'
            GROUP BY sender_domain
            ORDER BY count DESC
        """
        platform_rows = self._execute_query(platforms_query)
        analysis["platforms"] = dict(platform_rows)
        
        # Recent activity (last 7 days)
        recent_date = (datetime.now() - timedelta(days=7)).isoformat()
        recent_query = """
            SELECT COUNT(*) FROM emails_metadata
            WHERE (labels LIKE '%CATEGORY_SOCIAL%' OR category = 'social')
            AND date_received > ?
        """
        analysis["recent_activity"] = self._execute_query(recent_query, (recent_date,))[0][0]
        
        return analysis