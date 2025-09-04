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

    def filter_out_duplicates(self, new_filters: List[Dict[str, Any]], existing_filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out duplicate filters from new_filters based on existing_filters criteria."""
        # Extract criteria from existing filters for comparison
        existing_criteria = set()
        for existing_filter in existing_filters:
            criteria = existing_filter.get('criteria', {})
            # Convert criteria dict to a hashable format for comparison
            criteria_str = str(sorted(criteria.items()))
            existing_criteria.add(criteria_str)

        # Filter out duplicates from new filters
        non_duplicates = []
        for new_filter in new_filters:
            criteria = new_filter.get('criteria', {})
            criteria_str = str(sorted(criteria.items()))

            if criteria_str not in existing_criteria:
                non_duplicates.append(new_filter)

        return non_duplicates

    def identify_duplicate_filters(self, filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify duplicate filters in a list and return groups of duplicates."""
        # Group filters by their criteria
        criteria_groups = defaultdict(list)

        for filter_item in filters:
            criteria = filter_item.get('criteria', {})
            # Convert criteria dict to a hashable format for grouping
            criteria_str = str(sorted(criteria.items()))
            criteria_groups[criteria_str].append(filter_item)

        # Find groups with more than one filter (duplicates)
        duplicates = []
        for criteria_str, filter_list in criteria_groups.items():
            if len(filter_list) > 1:
                # Convert criteria string back to dict for display
                criteria_items = eval(criteria_str)  # Safe here since we created it
                criteria_dict = dict(criteria_items)

                duplicates.append({
                    'criteria': criteria_dict,
                    'filters': filter_list,
                    'count': len(filter_list)
                })

        return duplicates

    def export_filters_to_xml(self, filters: List[Dict[str, Any]]) -> str:
        """Export filters to Gmail XML format for backup/restore."""
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:apps="http://schemas.google.com/apps/2006">'
        ]

        for filter_item in filters:
            xml_lines.append('  <entry>')
            xml_lines.append('    <category term="filter"></category>')
            xml_lines.append('    <title>Mail Filter</title>')
            xml_lines.append('    <content></content>')
            xml_lines.append('    <apps:property name="hasTheWord" value=""/>')
            xml_lines.append('    <apps:property name="doesNotHaveTheWord" value=""/>')

            # Add criteria properties
            criteria = filter_item.get('criteria', {})
            if 'from' in criteria:
                xml_lines.append(f'    <apps:property name="from" value="{criteria["from"]}"/>')
            if 'to' in criteria:
                xml_lines.append(f'    <apps:property name="to" value="{criteria["to"]}"/>')
            if 'subject' in criteria:
                xml_lines.append(f'    <apps:property name="subject" value="{criteria["subject"]}"/>')
            if 'query' in criteria:
                xml_lines.append(f'    <apps:property name="hasTheWord" value="{criteria["query"]}"/>')

            # Add action properties
            action = filter_item.get('action', {})
            if 'addLabelIds' in action:
                for label in action['addLabelIds']:
                    if label == 'TRASH':
                        xml_lines.append('    <apps:property name="shouldTrash" value="true"/>')
                    elif label == 'SPAM':
                        xml_lines.append('    <apps:property name="shouldSpam" value="true"/>')
                    else:
                        xml_lines.append(f'    <apps:property name="label" value="{label}"/>')

            if 'removeLabelIds' in action:
                for label in action['removeLabelIds']:
                    if label == 'INBOX':
                        xml_lines.append('    <apps:property name="shouldArchive" value="true"/>')
                    elif label == 'UNREAD':
                        xml_lines.append('    <apps:property name="shouldMarkAsRead" value="true"/>')

            # Default properties for spam filters
            if 'TRASH' in action.get('addLabelIds', []):
                xml_lines.append('    <apps:property name="shouldNeverSpam" value="true"/>')

            xml_lines.append('  </entry>')

        xml_lines.append('</feed>')
        return '\n'.join(xml_lines)

    def optimize_filters(self, filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify filter optimization opportunities."""
        optimizations = []

        # Group filters by domain for consolidation opportunities
        domain_groups = defaultdict(list)

        for filter_item in filters:
            criteria = filter_item.get('criteria', {})
            if 'from' in criteria:
                from_value = criteria['from']
                # Extract domain from email patterns like user@domain.com or *@domain.com
                if '@' in from_value:
                    domain = from_value.split('@')[-1]
                    # Only consider if not already a wildcard pattern
                    if not from_value.startswith('*@'):
                        domain_groups[domain].append(filter_item)

        # Find domains with multiple individual email filters that could be consolidated
        for domain, domain_filters in domain_groups.items():
            if len(domain_filters) >= 3:  # Only optimize if 3+ filters for same domain
                # Check if all filters have the same action
                first_action = str(sorted(domain_filters[0].get('action', {}).items()))
                if all(str(sorted(f.get('action', {}).items())) == first_action for f in domain_filters):
                    # Create consolidation optimization
                    optimizations.append({
                        'type': 'consolidate_domain',
                        'domain': domain,
                        'filters_to_remove': domain_filters,
                        'new_filter': {
                            'criteria': {'from': f'*@{domain}'},
                            'action': domain_filters[0]['action'].copy()
                        },
                        'description': f'Consolidate {len(domain_filters)} filters for {domain} into single wildcard filter'
                    })

        return optimizations

    def merge_similar_filters(self, service, filters_to_merge: List[Dict[str, Any]], new_filter: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple similar filters into a single wildcard filter."""
        result = {
            'success': False,
            'merged_count': 0,
            'new_filter_id': None,
            'failed_deletions': 0,
            'error': None
        }

        try:
            # First, create the new consolidated filter
            response = service.users().settings().filters().create(
                userId='me',
                body={
                    'criteria': new_filter['criteria'],
                    'action': new_filter['action']
                }
            ).execute()

            result['new_filter_id'] = response.get('id')
            result['success'] = True

            # Now delete the old filters
            deleted_count = 0
            failed_deletions = 0

            for old_filter in filters_to_merge:
                filter_id = old_filter.get('id')
                try:
                    service.users().settings().filters().delete(
                        userId='me',
                        id=filter_id
                    ).execute()
                    deleted_count += 1
                except Exception as e:
                    failed_deletions += 1
                    # Continue trying to delete other filters

            result['merged_count'] = deleted_count
            result['failed_deletions'] = failed_deletions

        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            result['merged_count'] = 0

        return result

    def apply_filter_optimizations(self, service, optimizations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply multiple filter optimizations by merging similar filters."""
        result = {
            'success': True,
            'optimizations_applied': 0,
            'total_merged': 0,
            'results': [],
            'errors': []
        }

        if not optimizations:
            return result

        for optimization in optimizations:
            if optimization['type'] == 'consolidate_domain':
                filters_to_merge = optimization['filters_to_remove']
                new_filter = optimization['new_filter']

                merge_result = self.merge_similar_filters(service, filters_to_merge, new_filter)
                result['results'].append(merge_result)

                if merge_result['success']:
                    result['optimizations_applied'] += 1
                    result['total_merged'] += merge_result['merged_count']
                else:
                    result['errors'].append({
                        'optimization': optimization['description'],
                        'error': merge_result.get('error', 'Unknown error')
                    })

        # Overall success if at least some optimizations worked
        result['success'] = result['optimizations_applied'] > 0 or len(optimizations) == 0

        return result