import tempfile
import os
from pathlib import Path
from typing import List, Dict
from unittest.mock import patch

import yaml
import pytest

from inbox_cleaner.spam_filters import SpamFilterManager
from inbox_cleaner.extractor import EmailMetadata


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


@pytest.mark.unit
def test_export_filters_to_xml():
    """Test exporting filters to XML format."""
    manager = SpamFilterManager(FakeDB([]))
    
    filters = [
        {
            'id': 'filter1',
            'criteria': {'from': 'spam@example.com'},
            'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
        },
        {
            'id': 'filter2',
            'criteria': {'subject': 'TEST SUBJECT'},
            'action': {'addLabelIds': ['IMPORTANT']}
        }
    ]
    
    xml_content = manager.export_filters_to_xml(filters)
    
    # Should contain XML structure
    assert '<?xml version="1.0" encoding="UTF-8"?>' in xml_content
    assert '<feed xmlns=' in xml_content
    assert '<entry>' in xml_content
    assert '<apps:property name="from" value="spam@example.com"/>' in xml_content
    assert '<apps:property name="subject" value="TEST SUBJECT"/>' in xml_content
    assert '<apps:property name="shouldTrash" value="true"/>' in xml_content
    assert '<apps:property name="label" value="IMPORTANT"/>' in xml_content
    assert '<apps:property name="shouldNeverSpam" value="true"/>' in xml_content


