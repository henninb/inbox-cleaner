"""Spam filter management for automated spam detection and filtering."""

import re
import yaml
from typing import List, Dict, Any, Set
from collections import defaultdict, Counter
from .database import DatabaseManager


class SpamFilterManager:
    """Manages spam detection and filter creation for inbox cleaning."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize spam filter manager with database connection."""
        self.db_manager = db_manager

        # Known spam indicators
        self.suspicious_tlds = ['.ml', '.tk', '.ga', '.cf', '.xyz']
        self.spam_keywords = [
            'free', 'win', 'winner', 'congratulations', 'prize', 'lottery', 'cash',
            'money', 'urgent', 'limited time', 'act now', 'click here', 'offer',
            'discount', 'save', '%', 'deal', 'sale', 'jackpot', 'claim', 'bonus'
        ]

    def identify_spam_domains(self) -> Set[str]:
        """Identify spam domains based on email content and domain patterns."""
        emails = self.db_manager.search_emails('', per_page=10000)
        spam_domains = set()

        for email in emails:
            domain = email.get('sender_domain', 'unknown').lower()
            subject = email.get('subject', '')

            is_spam = False

            # Check for suspicious TLDs
            if any(domain.endswith(tld) for tld in self.suspicious_tlds):
                is_spam = True

            # Money/lottery scam patterns
            if re.search(r'win.*\$[0-9,]+|jackpot.*winner|lottery', subject, re.IGNORECASE):
                is_spam = True

            # Prize/winner scam patterns
            if re.search(r'claim.*prize|claim.*bonus|you.*chosen|selected.*winner', subject, re.IGNORECASE):
                is_spam = True

            # Unclaimed money scam patterns
            if re.search(r'unclaimed.*money|reach.*you.*money', subject, re.IGNORECASE):
                is_spam = True

            # Fake company notification patterns
            if re.search(r'costco.*selected|costco.*chosen|airpods|ninja.*foodi', subject, re.IGNORECASE):
                is_spam = True

            # Excessive caps with money amounts
            if re.search(r'[A-Z]{8,}.*\$[0-9,]+', subject):
                is_spam = True

            # Large dollar amounts (scam indicator)
            if re.search(r'\$[0-9,]*[0-9]{6,}', subject):  # $1,000,000+
                is_spam = True

            if is_spam:
                spam_domains.add(domain)

        return spam_domains

    def generate_retention_rules(self, spam_domains: Set[str]) -> List[Dict[str, Any]]:
        """Generate retention rules for immediate deletion of spam domains."""
        retention_rules = []

        # Individual domain rules
        for domain in spam_domains:
            retention_rules.append({
                'domain': domain,
                'retention_days': 0,
                'description': f'Spam domain - immediate deletion ({domain})'
            })

        # Add TLD-based rules for common suspicious TLDs
        suspicious_tlds_found = set()
        for domain in spam_domains:
            for tld in self.suspicious_tlds:
                if domain.endswith(tld):
                    suspicious_tlds_found.add(tld)

        for tld in suspicious_tlds_found:
            retention_rules.append({
                'domain': tld,
                'retention_days': 0,
                'description': f'Suspicious TLD - immediate deletion (all {tld} domains)'
            })

        return retention_rules

    def create_gmail_filters(self, spam_domains: Set[str]) -> List[Dict[str, Any]]:
        """Create Gmail API filter configurations for spam domains."""
        filters = []

        # Individual domain filters
        for domain in spam_domains:
            filters.append({
                'criteria': {
                    'from': f'*@{domain}'
                },
                'action': {
                    'addLabelIds': ['TRASH'],
                    'removeLabelIds': ['INBOX', 'UNREAD']
                }
            })

        # Subject-based filters for common spam patterns
        spam_subject_patterns = [
            'WIN $*INSTANTLY*',
            'UNCLAIMED MONEY FOR*',
            'CLAIM YOUR $*BONUS*',
            'You have been chosen*',
            'JACKPOT WINNER*'
        ]

        for pattern in spam_subject_patterns:
            filters.append({
                'criteria': {
                    'subject': pattern
                },
                'action': {
                    'addLabelIds': ['TRASH'],
                    'removeLabelIds': ['INBOX', 'UNREAD']
                }
            })

        return filters

    def analyze_spam(self) -> Dict[str, Any]:
        """Perform comprehensive spam analysis and return detailed report."""
        emails = self.db_manager.search_emails('', per_page=10000)

        # Categorize spam types
        spam_categories = {
            'Money/Lottery Scams': [],
            'Prize/Winner Scams': [],
            'Unclaimed Money Scams': [],
            'Fake Company Notifications': [],
            'Suspicious TLD Domains': []
        }

        spam_domains = set()
        spam_emails = []

        for email in emails:
            domain = email.get('sender_domain', 'unknown').lower()
            subject = email.get('subject', '')
            message_id = email.get('message_id', '')

            is_spam = False
            categories = []

            # Categorize spam types
            if re.search(r'win.*\$[0-9,]+|jackpot.*winner|lottery', subject, re.IGNORECASE):
                spam_categories['Money/Lottery Scams'].append((domain, subject))
                categories.append('Money/Lottery Scams')
                is_spam = True

            if re.search(r'claim.*prize|claim.*bonus|you.*chosen|selected.*winner', subject, re.IGNORECASE):
                spam_categories['Prize/Winner Scams'].append((domain, subject))
                categories.append('Prize/Winner Scams')
                is_spam = True

            if re.search(r'unclaimed.*money|reach.*you.*money', subject, re.IGNORECASE):
                spam_categories['Unclaimed Money Scams'].append((domain, subject))
                categories.append('Unclaimed Money Scams')
                is_spam = True

            if re.search(r'costco.*selected|costco.*chosen|airpods|ninja.*foodi', subject, re.IGNORECASE):
                spam_categories['Fake Company Notifications'].append((domain, subject))
                categories.append('Fake Company Notifications')
                is_spam = True

            if any(domain.endswith(tld) for tld in self.suspicious_tlds):
                spam_categories['Suspicious TLD Domains'].append((domain, subject))
                categories.append('Suspicious TLD Domains')
                is_spam = True

            if is_spam:
                spam_domains.add(domain)
                spam_emails.append({
                    'domain': domain,
                    'subject': subject,
                    'message_id': message_id,
                    'categories': categories
                })

        return {
            'spam_domains': list(spam_domains),
            'spam_emails': spam_emails,
            'categories': {k: len(v) for k, v in spam_categories.items() if v},
            'total_spam': len(spam_emails),
            'detailed_categories': spam_categories
        }

    def save_filters_to_config(self, config_path: str, retention_rules: List[Dict[str, Any]]) -> None:
        """Save spam filtering rules to the config.yaml file."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Add spam rules to existing retention rules
        if 'retention_rules' not in config:
            config['retention_rules'] = []

        # Add spam section header comment
        spam_rules_with_header = [
            {'_comment': '# SPAM FILTERING RULES - Auto-generated'},
            {'_comment': '# These rules immediately delete identified spam domains'}
        ]

        # Add the actual spam rules
        for rule in retention_rules:
            # Skip TLD rules that might conflict with legitimate domains
            if not rule['domain'].startswith('.') or rule['domain'] in ['.ml', '.xyz']:
                spam_rules_with_header.append(rule)

        config['retention_rules'].extend(spam_rules_with_header)

        # Write updated config back to file
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)

    def create_filters(self, config_path: str) -> Dict[str, Any]:
        """Complete workflow to create spam filters and save to config."""
        # Analyze spam in database
        spam_report = self.analyze_spam()

        # Generate retention rules for identified spam domains
        spam_domains = set(spam_report['spam_domains'])
        retention_rules = self.generate_retention_rules(spam_domains)

        # Generate Gmail API filters
        gmail_filters = self.create_gmail_filters(spam_domains)

        # Save retention rules to config
        self.save_filters_to_config(config_path, retention_rules)

        return {
            'spam_report': spam_report,
            'retention_rules': retention_rules,
            'gmail_filters': gmail_filters
        }