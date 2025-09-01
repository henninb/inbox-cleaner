"""AI-powered email analysis for spam detection and cleanup recommendations."""

import json
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
import anthropic

from .database import DatabaseManager
from .extractor import EmailMetadata


class AIEmailAnalyzer:
    """Analyzes emails using AI to identify spam, subscriptions, and cleanup opportunities."""
    
    def __init__(self, anthropic_api_key: str, db_manager: DatabaseManager):
        """Initialize AI analyzer with Anthropic API key and database."""
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.db = db_manager
    
    def analyze_email_patterns(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Analyze all emails in database to identify patterns."""
        print("🔍 Analyzing email patterns...")
        
        # Get domain statistics
        domain_stats = self.db.get_domain_statistics()
        total_emails = sum(domain_stats.values())
        
        # Get general statistics
        general_stats = self.db.get_statistics()
        
        # Analyze high-volume domains (potential spam or newsletters)
        high_volume_domains = {
            domain: count for domain, count in domain_stats.items() 
            if count >= 5  # Domains with 5+ emails
        }
        
        # Get sample emails from high-volume domains
        domain_samples = {}
        for domain in list(high_volume_domains.keys())[:20]:  # Top 20 domains
            samples = self.db.get_emails_by_domain(domain)[:3]  # 3 samples per domain
            domain_samples[domain] = [
                {
                    'subject': email['subject'][:100],
                    'labels': email['labels'],
                    'snippet': email['snippet'][:150]
                } 
                for email in samples
            ]
        
        analysis_data = {
            'total_emails': total_emails,
            'unique_domains': len(domain_stats),
            'high_volume_domains': high_volume_domains,
            'category_breakdown': general_stats.get('categories', {}),
            'label_breakdown': general_stats.get('labels', {}),
            'domain_samples': domain_samples
        }
        
        return analysis_data
    
    def create_privacy_safe_summary(self, analysis_data: Dict[str, Any]) -> str:
        """Create a privacy-safe summary for AI analysis."""
        
        # Create anonymized summary without exposing personal info
        summary_parts = [
            f"EMAIL ANALYSIS REQUEST",
            f"Total emails: {analysis_data['total_emails']}",
            f"Unique domains: {analysis_data['unique_domains']}",
            "",
            "HIGH-VOLUME DOMAINS (5+ emails each):"
        ]
        
        # Add domain analysis without personal info
        for domain, count in sorted(analysis_data['high_volume_domains'].items(), 
                                  key=lambda x: x[1], reverse=True):
            summary_parts.append(f"  • {domain}: {count} emails")
            
            # Add sample subjects (first 50 chars only)
            samples = analysis_data['domain_samples'].get(domain, [])
            for i, sample in enumerate(samples):
                subject = sample['subject'][:50] + "..." if len(sample['subject']) > 50 else sample['subject']
                labels = ', '.join(sample['labels'][:3])  # First 3 labels only
                summary_parts.append(f"    - Subject: \"{subject}\"")
                summary_parts.append(f"      Labels: {labels}")
        
        # Add category breakdown
        if analysis_data['category_breakdown']:
            summary_parts.append("\nEMAIL CATEGORIES:")
            for category, count in analysis_data['category_breakdown'].items():
                summary_parts.append(f"  • {category}: {count}")
        
        # Add label breakdown (Gmail's automatic categorization)
        if analysis_data['label_breakdown']:
            summary_parts.append("\nGMAIL LABELS:")
            for label, count in sorted(analysis_data['label_breakdown'].items(), 
                                     key=lambda x: x[1], reverse=True)[:15]:
                summary_parts.append(f"  • {label}: {count}")
        
        return "\n".join(summary_parts)
    
    def get_ai_recommendations(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI recommendations for email cleanup."""
        print("🤖 Getting AI recommendations...")
        
        privacy_summary = self.create_privacy_safe_summary(analysis_data)
        
        prompt = f"""
You are helping someone clean up their Gmail inbox. Analyze this email pattern data and provide actionable recommendations.

{privacy_summary}

Please analyze and provide recommendations in this JSON format:
{{
  "spam_domains": [
    {{"domain": "example.com", "reason": "Suspicious promotional emails", "confidence": 0.9}}
  ],
  "unsubscribe_candidates": [
    {{"domain": "newsletter.com", "reason": "High volume promotional emails", "action": "unsubscribe", "confidence": 0.8}}
  ],
  "security_concerns": [
    {{"domain": "suspicious.com", "reason": "Potential phishing/social engineering", "severity": "high"}}
  ],
  "newsletter_cleanup": [
    {{"domain": "updates.com", "recommendation": "Keep - valuable updates", "reason": "Low volume, relevant content"}}
  ],
  "bulk_actions": [
    {{"action": "delete", "criteria": "CATEGORY_PROMOTIONS emails older than 6 months", "estimated_count": "unknown"}}
  ],
  "summary": {{
    "total_cleanup_potential": "estimated number of emails that could be cleaned",
    "priority_actions": ["Most important 3 actions to take"],
    "inbox_health_score": "1-10 rating of current inbox cleanliness"
  }}
}}

Focus on:
1. Identifying likely spam/promotional domains with high email counts
2. Newsletters that send too frequently or seem low-value
3. Suspicious domains that might be phishing/social engineering
4. Bulk cleanup opportunities (old promotions, social media notifications)
5. Security-focused recommendations

Be conservative with deletion recommendations - only suggest removing obviously promotional/spam content.
"""

        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            response_text = response.content[0].text
            
            # Extract JSON from response (handle cases where AI adds explanation)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                recommendations = json.loads(json_text)
                return recommendations
            else:
                print("⚠️ Could not parse AI response as JSON")
                return {"error": "Failed to parse AI response"}
                
        except Exception as e:
            print(f"❌ AI analysis failed: {e}")
            return {"error": str(e)}
    
    def generate_cleanup_report(self, recommendations: Dict[str, Any]) -> str:
        """Generate a human-readable cleanup report."""
        if "error" in recommendations:
            return f"❌ Analysis failed: {recommendations['error']}"
        
        report_lines = [
            "📊 GMAIL INBOX CLEANUP ANALYSIS",
            "=" * 50,
            ""
        ]
        
        # Summary
        summary = recommendations.get('summary', {})
        if summary:
            report_lines.extend([
                f"🎯 Inbox Health Score: {summary.get('inbox_health_score', 'Unknown')}/10",
                f"🧹 Cleanup Potential: {summary.get('total_cleanup_potential', 'Unknown')} emails",
                ""
            ])
        
        # Priority Actions
        priority_actions = summary.get('priority_actions', [])
        if priority_actions:
            report_lines.append("🚨 TOP PRIORITY ACTIONS:")
            for i, action in enumerate(priority_actions, 1):
                report_lines.append(f"  {i}. {action}")
            report_lines.append("")
        
        # Spam Domains
        spam_domains = recommendations.get('spam_domains', [])
        if spam_domains:
            report_lines.append("🚫 SUSPECTED SPAM DOMAINS:")
            for spam in spam_domains:
                confidence = spam.get('confidence', 0) * 100
                report_lines.append(f"  • {spam['domain']} (Confidence: {confidence:.0f}%)")
                report_lines.append(f"    Reason: {spam['reason']}")
            report_lines.append("")
        
        # Security Concerns
        security_concerns = recommendations.get('security_concerns', [])
        if security_concerns:
            report_lines.append("⚠️  SECURITY CONCERNS:")
            for concern in security_concerns:
                severity = concern.get('severity', 'medium').upper()
                report_lines.append(f"  • {concern['domain']} [{severity} RISK]")
                report_lines.append(f"    {concern['reason']}")
            report_lines.append("")
        
        # Unsubscribe Candidates
        unsubscribe = recommendations.get('unsubscribe_candidates', [])
        if unsubscribe:
            report_lines.append("📮 UNSUBSCRIBE RECOMMENDATIONS:")
            for unsub in unsubscribe:
                confidence = unsub.get('confidence', 0) * 100
                report_lines.append(f"  • {unsub['domain']} (Confidence: {confidence:.0f}%)")
                report_lines.append(f"    {unsub['reason']}")
            report_lines.append("")
        
        # Newsletter Cleanup
        newsletter_cleanup = recommendations.get('newsletter_cleanup', [])
        if newsletter_cleanup:
            report_lines.append("📰 NEWSLETTER RECOMMENDATIONS:")
            for newsletter in newsletter_cleanup:
                report_lines.append(f"  • {newsletter['domain']}: {newsletter['recommendation']}")
                report_lines.append(f"    {newsletter['reason']}")
            report_lines.append("")
        
        # Bulk Actions
        bulk_actions = recommendations.get('bulk_actions', [])
        if bulk_actions:
            report_lines.append("🗂️  BULK CLEANUP OPPORTUNITIES:")
            for action in bulk_actions:
                report_lines.append(f"  • {action['action'].upper()}: {action['criteria']}")
                if 'estimated_count' in action:
                    report_lines.append(f"    Estimated impact: {action['estimated_count']} emails")
            report_lines.append("")
        
        report_lines.extend([
            "💡 NEXT STEPS:",
            "  1. Review recommendations above",
            "  2. Start with high-confidence spam domains", 
            "  3. Unsubscribe from unwanted newsletters",
            "  4. Delete old promotional emails",
            "  5. Set up filters for future cleanup",
            "",
            "🔒 PRIVACY NOTE: No email content was shared with AI - only domain patterns and subjects"
        ])
        
        return "\n".join(report_lines)
    
    def full_analysis(self) -> str:
        """Perform complete email analysis and return recommendations."""
        # Step 1: Analyze patterns
        analysis_data = self.analyze_email_patterns()
        
        # Step 2: Get AI recommendations
        recommendations = self.get_ai_recommendations(analysis_data)
        
        # Step 3: Generate report
        report = self.generate_cleanup_report(recommendations)
        
        return report, recommendations