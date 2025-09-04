#!/usr/bin/env python3
"""
Automated Gmail Filter Cleanup Script

This script will:
1. Analyze your current filters and identify problems
2. Create new consolidated filters automatically
3. Generate precise deletion commands for manual execution
4. Provide direct browser automation commands where possible

Note: Gmail API doesn't allow filter deletion, so some steps require manual action.
"""

import yaml
import json
import webbrowser
from pathlib import Path
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator, AuthenticationError

class FilterManager:
    def __init__(self):
        self.service = None
        self.filters = []
        self.duplicates_to_delete = []
        self.filters_to_consolidate = []
        self.new_filters_to_create = []

    def setup_gmail_service(self):
        """Initialize Gmail API service."""
        config_path = Path("config.yaml")
        if not config_path.exists():
            raise Exception("config.yaml not found")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        authenticator = GmailAuthenticator(gmail_config)

        print("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            raise Exception(f"Authentication failed: {e}")

        self.service = build('gmail', 'v1', credentials=credentials)
        print("✅ Gmail service initialized")

    def fetch_current_filters(self):
        """Fetch all current Gmail filters."""
        print("📥 Fetching current filters...")
        try:
            result = self.service.users().settings().filters().list(userId='me').execute()
            self.filters = result.get('filter', [])
            print(f"📊 Found {len(self.filters)} current filters")
            return True
        except Exception as e:
            print(f"❌ Error fetching filters: {e}")
            return False

    def analyze_and_plan_cleanup(self):
        """Analyze filters and create cleanup plan."""
        print("\n🔍 Analyzing filters for cleanup opportunities...")

        # Find exact duplicates
        self._find_duplicates()

        # Plan consolidations
        self._plan_consolidations()

        # Identify dangerous filters
        self._identify_dangerous_filters()

        print(f"\n📋 Cleanup Plan Summary:")
        print(f"   Duplicates to delete: {len(self.duplicates_to_delete)}")
        print(f"   Filter groups to consolidate: {len(self.filters_to_consolidate)}")
        print(f"   New consolidated filters to create: {len(self.new_filters_to_create)}")

    def _find_duplicates(self):
        """Find exact duplicate filters."""
        seen_signatures = {}

        for f in self.filters:
            # Create signature based on criteria and action
            criteria = f.get('criteria', {})
            action = f.get('action', {})

            sig_parts = []
            if 'from' in criteria:
                sig_parts.append(f"from:{criteria['from']}")
            if 'to' in criteria:
                sig_parts.append(f"to:{criteria['to']}")
            if 'query' in criteria:
                sig_parts.append(f"query:{criteria['query']}")

            # Include action in signature
            if 'addLabelIds' in action:
                sig_parts.append(f"labels:{sorted(action['addLabelIds'])}")

            signature = "|".join(sorted(sig_parts))

            if signature in seen_signatures:
                # This is a duplicate
                self.duplicates_to_delete.append({
                    'filter': f,
                    'reason': f"Duplicate of filter {seen_signatures[signature]['id'][:8]}",
                    'original': seen_signatures[signature]
                })
            else:
                seen_signatures[signature] = f

    def _plan_consolidations(self):
        """Plan filter consolidations."""
        # Group similar filters
        casino_filters = []
        facebook_filters = []
        att_filters = []
        domain_pairs = {}  # For @domain.com vs domain.com pairs

        for f in self.filters:
            criteria = f.get('criteria', {})

            # Look for casino/bonus patterns
            if 'query' in criteria:
                query = criteria['query'].lower()
                if any(word in query for word in ['casino', 'bonus', 'reward']):
                    casino_filters.append(f)

            # Look for Facebook mail
            if 'from' in criteria and 'facebookmail.com' in criteria['from']:
                facebook_filters.append(f)

            # Look for ATT mail individual filters (not the consolidated queries)
            if ('from' in criteria and 'att-mail.com' in criteria['from'] and
                'query' not in criteria):  # Exclude already consolidated ones
                att_filters.append(f)

            # Look for domain pairs (@domain vs domain)
            if 'from' in criteria:
                from_val = criteria['from']
                if from_val.startswith('@'):
                    domain = from_val[1:]  # Remove @
                    if domain not in domain_pairs:
                        domain_pairs[domain] = []
                    domain_pairs[domain].append(('@version', f))
                else:
                    # Check if this is a bare domain
                    if '.' in from_val and '@' not in from_val:
                        if from_val not in domain_pairs:
                            domain_pairs[from_val] = []
                        domain_pairs[from_val].append(('bare', f))

        # Plan consolidations
        if len(casino_filters) > 1:
            self.filters_to_consolidate.append({
                'name': 'Casino/Bonus/Rewards',
                'filters': casino_filters,
                'new_filter': {
                    'criteria': {
                        'query': 'from:(*casino* OR *bonus* OR *reward*) OR subject:(casino OR bonus OR reward)'
                    },
                    'action': {
                        'addLabelIds': ['TRASH']
                    }
                }
            })
            self.new_filters_to_create.append('Casino/Bonus/Rewards consolidated filter')

        if len(facebook_filters) > 1:
            self.filters_to_consolidate.append({
                'name': 'Facebook Mail',
                'filters': facebook_filters,
                'new_filter': {
                    'criteria': {
                        'from': 'facebookmail.com'
                    },
                    'action': {
                        'addLabelIds': ['TRASH']  # or whatever action you prefer
                    }
                }
            })
            self.new_filters_to_create.append('Facebook Mail consolidated filter')

        # Check for domain pairs that can be consolidated
        for domain, versions in domain_pairs.items():
            if len(versions) > 1:
                # Keep the @domain version, delete bare domain
                at_version = [v for v in versions if v[0] == '@version']
                bare_version = [v for v in versions if v[0] == 'bare']

                if at_version and bare_version:
                    for _, filter_obj in bare_version:
                        self.duplicates_to_delete.append({
                            'filter': filter_obj,
                            'reason': f'Redundant with @{domain} filter',
                            'original': at_version[0][1]
                        })

    def _identify_dangerous_filters(self):
        """Identify potentially dangerous filters."""
        dangerous = []

        for f in self.filters:
            criteria = f.get('criteria', {})

            # Check for overly broad patterns
            if 'from' in criteria and criteria['from'] in ['co.uk', 'org.uk']:
                dangerous.append({
                    'filter': f,
                    'risk': 'Blocks entire UK domains',
                    'suggestion': 'DELETE - too broad'
                })

            if 'query' in criteria:
                query = criteria['query'].lower()
                if 'brianhennin' in query and 'brianhenning@gmail.com' not in query:
                    dangerous.append({
                        'filter': f,
                        'risk': 'May block legitimate emails to your name',
                        'suggestion': 'REVIEW and make more specific'
                    })

        if dangerous:
            print(f"\n⚠️  WARNING: Found {len(dangerous)} potentially dangerous filters")
            for d in dangerous:
                filter_id = d['filter']['id'][:8]
                print(f"   • Filter {filter_id}: {d['risk']}")
                print(f"     Action: {d['suggestion']}")

    def create_new_consolidated_filters(self):
        """Create new consolidated filters via Gmail API."""
        print(f"\n🔧 Creating {len(self.new_filters_to_create)} new consolidated filters...")

        for consolidation in self.filters_to_consolidate:
            name = consolidation['name']
            new_filter = consolidation['new_filter']

            try:
                print(f"Creating: {name}")
                result = self.service.users().settings().filters().create(
                    userId='me',
                    body=new_filter
                ).execute()
                print(f"✅ Created filter: {result.get('id', 'Unknown ID')[:8]}")

            except Exception as e:
                print(f"❌ Failed to create {name}: {e}")

    def generate_manual_deletion_commands(self):
        """Generate commands for manual filter deletion."""
        if not self.duplicates_to_delete:
            print("\n✅ No duplicates found to delete")
            return

        print(f"\n🗑️  MANUAL DELETION REQUIRED")
        print("=" * 50)
        print(f"Gmail API doesn't allow filter deletion. Please manually delete these {len(self.duplicates_to_delete)} filters:")
        print(f"\n🌐 Go to: https://mail.google.com/mail/u/0/#settings/filters")

        for i, dup in enumerate(self.duplicates_to_delete, 1):
            filter_obj = dup['filter']
            reason = dup['reason']
            filter_id = filter_obj['id']

            print(f"\n{i}. DELETE Filter ID: {filter_id[:15]}...")
            print(f"   Reason: {reason}")
            print(f"   Rule: {self._describe_filter(filter_obj)}")

        # Save deletion list to file for reference
        with open('filters_to_delete.json', 'w') as f:
            json.dump([{
                'id': d['filter']['id'],
                'reason': d['reason'],
                'description': self._describe_filter(d['filter'])
            } for d in self.duplicates_to_delete], f, indent=2)

        print(f"\n💾 Detailed deletion list saved to: filters_to_delete.json")

    def _describe_filter(self, filter_obj):
        """Describe a filter in human terms."""
        criteria = filter_obj.get('criteria', {})
        action = filter_obj.get('action', {})

        parts = []
        if 'from' in criteria:
            parts.append(f"From: {criteria['from']}")
        if 'to' in criteria:
            parts.append(f"To: {criteria['to']}")
        if 'query' in criteria:
            parts.append(f"Query: {criteria['query']}")

        if 'addLabelIds' in action and 'TRASH' in action['addLabelIds']:
            parts.append("→ Auto-delete")
        elif 'addLabelIds' in action:
            parts.append(f"→ Add labels {action['addLabelIds']}")

        return " | ".join(parts)

    def open_gmail_filters_page(self):
        """Open Gmail filters page in browser."""
        try:
            print("\n🌐 Opening Gmail filters page in your browser...")
            webbrowser.open("https://mail.google.com/mail/u/0/#settings/filters")
            return True
        except:
            print("❌ Could not open browser automatically")
            print("🌐 Please visit: https://mail.google.com/mail/u/0/#settings/filters")
            return False

    def execute_cleanup(self):
        """Execute the complete filter cleanup process."""
        print("🧹 Starting Automated Gmail Filter Cleanup")
        print("=" * 50)

        try:
            # Setup
            self.setup_gmail_service()

            # Fetch and analyze
            if not self.fetch_current_filters():
                return False

            self.analyze_and_plan_cleanup()

            # Create new consolidated filters first
            if self.new_filters_to_create:
                confirm = input(f"\n❓ Create {len(self.new_filters_to_create)} new consolidated filters? (y/n): ")
                if confirm.lower() == 'y':
                    self.create_new_consolidated_filters()
                else:
                    print("⏭️  Skipping filter creation")

            # Generate deletion commands
            self.generate_manual_deletion_commands()

            # Open browser for manual deletions
            if self.duplicates_to_delete:
                confirm = input(f"\n❓ Open Gmail filters page in browser for manual cleanup? (y/n): ")
                if confirm.lower() == 'y':
                    self.open_gmail_filters_page()

            print(f"\n🎉 Automated cleanup complete!")
            print(f"   New filters created: {len(self.new_filters_to_create)}")
            print(f"   Filters to manually delete: {len(self.duplicates_to_delete)}")

            return True

        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            return False

def main():
    manager = FilterManager()
    success = manager.execute_cleanup()

    if success:
        print("\n✅ Filter cleanup process completed successfully!")
    else:
        print("\n❌ Filter cleanup encountered errors")

if __name__ == "__main__":
    main()