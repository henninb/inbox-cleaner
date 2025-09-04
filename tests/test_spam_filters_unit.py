import tempfile
from pathlib import Path
from typing import List, Dict
from unittest.mock import patch

import yaml
import pytest

from inbox_cleaner.spam_filters import SpamFilterManager


class FakeDB:
    def __init__(self, emails: List[Dict]):
        self._emails = emails

    def search_emails(self, query: str, per_page: int = 1000):
        return list(self._emails)[:per_page]


@pytest.mark.unit
def test_identify_spam_domains_patterns_and_tlds():
    emails = [
        {
            'sender_domain': 'shady.ml',
            'subject': 'Win $1,000,000 jackpot lottery winner',
        },
        {
            'sender_domain': 'promo.example.com',
            'subject': 'Claim your prize bonus now',
        },
        {
            'sender_domain': 'legit.com',
            'subject': 'Weekly newsletter',
        },
    ]
    manager = SpamFilterManager(FakeDB(emails))
    domains = manager.identify_spam_domains()
    assert 'shady.ml' in domains  # suspicious TLD + money pattern
    assert 'promo.example.com' in domains  # prize/bonus pattern
    assert 'legit.com' not in domains


@pytest.mark.unit
def test_generate_retention_rules_includes_tld_rules_once():
    manager = SpamFilterManager(FakeDB([]))
    spam_domains = {"bad.ml", "other.xyz", "regular.com"}
    rules = manager.generate_retention_rules(spam_domains)
    # Expect per-domain rules
    per_domain = {r['domain'] for r in rules if not r['domain'].startswith('.')}
    assert {"bad.ml", "other.xyz", "regular.com"} <= per_domain
    # Expect TLD rules for .ml and .xyz (the manager only adds tlds present)
    tld_rules = {r['domain'] for r in rules if r['domain'].startswith('.')}
    assert '.ml' in tld_rules
    assert '.xyz' in tld_rules


@pytest.mark.unit
def test_create_gmail_filters_structure_and_subject_rules():
    manager = SpamFilterManager(FakeDB([]))
    filters = manager.create_gmail_filters({"spam.com"})
    # One per domain + 5 subject-based filters
    assert len(filters) >= 6
    # Domain filter present
    domain_filter = next((f for f in filters if f['criteria'].get('from') == '*@spam.com'), None)
    assert domain_filter is not None
    assert set(domain_filter['action']['removeLabelIds']) >= {'INBOX', 'UNREAD'}


@pytest.mark.unit
def test_analyze_spam_returns_categories_and_spam_emails():
    emails = [
        {'message_id': '1', 'sender_domain': 'win.xyz', 'subject': 'Win $250,000 now'},
        {'message_id': '2', 'sender_domain': 'alert.com', 'subject': 'NINJA FOODI giveaway'},
        {'message_id': '3', 'sender_domain': 'normal.com', 'subject': 'Hello world'},
    ]
    manager = SpamFilterManager(FakeDB(emails))
    report = manager.analyze_spam()
    assert report['total_spam'] >= 2
    assert 'Money/Lottery Scams' in report['categories'] or 'Fake Company Notifications' in report['categories']
    # Ensure each spam email carries categories list
    for e in report['spam_emails']:
        assert isinstance(e.get('categories'), list)


@pytest.mark.unit
def test_save_filters_to_config_skips_some_tlds_and_adds_headers(tmp_path: Path):
    # Prepare base config file
    config_path = tmp_path / 'config.yaml'
    base = {'gmail': {'client_id': 'x'}, 'retention_rules': []}
    config_path.write_text(yaml.dump(base))

    manager = SpamFilterManager(FakeDB([]))
    rules = [
        {'domain': 'example.com', 'retention_days': 0, 'description': 'domain rule'},
        {'domain': '.ga', 'retention_days': 0, 'description': 'tld rule skipped'},
        {'domain': '.ml', 'retention_days': 0, 'description': 'tld rule allowed'},
    ]
    manager.save_filters_to_config(str(config_path), rules)

    updated = yaml.safe_load(config_path.read_text())
    rr = updated.get('retention_rules', [])
    # Contains header comments
    assert any(isinstance(x, dict) and '_comment' in x for x in rr)
    # Contains example.com and .ml but not .ga
    domains = [x['domain'] for x in rr if 'domain' in x]
    assert 'example.com' in domains
    assert '.ml' in domains
    assert '.ga' not in domains