@pytest.mark.unit  
def test_optimize_filters():
    """Test filter optimization logic."""
    manager = SpamFilterManager(FakeDB([]))
    
    filters = [
        {
            'id': 'filter1',
            'criteria': {'from': 'user1@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter2', 
            'criteria': {'from': 'user2@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter3',
            'criteria': {'from': 'user3@spam.com'}, 
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter4',
            'criteria': {'from': 'legitimate@example.com'},
            'action': {'addLabelIds': ['INBOX']}
        }
    ]
    
    optimizations = manager.optimize_filters(filters)
    
    # Should identify optimization opportunities
    assert len(optimizations) > 0
    
    # Should suggest consolidating spam.com filters
    spam_consolidation = next(
        (opt for opt in optimizations if opt['type'] == 'consolidate_domain'),
        None
    )
    assert spam_consolidation is not None
    assert spam_consolidation['domain'] == 'spam.com'
    assert len(spam_consolidation['filters_to_remove']) == 3
    assert spam_consolidation['new_filter']['criteria']['from'] == '*@spam.com'


@pytest.mark.unit
def test_optimize_filters_no_opportunities():
    """Test filter optimization when no opportunities exist."""
    manager = SpamFilterManager(FakeDB([]))
    
    filters = [
        {
            'id': 'filter1',
            'criteria': {'from': 'unique1@example.com'},
            'action': {'addLabelIds': ['TRASH']}
        },
        {
            'id': 'filter2',
            'criteria': {'from': 'unique2@different.com'},
            'action': {'addLabelIds': ['INBOX']}
        }
    ]
    
    optimizations = manager.optimize_filters(filters)
    
    # Should find no optimization opportunities
    assert len(optimizations) == 0


@pytest.mark.unit
def test_merge_similar_filters():
    """Test merging multiple domain filters using wildcards."""
    manager = SpamFilterManager(FakeDB([]))
    
    # Mock Gmail service for filter operations
    from unittest.mock import MagicMock
    service = MagicMock()
    service.users.return_value.settings.return_value.filters.return_value.create.return_value.execute.return_value = {'id': 'new_filter_123'}
    service.users.return_value.settings.return_value.filters.return_value.delete.return_value.execute.return_value = None
    
    # Test data: multiple filters for same domain that can be merged
    filters_to_merge = [
        {
            'id': 'filter1',
            'criteria': {'from': 'user1@spam.com'},
            'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
        },
        {
            'id': 'filter2', 
            'criteria': {'from': 'user2@spam.com'},
            'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
        },
        {
            'id': 'filter3',
            'criteria': {'from': 'user3@spam.com'}, 
            'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
        }
    ]
    
    new_filter = {
        'criteria': {'from': '*@spam.com'},
        'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
    }
    
    result = manager.merge_similar_filters(service, filters_to_merge, new_filter)
    
    # Should successfully merge filters
    assert result['success'] is True
    assert result['merged_count'] == 3
    assert result['new_filter_id'] is not None
    
    # Should have called service to create new filter
    create_mock = service.users.return_value.settings.return_value.filters.return_value.create
    create_mock.assert_called_once_with(
        userId='me',
        body={
            'criteria': {'from': '*@spam.com'},
            'action': {'addLabelIds': ['TRASH'], 'removeLabelIds': ['INBOX']}
        }
    )
    
    # Should have called service to delete old filters
    delete_mock = service.users.return_value.settings.return_value.filters.return_value.delete
    assert delete_mock.call_count == 3


@pytest.mark.unit
def test_merge_similar_filters_creation_failure():
    """Test handling when new filter creation fails."""
    manager = SpamFilterManager(FakeDB([]))
    
    # Mock Gmail service to fail on filter creation
    from unittest.mock import MagicMock
    service = MagicMock()
    service.users.return_value.settings.return_value.filters.return_value.create.return_value.execute.side_effect = Exception("Creation failed")
    
    filters_to_merge = [
        {
            'id': 'filter1',
            'criteria': {'from': 'user1@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        }
    ]
    
    new_filter = {
        'criteria': {'from': '*@spam.com'},
        'action': {'addLabelIds': ['TRASH']}
    }
    
    result = manager.merge_similar_filters(service, filters_to_merge, new_filter)
    
    # Should fail gracefully
    assert result['success'] is False
    assert result['merged_count'] == 0
    assert 'error' in result
    
    # Should not have deleted any filters since creation failed
    delete_mock = service.users.return_value.settings.return_value.filters.return_value.delete
    delete_mock.assert_not_called()


@pytest.mark.unit
def test_merge_similar_filters_partial_deletion_failure():
    """Test handling when some filter deletions fail.""" 
    manager = SpamFilterManager(FakeDB([]))
    
    # Mock Gmail service 
    from unittest.mock import MagicMock
    service = MagicMock()
    service.users.return_value.settings.return_value.filters.return_value.create.return_value.execute.return_value = {'id': 'new_filter_123'}
    
    # Make second deletion fail
    service.users.return_value.settings.return_value.filters.return_value.delete.return_value.execute.side_effect = [
        None,  # First deletion succeeds
        Exception("Deletion failed"),  # Second deletion fails
        None   # Third deletion succeeds
    ]
    
    filters_to_merge = [
        {'id': 'filter1', 'criteria': {'from': 'user1@spam.com'}, 'action': {'addLabelIds': ['TRASH']}},
        {'id': 'filter2', 'criteria': {'from': 'user2@spam.com'}, 'action': {'addLabelIds': ['TRASH']}},
        {'id': 'filter3', 'criteria': {'from': 'user3@spam.com'}, 'action': {'addLabelIds': ['TRASH']}}
    ]
    
    new_filter = {
        'criteria': {'from': '*@spam.com'},
        'action': {'addLabelIds': ['TRASH']}
    }
    
    result = manager.merge_similar_filters(service, filters_to_merge, new_filter)
    
    # Should be successful but with warnings
    assert result['success'] is True
    assert result['merged_count'] == 2  # Only 2 successfully deleted
    assert result['new_filter_id'] == 'new_filter_123'
    assert result['failed_deletions'] == 1
    
    # Should have called deletion for all 3 filters
    delete_mock = service.users.return_value.settings.return_value.filters.return_value.delete
    assert delete_mock.call_count == 3


@pytest.mark.unit  
def test_apply_filter_optimizations():
    """Test applying multiple filter optimizations."""
    manager = SpamFilterManager(FakeDB([]))
    
    from unittest.mock import Mock, MagicMock
    service = MagicMock()
    service.users.return_value.settings.return_value.filters.return_value.create.return_value.execute.return_value = {'id': 'new_filter_123'}
    service.users.return_value.settings.return_value.filters.return_value.delete.return_value.execute.return_value = None
    
    # Test optimizations data
    optimizations = [
        {
            'type': 'consolidate_domain',
            'domain': 'spam.com',
            'filters_to_remove': [
                {'id': 'f1', 'criteria': {'from': 'user1@spam.com'}, 'action': {'addLabelIds': ['TRASH']}},
                {'id': 'f2', 'criteria': {'from': 'user2@spam.com'}, 'action': {'addLabelIds': ['TRASH']}},
                {'id': 'f3', 'criteria': {'from': 'user3@spam.com'}, 'action': {'addLabelIds': ['TRASH']}}
            ],
            'new_filter': {
                'criteria': {'from': '*@spam.com'},
                'action': {'addLabelIds': ['TRASH']}
            },
            'description': 'Test consolidation'
        }
    ]
    
    result = manager.apply_filter_optimizations(service, optimizations)
    
    # Should successfully apply all optimizations
    assert result['success'] is True
    assert result['optimizations_applied'] == 1
    assert result['total_merged'] == 3
    assert len(result['results']) == 1
    
    # Check individual optimization result
    opt_result = result['results'][0]
    assert opt_result['success'] is True
    assert opt_result['merged_count'] == 3
    
    # Should have created new filter and deleted old ones
    create_mock = service.users.return_value.settings.return_value.filters.return_value.create
    create_mock.assert_called_once_with(
        userId='me',
        body={
            'criteria': {'from': '*@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        }
    )
    delete_mock = service.users.return_value.settings.return_value.filters.return_value.delete
    assert delete_mock.call_count == 3


@pytest.mark.unit
def test_apply_filter_optimizations_empty_list():
    """Test applying optimizations with empty list."""
    manager = SpamFilterManager(FakeDB([]))
    
    from unittest.mock import MagicMock
    service = MagicMock()
    
    result = manager.apply_filter_optimizations(service, [])
    
    # Should handle empty list gracefully
    assert result['success'] is True
    assert result['optimizations_applied'] == 0
    assert result['total_merged'] == 0
    assert len(result['results']) == 0
    
    # Should not have made any service calls
    create_mock = service.users.return_value.settings.return_value.filters.return_value.create
    delete_mock = service.users.return_value.settings.return_value.filters.return_value.delete
    create_mock.assert_not_called()
    delete_mock.assert_not_called()


@pytest.mark.unit
def test_identify_spam_domains_all_patterns():
    """Test all spam detection patterns for comprehensive coverage."""
    
    # Create test emails that hit all uncovered spam detection lines
    test_emails = [
        {'sender_domain': 'unclaimed.com', 'subject': 'You have UNCLAIMED MONEY waiting'},  # Line 50
        {'sender_domain': 'scam.com', 'subject': 'We need to REACH YOU about your MONEY'},  # Line 50
        {'sender_domain': 'fake.com', 'subject': 'COSTCO has SELECTED you for a prize'},  # Line 54
        {'sender_domain': 'scammer.com', 'subject': 'You are CHOSEN for FREE AIRPODS'},  # Line 54  
        {'sender_domain': 'caps.com', 'subject': 'SCREAMING CAPS WITH $50000 DOLLARS'},  # Line 58
        {'sender_domain': 'million.com', 'subject': 'Win $10000000 today!'},  # Line 62 - Large amount
        {'sender_domain': 'normal.com', 'subject': 'Regular email subject'}  # Control case
    ]
    
    # Mock the database to return our test emails
    fake_db = FakeDB([])
    fake_db.search_emails = lambda query, per_page: test_emails
    
    manager = SpamFilterManager(fake_db)
    spam_domains = manager.identify_spam_domains()
    
    # Should identify all spam domains except the normal one
    expected_spam = {'unclaimed.com', 'scam.com', 'fake.com', 'scammer.com', 'caps.com', 'million.com'}
    assert spam_domains == expected_spam


@pytest.mark.unit 
def test_analyze_spam_all_categories():
    """Test spam analysis with all category patterns for coverage."""
    # Create test data that hits all spam category detection lines
    from datetime import datetime
    test_emails = [
        # Prize/Winner scams (lines 166-168) - as dict format since analyze_spam expects search_emails result
        {
            'message_id': '1',
            'sender_domain': 'scam.com',
            'subject': 'CLAIM YOUR PRIZE NOW!'
        },
        # Unclaimed money scams (lines 171-173)
        {
            'message_id': '2', 
            'sender_domain': 'scam.com',
            'subject': 'UNCLAIMED MONEY belongs to you'
        },
        # Fake company notifications (lines covered but want comprehensive test)
        {
            'message_id': '3',
            'sender_domain': 'company.com',
            'subject': 'COSTCO has CHOSEN you for NINJA FOODI'
        },
        # Normal email
        {
            'message_id': '4',
            'sender_domain': 'good.com', 
            'subject': 'Meeting tomorrow'
        }
    ]
    
    # Create manager with mocked database that returns our test emails
    manager = SpamFilterManager(FakeDB(test_emails))
    
    spam_report = manager.analyze_spam()
    
    # Should categorize emails correctly
    assert 'Prize/Winner Scams' in spam_report['categories']
    assert 'Unclaimed Money Scams' in spam_report['categories'] 
    assert 'Fake Company Notifications' in spam_report['categories']
    
    # Should identify spam domains
    expected_spam_domains = {'scam.com', 'company.com'}
    assert set(spam_report['spam_domains']) == expected_spam_domains


@pytest.mark.unit
def test_save_filters_to_config_no_existing_rules():
    """Test saving to config when no retention_rules section exists (line 209)."""
    manager = SpamFilterManager(FakeDB([]))
    
    config_content = {
        'gmail': {'client_id': 'test'},
        # No 'retention_rules' key
    }
    
    test_rules = [
        {'domain': 'spam.com', 'retention_days': 0, 'description': 'Test rule'}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_content, f)
        temp_path = f.name
    
    try:
        manager.save_filters_to_config(temp_path, test_rules)
        
        # Read back the config
        with open(temp_path, 'r') as f:
            updated_config = yaml.safe_load(f)
        
        # Should have created retention_rules section
        assert 'retention_rules' in updated_config
        assert len(updated_config['retention_rules']) > 0
    finally:
        os.unlink(temp_path)


@pytest.mark.unit
def test_export_filters_to_xml_all_criteria_types():
    """Test XML export with all criteria types for comprehensive coverage."""
    manager = SpamFilterManager(FakeDB([]))
    
    # Test filters with different criteria to hit all XML export lines
    filters = [
        {
            'id': 'filter1',
            'criteria': {'from': 'test@example.com', 'to': 'me@test.com'},
            'action': {'addLabelIds': ['SPAM'], 'removeLabelIds': ['UNREAD']}
        },
        {
            'id': 'filter2', 
            'criteria': {'subject': 'Test Subject', 'query': 'has:attachment'},
            'action': {'addLabelIds': ['IMPORTANT']}
        },
        {
            'id': 'filter3',
            'criteria': {'from': 'newsletter@company.com'},
            'action': {'removeLabelIds': ['INBOX', 'UNREAD']}
        }
    ]
    
    xml_content = manager.export_filters_to_xml(filters)
    
    # Should contain all criteria types (lines 318, 320, 322)
    assert '<apps:property name="to" value="me@test.com"/>' in xml_content
    assert '<apps:property name="subject" value="Test Subject"/>' in xml_content  
    assert '<apps:property name="hasTheWord" value="has:attachment"/>' in xml_content
    
    # Should contain spam action (line 331)
    assert '<apps:property name="shouldSpam" value="true"/>' in xml_content
    
    # Should contain mark as read action (lines 339-340)
    assert '<apps:property name="shouldMarkAsRead" value="true"/>' in xml_content
    assert '<apps:property name="shouldArchive" value="true"/>' in xml_content


@pytest.mark.unit
def test_merge_similar_filters_no_failed_deletions():
    """Test successful merge without any deletion failures."""
    manager = SpamFilterManager(FakeDB([]))
    
    from unittest.mock import MagicMock
    service = MagicMock()
    service.users.return_value.settings.return_value.filters.return_value.create.return_value.execute.return_value = {'id': 'new123'}
    service.users.return_value.settings.return_value.filters.return_value.delete.return_value.execute.return_value = None
    
    filters_to_merge = [
        {'id': 'f1', 'criteria': {'from': 'user1@test.com'}, 'action': {'addLabelIds': ['TRASH']}},
        {'id': 'f2', 'criteria': {'from': 'user2@test.com'}, 'action': {'addLabelIds': ['TRASH']}}
    ]
    
    new_filter = {
        'criteria': {'from': '*@test.com'},
        'action': {'addLabelIds': ['TRASH']}
    }
    
    result = manager.merge_similar_filters(service, filters_to_merge, new_filter)
    
    # Should be successful with no failed deletions (line 463 - successful path)
    assert result['success'] is True
    assert result['merged_count'] == 2
    assert result['failed_deletions'] == 0
    assert result['new_filter_id'] == 'new123'

