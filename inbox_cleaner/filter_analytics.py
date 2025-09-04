"""Filter analytics for efficiency analysis and usage tracking."""

import re
import time
import json
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from .database import DatabaseManager


class FilterAnalytics:
    """Analyzes filter efficiency and tracks usage statistics."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize filter analytics with database manager."""
        self.db_manager = db_manager
        self.create_usage_tracking_schema()

    def create_usage_tracking_schema(self):
        """Create database tables for tracking filter usage."""
        create_usage_table = """
        CREATE TABLE IF NOT EXISTS filter_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filter_id TEXT NOT NULL,
            email_message_id TEXT NOT NULL,
            matched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            criteria_matched TEXT,
            action_applied TEXT,
            FOREIGN KEY (email_message_id) REFERENCES emails_metadata (message_id)
        )
        """

        create_filter_performance_table = """
        CREATE TABLE IF NOT EXISTS filter_performance (
            filter_id TEXT PRIMARY KEY,
            total_matches INTEGER DEFAULT 0,
            total_emails_processed INTEGER DEFAULT 0,
            avg_execution_time_ms REAL DEFAULT 0.0,
            effectiveness_ratio REAL DEFAULT 0.0,
            last_analyzed DATETIME DEFAULT CURRENT_TIMESTAMP,
            complexity_score INTEGER DEFAULT 1
        )
        """

        create_usage_index = """
        CREATE INDEX IF NOT EXISTS idx_filter_usage_filter_id
        ON filter_usage(filter_id)
        """

        create_usage_date_index = """
        CREATE INDEX IF NOT EXISTS idx_filter_usage_matched_at
        ON filter_usage(matched_at)
        """

        self.db_manager.execute_query(create_usage_table)
        self.db_manager.execute_query(create_filter_performance_table)
        self.db_manager.execute_query(create_usage_index)
        self.db_manager.execute_query(create_usage_date_index)

    def analyze_filter_complexity(self, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the complexity of a single filter."""
        complexity_score = 0
        complexity_factors = []

        criteria = filter_data.get('criteria', {})
        action = filter_data.get('action', {})

        # Analyze criteria complexity
        criteria_count = len(criteria)
        complexity_score += criteria_count

        if criteria_count > 1:
            complexity_factors.append('Multiple criteria')

        # Check for regex patterns
        for field, value in criteria.items():
            if isinstance(value, str):
                # Check for regex special characters
                regex_chars = r'[\.\*\+\?\[\]\(\)\{\}\|\^\$\\]'
                if re.search(regex_chars, value):
                    complexity_score += 2
                    complexity_factors.append(f'Regex in {field}')

                # Check for complex query syntax
                if field == 'query' and any(op in value.lower() for op in ['and', 'or', 'not', 'has:']):
                    complexity_score += 3
                    complexity_factors.append('Complex query syntax')

        # Analyze action complexity
        if 'addLabelIds' in action:
            complexity_score += len(action['addLabelIds'])
        if 'removeLabelIds' in action:
            complexity_score += len(action['removeLabelIds'])
        if len(action) > 2:
            complexity_score += 1
            complexity_factors.append('Multiple actions')

        # Determine complexity level
        if complexity_score <= 2:
            complexity_level = 'simple'
        elif complexity_score <= 5:
            complexity_level = 'moderate'
        else:
            complexity_level = 'complex'

        return {
            'filter_id': filter_data.get('id', 'unknown'),
            'complexity_score': complexity_score,
            'complexity_level': complexity_level,
            'factors': complexity_factors,
            'description': self._generate_complexity_description(complexity_level, complexity_factors)
        }

    def _generate_complexity_description(self, level: str, factors: List[str]) -> str:
        """Generate a human-readable description of filter complexity."""
        if level == 'simple':
            return "Simple sender filter with basic criteria"
        elif level == 'moderate':
            return f"Moderate complexity filter with {', '.join(factors[:2])}"
        else:
            return f"Complex filter with {', '.join(factors[:3])} and potentially high execution cost"

    def identify_duplicate_filters(self, filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify duplicate or near-duplicate filters."""
        criteria_groups = defaultdict(list)

        for filter_data in filters:
            criteria = filter_data.get('criteria', {})
            # Create a normalized string representation of criteria
            criteria_key = self._normalize_criteria(criteria)
            criteria_groups[criteria_key].append(filter_data)

        duplicates = []
        for criteria_key, group in criteria_groups.items():
            if len(group) > 1:
                # Parse criteria back from key for display
                criteria_dict = self._parse_criteria_key(criteria_key)
                duplicates.append({
                    'criteria': criteria_dict,
                    'filters': group,
                    'count': len(group),
                    'filter_ids': [f.get('id', 'unknown') for f in group]
                })

        return duplicates

    def _normalize_criteria(self, criteria: Dict[str, Any]) -> str:
        """Normalize criteria for comparison."""
        # Sort keys and create a consistent string representation
        normalized = {}
        for key, value in sorted(criteria.items()):
            if isinstance(value, str):
                normalized[key] = value.lower().strip()
            else:
                normalized[key] = value
        return json.dumps(normalized, sort_keys=True)

    def _parse_criteria_key(self, criteria_key: str) -> Dict[str, Any]:
        """Parse normalized criteria key back to dict."""
        try:
            return json.loads(criteria_key)
        except:
            return {'criteria': criteria_key}

    def suggest_filter_optimizations(self, filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest optimizations for filter efficiency."""
        optimizations = []

        # Group filters by domain for consolidation
        domain_groups = defaultdict(list)

        for filter_data in filters:
            criteria = filter_data.get('criteria', {})
            if 'from' in criteria:
                from_value = criteria['from']
                if '@' in from_value and not from_value.startswith('*@'):
                    # Extract domain from email
                    domain = from_value.split('@')[-1]
                    domain_groups[domain].append(filter_data)

        # Find consolidation opportunities
        for domain, domain_filters in domain_groups.items():
            if len(domain_filters) >= 3:
                # Check if all filters have similar actions
                first_action = domain_filters[0].get('action', {})
                if all(self._actions_are_similar(f.get('action', {}), first_action) for f in domain_filters):
                    optimizations.append({
                        'type': 'consolidate_domain',
                        'domain': domain,
                        'filters_to_consolidate': domain_filters,
                        'new_filter': {
                            'criteria': {'from': f'*@{domain}'},
                            'action': first_action.copy()
                        },
                        'description': f'Consolidate {len(domain_filters)} filters for domain {domain}',
                        'estimated_savings': len(domain_filters) - 1
                    })

        # Look for overly complex filters that could be simplified
        for filter_data in filters:
            complexity = self.analyze_filter_complexity(filter_data)
            if complexity['complexity_score'] > 6:
                optimizations.append({
                    'type': 'simplify_complex',
                    'filter_id': filter_data.get('id'),
                    'current_complexity': complexity['complexity_score'],
                    'description': f'Simplify overly complex filter (score: {complexity["complexity_score"]})',
                    'suggestions': self._suggest_simplifications(filter_data)
                })

        return optimizations

    def _actions_are_similar(self, action1: Dict[str, Any], action2: Dict[str, Any]) -> bool:
        """Check if two filter actions are similar enough to consolidate."""
        # Simple comparison - could be made more sophisticated
        return json.dumps(action1, sort_keys=True) == json.dumps(action2, sort_keys=True)

    def _suggest_simplifications(self, filter_data: Dict[str, Any]) -> List[str]:
        """Suggest simplifications for a complex filter."""
        suggestions = []
        criteria = filter_data.get('criteria', {})

        if 'query' in criteria and len(criteria['query']) > 100:
            suggestions.append("Break down complex query into multiple simpler filters")

        if len(criteria) > 3:
            suggestions.append("Split into multiple filters with fewer criteria each")

        action = filter_data.get('action', {})
        if len(action.get('addLabelIds', [])) > 2:
            suggestions.append("Reduce number of labels being added")

        return suggestions

    def track_filter_usage(self, filter_id: str, email_message_id: str,
                          criteria_matched: str = None, action_applied: str = None):
        """Track that a filter was used on a specific email."""
        query = """
        INSERT INTO filter_usage (filter_id, email_message_id, criteria_matched, action_applied)
        VALUES (?, ?, ?, ?)
        """

        self.db_manager.execute_query(
            query,
            (filter_id, email_message_id, criteria_matched, action_applied)
        )

    def bulk_track_filter_usage(self, usage_data: List[tuple]):
        """Track filter usage for multiple emails in bulk."""
        query = """
        INSERT INTO filter_usage (filter_id, email_message_id, criteria_matched, action_applied)
        VALUES (?, ?, ?, ?)
        """

        # Pad tuples to 4 elements if needed
        padded_data = []
        for item in usage_data:
            if len(item) == 2:
                padded_data.append(item + (None, None))
            elif len(item) == 3:
                padded_data.append(item + (None,))
            else:
                padded_data.append(item)

        self.db_manager.executemany(query, padded_data)

    def get_filter_usage_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get usage statistics for all filters."""
        cutoff_date = datetime.now() - timedelta(days=days)

        query = """
        SELECT
            fp.filter_id,
            COALESCE(usage_stats.usage_count, 0) as usage_count,
            usage_stats.last_used
        FROM filter_performance fp
        LEFT JOIN (
            SELECT
                filter_id,
                COUNT(*) as usage_count,
                MAX(matched_at) as last_used
            FROM filter_usage
            WHERE matched_at >= ?
            GROUP BY filter_id
        ) usage_stats ON fp.filter_id = usage_stats.filter_id
        ORDER BY usage_count DESC
        """

        results = self.db_manager.fetch_all(query, (cutoff_date,))

        stats = []
        for row in results:
            stats.append({
                'filter_id': row[0],
                'usage_count': row[1],
                'last_used': row[2]
            })

        return stats

    def identify_unused_filters(self, all_filters: List[Dict[str, Any]], days: int = 30) -> List[Dict[str, Any]]:
        """Identify filters that haven't been used recently."""
        usage_stats = self.get_filter_usage_stats(days)
        used_filter_ids = {stat['filter_id'] for stat in usage_stats if stat['usage_count'] > 0}

        all_filter_ids = {f.get('id') for f in all_filters}
        unused_filter_ids = all_filter_ids - used_filter_ids

        unused_filters = [f for f in all_filters if f.get('id') in unused_filter_ids]

        return unused_filters

    def get_filter_effectiveness_metrics(self) -> List[Dict[str, Any]]:
        """Calculate effectiveness metrics for all filters."""
        query = """
        SELECT
            filter_id,
            total_emails_processed,
            total_matches,
            effectiveness_ratio
        FROM filter_performance
        ORDER BY effectiveness_ratio DESC
        """

        results = self.db_manager.fetch_all(query)

        metrics = []
        for row in results:
            metrics.append({
                'filter_id': row[0],
                'emails_processed': row[1],
                'matches': row[2],
                'effectiveness_ratio': row[3]
            })

        return metrics

    def measure_filter_performance(self, filter_data: Dict[str, Any],
                                 sample_emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Measure filter performance against a sample of emails."""
        start_time = time.time()
        matches_found = 0

        criteria = filter_data.get('criteria', {})

        for email in sample_emails:
            if self._email_matches_criteria(email, criteria):
                matches_found += 1

        execution_time_ms = (time.time() - start_time) * 1000

        return {
            'filter_id': filter_data.get('id', 'unknown'),
            'execution_time_ms': execution_time_ms,
            'matches_found': matches_found,
            'emails_tested': len(sample_emails),
            'match_rate': matches_found / len(sample_emails) if sample_emails else 0
        }

    def _email_matches_criteria(self, email: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """Check if an email matches filter criteria."""
        for field, pattern in criteria.items():
            if field == 'from':
                sender = email.get('sender_email', '')
                if not self._matches_pattern(sender, pattern):
                    return False
            elif field == 'to':
                # This would need actual 'to' field in email data
                continue
            elif field == 'subject':
                subject = email.get('subject', '')
                if not self._matches_pattern(subject, pattern):
                    return False
            elif field == 'query':
                # Simplified query matching - would need more sophisticated parsing
                if not self._matches_query(email, pattern):
                    return False

        return True

    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Check if text matches a pattern (supports wildcards and regex)."""
        if '*' in pattern:
            # Convert wildcard to regex
            regex_pattern = pattern.replace('*', '.*')
            return re.search(regex_pattern, text, re.IGNORECASE) is not None
        else:
            # Exact match or regex
            try:
                return re.search(pattern, text, re.IGNORECASE) is not None
            except:
                return pattern.lower() in text.lower()

    def _matches_query(self, email: Dict[str, Any], query: str) -> bool:
        """Simplified query matching."""
        # This is a very basic implementation
        # Real Gmail query parsing would be much more complex
        query_lower = query.lower()

        if 'from:' in query_lower:
            # Extract from: pattern
            from_match = re.search(r'from:([^\s]+)', query_lower)
            if from_match:
                from_pattern = from_match.group(1)
                sender = email.get('sender_email', '')
                if not self._matches_pattern(sender, from_pattern):
                    return False

        return True

    def generate_efficiency_report(self, filters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive efficiency report for all filters."""
        # Analyze complexity for all filters
        complexity_analysis = [self.analyze_filter_complexity(f) for f in filters]

        # Get usage statistics
        usage_stats = self.get_filter_usage_stats()

        # Identify optimizations
        optimizations = self.suggest_filter_optimizations(filters)

        # Identify unused filters
        unused_filters = self.identify_unused_filters(filters)

        # Generate summary statistics
        total_filters = len(filters)
        complex_filters = len([c for c in complexity_analysis if c['complexity_level'] == 'complex'])
        unused_count = len(unused_filters)
        optimization_count = len(optimizations)

        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_filters': total_filters,
                'complex_filters': complex_filters,
                'unused_filters': unused_count,
                'optimization_opportunities': optimization_count,
                'average_complexity': sum(c['complexity_score'] for c in complexity_analysis) / total_filters if total_filters > 0 else 0
            },
            'complexity_analysis': complexity_analysis,
            'usage_statistics': usage_stats,
            'optimizations': optimizations,
            'unused_filters': [{'id': f.get('id'), 'criteria': f.get('criteria')} for f in unused_filters]
        }