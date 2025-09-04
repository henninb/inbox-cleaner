# tests/test_spam_filters.py
import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime
from inbox_cleaner.spam_filters import SpamFilterManager
from inbox_cleaner.extractor import EmailMetadata


class TestSpamFilterManager:
    def test_init_with_database_manager(self):
        """Test that SpamFilterManager initializes correctly with database manager."""
        mock_db_manager = MagicMock()

        spam_filter = SpamFilterManager(mock_db_manager)

        assert spam_filter.db_manager == mock_db_manager

    def test_identify_spam_domains_detects_suspicious_tlds(self):
        """Test that suspicious TLD domains (.ml, .xyz) are identified as spam."""
        mock_db_manager = MagicMock()

        # Mock emails with suspicious TLD domains
        mock_emails = [
            {'sender_domain': 'cvbhyvyhvdhvgcds.ml', 'subject': "You've been chosen!"},
            {'sender_domain': 'saytmtopjavhd.xyz', 'subject': 'CLAIM YOUR $1000 BONUS'},
            {'sender_domain': 'legitimate-site.com', 'subject': 'Regular email'},
        ]
        mock_db_manager.search_emails.return_value = mock_emails

        spam_filter = SpamFilterManager(mock_db_manager)
        spam_domains = spam_filter.identify_spam_domains()

        assert 'cvbhyvyhvdhvgcds.ml' in spam_domains
        assert 'saytmtopjavhd.xyz' in spam_domains
        assert 'legitimate-site.com' not in spam_domains

    def test_identify_spam_domains_detects_money_scams(self):
        """Test that money/lottery scam patterns are detected."""
        mock_db_manager = MagicMock()

        mock_emails = [
            {'sender_domain': 'dlckids.com', 'subject': 'WIN $4,751,298 INSTANTLY CAE'},
            {'sender_domain': 'normal-site.com', 'subject': 'Your order confirmation'},
            {'sender_domain': 'scam-site.com', 'subject': 'JACKPOT WINNER - CLAIM NOW!'},
        ]
        mock_db_manager.search_emails.return_value = mock_emails

        spam_filter = SpamFilterManager(mock_db_manager)
        spam_domains = spam_filter.identify_spam_domains()

        assert 'dlckids.com' in spam_domains
        assert 'scam-site.com' in spam_domains
        assert 'normal-site.com' not in spam_domains

    def test_identify_spam_domains_detects_unclaimed_money_scams(self):
        """Test that unclaimed money scam patterns are detected."""
        mock_db_manager = MagicMock()

        mock_emails = [
            {'sender_domain': 'fondueflameless.com', 'subject': 'UNCLAIMED MONEY FOR BRIANHENNING'},
            {'sender_domain': 'meadco.taosight.com', 'subject': 'Unclaimed money for "brianhenning"'},
            {'sender_domain': 'bank.com', 'subject': 'Your account statement'},
        ]
        mock_db_manager.search_emails.return_value = mock_emails

        spam_filter = SpamFilterManager(mock_db_manager)
        spam_domains = spam_filter.identify_spam_domains()

        assert 'fondueflameless.com' in spam_domains
        assert 'meadco.taosight.com' in spam_domains
        assert 'bank.com' not in spam_domains

    def test_identify_spam_domains_detects_prize_scams(self):
        """Test that prize/winner scam patterns are detected."""
        mock_db_manager = MagicMock()

        mock_emails = [
            {'sender_domain': 'reha-kaiser.de', 'subject': 'BeOur...next...JACKPOTWINNER!_EDfED'},
            {'sender_domain': 'declidem.art', 'subject': 'Claim your $1000 BONUSBRIANHENNIN'},
            {'sender_domain': 'store.com', 'subject': 'Your reward points'},
        ]
        mock_db_manager.search_emails.return_value = mock_emails

        spam_filter = SpamFilterManager(mock_db_manager)
        spam_domains = spam_filter.identify_spam_domains()

        assert 'reha-kaiser.de' in spam_domains
        assert 'declidem.art' in spam_domains
        assert 'store.com' not in spam_domains

    def test_generate_retention_rules_creates_immediate_deletion_rules(self):
        """Test that spam domains get 0-day retention rules for immediate deletion."""
        mock_db_manager = MagicMock()

        spam_filter = SpamFilterManager(mock_db_manager)

        spam_domains = ['dlckids.com', 'fondueflameless.com', 'scamsite.ml']
        retention_rules = spam_filter.generate_retention_rules(spam_domains)

        assert len(retention_rules) == 4  # 3 domains + 1 TLD rule

        # Check that all rules have 0-day retention for immediate deletion
        for rule in retention_rules:
            assert rule['retention_days'] == 0
            # Either spam or suspicious in description
            desc_lower = rule['description'].lower()
            assert 'spam' in desc_lower or 'suspicious' in desc_lower
            # Domain should be one of the spam domains or a TLD
            assert rule['domain'] in spam_domains or rule['domain'].startswith('.')

    def test_generate_retention_rules_includes_tld_blocking(self):
        """Test that TLD-based blocking rules are generated."""
        mock_db_manager = MagicMock()

        spam_filter = SpamFilterManager(mock_db_manager)

        spam_domains = ['scamsite1.ml', 'scamsite2.ml', 'badsite.xyz', 'normal.com']
        retention_rules = spam_filter.generate_retention_rules(spam_domains)

        # Should have individual domain rules + TLD rules
        domain_rules = [r for r in retention_rules if not r['domain'].startswith('.')]
        tld_rules = [r for r in retention_rules if r['domain'].startswith('.')]

        assert len(domain_rules) == 4  # All individual domains
        assert len(tld_rules) == 2     # .ml and .xyz TLD rules

        # Check TLD rules
        tld_domains = [r['domain'] for r in tld_rules]
        assert '.ml' in tld_domains
        assert '.xyz' in tld_domains

    def test_create_gmail_filters_generates_filter_config(self):
        """Test that Gmail filter configuration is generated correctly."""
        mock_db_manager = MagicMock()

        spam_filter = SpamFilterManager(mock_db_manager)

        spam_domains = ['dlckids.com', 'scamsite.ml']
        filters = spam_filter.create_gmail_filters(spam_domains)

        assert len(filters) >= 2

        # Check that filters contain proper Gmail filter format
        for filter_config in filters:
            assert 'criteria' in filter_config
            assert 'action' in filter_config
            assert filter_config['action']['addLabelIds'] == ['TRASH']

    def test_analyze_spam_returns_comprehensive_report(self):
        """Test that analyze_spam returns a comprehensive spam analysis report."""
        mock_db_manager = MagicMock()

        mock_emails = [
            {'sender_domain': 'dlckids.com', 'subject': 'WIN $4,751,298 INSTANTLY CAE'},
            {'sender_domain': 'scamsite.ml', 'subject': "You've been chosen!"},
            {'sender_domain': 'normal.com', 'subject': 'Regular email'},
        ]
        mock_db_manager.search_emails.return_value = mock_emails

        spam_filter = SpamFilterManager(mock_db_manager)
        report = spam_filter.analyze_spam()

        assert 'spam_domains' in report
        assert 'spam_emails' in report
        assert 'categories' in report
        assert 'total_spam' in report

        assert len(report['spam_domains']) >= 2
        assert report['total_spam'] >= 2

        # Check categories are identified
        assert 'Money/Lottery Scams' in report['categories']
        assert 'Prize/Winner Scams' in report['categories']

    def test_save_filters_to_config_updates_yaml_file(self):
        """Test that spam filters are properly saved to config.yaml file."""
        mock_db_manager = MagicMock()

        spam_filter = SpamFilterManager(mock_db_manager)

        retention_rules = [
            {'domain': 'dlckids.com', 'retention_days': 0, 'description': 'Spam domain - immediate deletion'},
            {'domain': '.ml', 'retention_days': 0, 'description': 'Suspicious TLD - immediate deletion'}
        ]

        existing_config = {
            'gmail': {'client_id': 'test'},
            'database': {'path': 'test.db'},
            'retention_rules': [
                {'domain': 'usps.com', 'retention_days': 30}
            ]
        }

        with patch('builtins.open', mock_open()) as mock_file:
            with patch('yaml.safe_load', return_value=existing_config):
                with patch('yaml.dump') as mock_dump:
                    spam_filter.save_filters_to_config('config.yaml', retention_rules)

        # Verify that yaml.dump was called with updated config
        mock_dump.assert_called_once()
        updated_config = mock_dump.call_args[0][0]

        # Should have original rules plus new spam rules (+ comment headers)
        assert len(updated_config['retention_rules']) == 5  # 1 original + 2 comments + 2 spam rules
        # Check that the spam domain rule exists (ignore comment entries)
        domain_rules = [rule for rule in updated_config['retention_rules'] if isinstance(rule, dict) and 'domain' in rule and not rule.get('_comment')]
        assert any(rule['domain'] == 'dlckids.com' for rule in domain_rules)
        assert any(rule['domain'] == '.ml' for rule in domain_rules)

    def test_create_filters_end_to_end_workflow(self):
        """Test the complete create_filters workflow."""
        mock_db_manager = MagicMock()

        mock_emails = [
            {'sender_domain': 'dlckids.com', 'subject': 'WIN $4,751,298 INSTANTLY CAE', 'message_id': 'msg1'},
            {'sender_domain': 'scamsite.ml', 'subject': "You've been chosen!", 'message_id': 'msg2'},
        ]
        mock_db_manager.search_emails.return_value = mock_emails

        spam_filter = SpamFilterManager(mock_db_manager)

        with patch.object(spam_filter, 'save_filters_to_config') as mock_save:
            result = spam_filter.create_filters('config.yaml')

        assert 'spam_report' in result
        assert 'retention_rules' in result
        assert 'gmail_filters' in result

        # Should have found spam domains
        assert len(result['retention_rules']) >= 2

        # Should have called save_filters_to_config
        mock_save.assert_called_once()