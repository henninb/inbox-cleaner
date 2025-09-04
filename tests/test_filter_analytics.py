"""Tests for filter analytics and efficiency analysis functionality."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from inbox_cleaner.filter_analytics import FilterAnalytics


class TestFilterAnalytics:
    """Test cases for FilterAnalytics class."""

    def test_init_with_database_manager(self):
        """Test that FilterAnalytics initializes correctly with database manager."""
        mock_db_manager = MagicMock()
        
        analytics = FilterAnalytics(mock_db_manager)
        
        assert analytics.db_manager == mock_db_manager

    def test_analyze_filter_complexity_simple_filter(self):
        """Test complexity analysis for a simple filter."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        simple_filter = {
            'id': 'filter1',
            'criteria': {
                'from': 'test-sender'  # No @ symbol to avoid regex detection
            },
            'action': {
                'addLabelIds': ['TRASH']
            }
        }
        
        result = analytics.analyze_filter_complexity(simple_filter)
        
        assert result['complexity_score'] == 2  # 1 criteria + 1 label = 2
        assert result['filter_id'] == 'filter1'
        assert result['complexity_level'] == 'simple'  # <= 2 is simple

    def test_analyze_filter_complexity_complex_filter(self):
        """Test complexity analysis for a complex regex filter."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        complex_filter = {
            'id': 'filter2',
            'criteria': {
                'query': '(from:*.ml OR from:*.tk) AND (subject:prize OR subject:winner) NOT is:important',
                'subject': r'.*\b(win|prize|lottery|cash)\b.*'
            },
            'action': {
                'addLabelIds': ['TRASH'],
                'removeLabelIds': ['INBOX', 'UNREAD']
            }
        }
        
        result = analytics.analyze_filter_complexity(complex_filter)
        
        assert result['complexity_score'] >= 4
        assert result['filter_id'] == 'filter2'
        assert result['complexity_level'] == 'complex'
        assert 'Multiple criteria' in result['description']

    def test_identify_duplicate_filters(self):
        """Test identification of duplicate filters."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        filters = [
            {
                'id': 'filter1',
                'criteria': {'from': 'spam@example.com'},
                'action': {'addLabelIds': ['TRASH']}
            },
            {
                'id': 'filter2',
                'criteria': {'from': 'spam@example.com'},
                'action': {'addLabelIds': ['TRASH']}
            },
            {
                'id': 'filter3',
                'criteria': {'from': 'different@example.com'},
                'action': {'addLabelIds': ['TRASH']}
            }
        ]
        
        duplicates = analytics.identify_duplicate_filters(filters)
        
        assert len(duplicates) == 1
        assert duplicates[0]['count'] == 2
        assert duplicates[0]['criteria']['from'] == 'spam@example.com'

    def test_suggest_filter_optimizations(self):
        """Test filter optimization suggestions."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
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
            }
        ]
        
        optimizations = analytics.suggest_filter_optimizations(filters)
        
        assert len(optimizations) == 1
        assert optimizations[0]['type'] == 'consolidate_domain'
        assert optimizations[0]['domain'] == 'spam.com'
        assert len(optimizations[0]['filters_to_consolidate']) == 3
        assert optimizations[0]['new_filter']['criteria']['from'] == '*@spam.com'

    def test_track_filter_usage(self):
        """Test filter usage tracking."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        # Reset call count after schema creation
        mock_db_manager.execute_query.reset_mock()
        
        filter_id = 'filter123'
        email_id = 'email456'
        
        analytics.track_filter_usage(filter_id, email_id)
        
        mock_db_manager.execute_query.assert_called_once()
        call_args = mock_db_manager.execute_query.call_args
        assert 'INSERT INTO filter_usage' in call_args[0][0]
        assert filter_id in call_args[0][1]
        assert email_id in call_args[0][1]

    def test_get_filter_usage_stats(self):
        """Test retrieval of filter usage statistics."""
        mock_db_manager = MagicMock()
        
        # Mock database results
        mock_db_manager.fetch_all.return_value = [
            ('filter1', 25, '2024-01-01'),
            ('filter2', 10, '2024-01-02'),
            ('filter3', 0, None)
        ]
        
        analytics = FilterAnalytics(mock_db_manager)
        
        stats = analytics.get_filter_usage_stats()
        
        assert len(stats) == 3
        assert stats[0]['filter_id'] == 'filter1'
        assert stats[0]['usage_count'] == 25
        assert stats[0]['last_used'] == '2024-01-01'
        
        # Check for unused filter
        unused_filter = next(f for f in stats if f['filter_id'] == 'filter3')
        assert unused_filter['usage_count'] == 0
        assert unused_filter['last_used'] is None

    def test_identify_unused_filters(self):
        """Test identification of unused filters."""
        mock_db_manager = MagicMock()
        
        # Mock filter usage data - filter3 has no usage
        mock_db_manager.fetch_all.return_value = [
            ('filter1', 25, '2024-01-01'),
            ('filter2', 10, '2024-01-02'),
        ]
        
        analytics = FilterAnalytics(mock_db_manager)
        
        # Mock all existing filters
        all_filters = [
            {'id': 'filter1', 'criteria': {'from': 'test1@spam.com'}},
            {'id': 'filter2', 'criteria': {'from': 'test2@spam.com'}},
            {'id': 'filter3', 'criteria': {'from': 'test3@spam.com'}},
        ]
        
        unused_filters = analytics.identify_unused_filters(all_filters, days=30)
        
        assert len(unused_filters) == 1
        assert unused_filters[0]['id'] == 'filter3'

    def test_generate_efficiency_report(self):
        """Test generation of comprehensive efficiency report."""
        mock_db_manager = MagicMock()
        
        # Mock usage stats
        mock_db_manager.fetch_all.return_value = [
            ('filter1', 100, '2024-01-01'),
            ('filter2', 0, None),
        ]
        
        analytics = FilterAnalytics(mock_db_manager)
        
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
            }
        ]
        
        report = analytics.generate_efficiency_report(filters)
        
        assert 'summary' in report
        assert 'complexity_analysis' in report
        assert 'usage_statistics' in report
        assert 'optimizations' in report
        assert 'unused_filters' in report
        
        assert report['summary']['total_filters'] == 2
        assert report['summary']['unused_filters'] == 1

    def test_measure_filter_performance(self):
        """Test filter performance measurement."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        # Mock email data for performance testing
        mock_emails = [
            {'sender_email': 'test1@spam.com', 'subject': 'Test 1'},
            {'sender_email': 'test2@spam.com', 'subject': 'Test 2'},
            {'sender_email': 'legitimate@good.com', 'subject': 'Test 3'}
        ]
        
        filter_to_test = {
            'id': 'filter1',
            'criteria': {'from': '*@spam.com'},
            'action': {'addLabelIds': ['TRASH']}
        }
        
        performance = analytics.measure_filter_performance(filter_to_test, mock_emails)
        
        assert 'execution_time_ms' in performance
        assert 'matches_found' in performance
        assert 'filter_id' in performance
        assert performance['filter_id'] == 'filter1'
        assert performance['matches_found'] == 2  # Should match 2 spam emails

class TestFilterUsageTracking:
    """Test cases specifically for usage tracking functionality."""

    def test_create_usage_tracking_schema(self):
        """Test creation of usage tracking database schema."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        analytics.create_usage_tracking_schema()
        
        # Should call execute_query with CREATE TABLE statements
        assert mock_db_manager.execute_query.called
        call_args = mock_db_manager.execute_query.call_args_list
        
        # Check that filter_usage table creation was called
        create_calls = [call for call in call_args if 'CREATE TABLE' in str(call[0][0])]
        assert len(create_calls) >= 1
        assert any('filter_usage' in str(call) for call in create_calls)

    def test_bulk_track_filter_usage(self):
        """Test bulk tracking of filter usage for multiple emails."""
        mock_db_manager = MagicMock()
        analytics = FilterAnalytics(mock_db_manager)
        
        usage_data = [
            ('filter1', 'email1'),
            ('filter1', 'email2'),
            ('filter2', 'email3')
        ]
        
        analytics.bulk_track_filter_usage(usage_data)
        
        # Should call executemany for bulk insert
        mock_db_manager.executemany.assert_called_once()
        call_args = mock_db_manager.executemany.call_args
        assert 'INSERT INTO filter_usage' in call_args[0][0]
        
        # Data should be padded with None values for the 4-column table
        expected_padded_data = [
            ('filter1', 'email1', None, None),
            ('filter1', 'email2', None, None),
            ('filter2', 'email3', None, None)
        ]
        assert call_args[0][1] == expected_padded_data

    def test_get_filter_effectiveness_metrics(self):
        """Test calculation of filter effectiveness metrics."""
        mock_db_manager = MagicMock()
        
        # Mock database response for effectiveness query
        mock_db_manager.fetch_all.return_value = [
            ('filter1', 100, 95, 0.95),  # filter_id, emails_processed, matches, effectiveness
            ('filter2', 50, 10, 0.20),
            ('filter3', 200, 0, 0.0)
        ]
        
        analytics = FilterAnalytics(mock_db_manager)
        
        metrics = analytics.get_filter_effectiveness_metrics()
        
        assert len(metrics) == 3
        assert metrics[0]['filter_id'] == 'filter1'
        assert metrics[0]['effectiveness_ratio'] == 0.95
        assert metrics[2]['effectiveness_ratio'] == 0.0  # Unused filter