@pytest.mark.unit
def test_create_filters_glue_invokes_substeps(tmp_path: Path):
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(yaml.dump({'retention_rules': []}))

    manager = SpamFilterManager(FakeDB([]))

    with patch.object(manager, 'analyze_spam', return_value={'spam_domains': ['evil.com']}), \
         patch.object(manager, 'generate_retention_rules', return_value=[{'domain': 'evil.com', 'retention_days': 0, 'description': 'x'}]) as gen_rules, \
         patch.object(manager, 'create_gmail_filters', return_value=[{'criteria': {'from': '*@evil.com'}, 'action': {'addLabelIds': ['TRASH']}}]) as create_filters, \
         patch.object(manager, 'save_filters_to_config') as save_config:
        result = manager.create_filters(str(config_path))

    assert 'spam_report' in result and 'retention_rules' in result and 'gmail_filters' in result
    gen_rules.assert_called_once()
    create_filters.assert_called_once()
    save_config.assert_called_once()


@pytest.mark.unit
def test_check_for_duplicate_filters():
    """Test that duplicate filters can be detected before creation."""
    manager = SpamFilterManager(FakeDB([]))
    
    existing_filters = [
        {
            'id': 'filter1',
            'criteria': {'from': '*@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter2', 
            'criteria': {'subject': 'WIN $*INSTANTLY*'},
            'action': {'addLabelIds': ['TRASH']}
        }
    ]
    
    new_filters = [
        {
            'criteria': {'from': '*@spam.com'},  # Duplicate
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'criteria': {'from': '*@newspam.com'},  # New
            'action': {'addLabelIds': ['TRASH']}
        }
    ]
    
    non_duplicates = manager.filter_out_duplicates(new_filters, existing_filters)
    
    # Should only contain the new filter, not the duplicate
    assert len(non_duplicates) == 1
    assert non_duplicates[0]['criteria']['from'] == '*@newspam.com'


@pytest.mark.unit
def test_identify_duplicate_filters():
    """Test that duplicate filters can be identified in a list."""
    manager = SpamFilterManager(FakeDB([]))
    
    filters = [
        {
            'id': 'filter1',
            'criteria': {'from': '*@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter2',
            'criteria': {'from': '*@spam.com'},  # Duplicate criteria
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter3',
            'criteria': {'subject': 'WIN $*'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter4',
            'criteria': {'subject': 'WIN $*'},  # Duplicate criteria
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter5',
            'criteria': {'from': '*@unique.com'},  # Unique
            'action': {'addLabelIds': ['TRASH']}
        }
    ]
    
    duplicates = manager.identify_duplicate_filters(filters)
    
    # Should identify 2 groups of duplicates
    assert len(duplicates) == 2
    
    # Find the spam.com duplicate group
    spam_group = next(group for group in duplicates if group['criteria'] == {'from': '*@spam.com'})
    assert len(spam_group['filters']) == 2
    assert 'filter1' in [f['id'] for f in spam_group['filters']]
    assert 'filter2' in [f['id'] for f in spam_group['filters']]
    
    # Find the WIN $* duplicate group  
    win_group = next(group for group in duplicates if group['criteria'] == {'subject': 'WIN $*'})
    assert len(win_group['filters']) == 2
    assert 'filter3' in [f['id'] for f in win_group['filters']]
    assert 'filter4' in [f['id'] for f in win_group['filters']]


@pytest.mark.unit
def test_identify_duplicate_filters_no_duplicates():
    """Test that no duplicates are identified when all filters are unique."""
    manager = SpamFilterManager(FakeDB([]))
    
    filters = [
        {
            'id': 'filter1',
            'criteria': {'from': '*@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter2',
            'criteria': {'from': '*@different.com'},
            'action': {'addLabelIds': ['TRASH']}
        }
    ]
    
    duplicates = manager.identify_duplicate_filters(filters)
    assert len(duplicates) == 0

