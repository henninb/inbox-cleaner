#!/usr/bin/env python3
"""
Gmail Filter Backup and Recreation System

This script will:
1. Create a backup of all current filters
2. Analyze your filters and create a clean, optimized set
3. Recreate only the essential filters automatically after manual deletion

Usage:
1. Run with --backup to save current filters
2. Delete all filters manually in Gmail
3. Run with --recreate to build clean filter set
"""

import yaml
import json
from pathlib import Path
from datetime import datetime
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator, AuthenticationError

class FilterRecreationManager:
    def __init__(self):
        self.service = None
        self.backup_file = f"gmail_filters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

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
        credentials = authenticator.get_valid_credentials()
        self.service = build('gmail', 'v1', credentials=credentials)
        print("✅ Gmail service ready")

    def backup_current_filters(self):
        """Create complete backup of current filters."""
        print("💾 Backing up current filters...")

        result = self.service.users().settings().filters().list(userId='me').execute()
        filters = result.get('filter', [])

        backup_data = {
            'backup_date': datetime.now().isoformat(),
            'total_filters': len(filters),
            'filters': filters
        }

        with open(self.backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        print(f"✅ Backed up {len(filters)} filters to: {self.backup_file}")
        return filters

    def create_essential_filters(self):
        """Create a clean set of essential filters based on your original ones."""

        essential_filters = [
            # === SPAM BLOCKING ===
            {
                'name': 'Casino/Gambling/Bonus Spam',
                'criteria': {
                    'query': 'from:(*casino* OR *CaSiNoRewaRdS* OR *bonus* OR *reward* OR *gambling*) OR subject:(casino OR bonus OR reward OR gambling OR "free money" OR jackpot)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Spam Protection'
            },

            {
                'name': 'Prize/Lottery Scams',
                'criteria': {
                    'query': 'subject:(winner OR "you won" OR "claim prize" OR lottery OR "instant millionaire" OR "congratulations" OR millionaire) OR from:(*winner* OR *lottery* OR *prize*)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Spam Protection'
            },

            {
                'name': 'Suspicious Email Patterns',
                'criteria': {
                    'query': 'to:(brianhennin88* OR brianhennin*@* OR *@outlook.com OR *@prod.outlook.com) -(to:brianhenning@gmail.com)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Spam Protection'
            },

            # === MARKETING/NEWSLETTERS ===
            {
                'name': 'DirectTV Marketing',
                'criteria': {'from': 'directv@customerinfo.directv.com'},
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Marketing'
            },

            {
                'name': 'Marketing/Success Emails',
                'criteria': {'from': 'learn@success.marketleader.com'},
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Marketing'
            },

            {
                'name': 'Cannabis Companies',
                'criteria': {
                    'query': 'from:(trulieve.com OR info.curaleaf.com)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Marketing'
            },

            {
                'name': 'Retail Marketing',
                'criteria': {
                    'query': 'from:(t.timberland.com OR harborfreight.com OR m.jabra.com OR newsletter@m.jabra.com)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Marketing'
            },

            # === SUSPICIOUS DOMAINS ===
            {
                'name': 'Known Spam Domains',
                'criteria': {
                    'query': 'from:(@jazzyue.com OR @gpelectricos.com OR @planetbrandy.com OR @mathewyoga.com OR bethel-ballet.com OR bbtransporting.com OR huntersvillelandscaping.com)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Spam Domains'
            },

            {
                'name': 'Suspicious Service Domains',
                'criteria': {
                    'query': 'from:(splitwise.com OR pigdead.com OR shared1.ccsend.com OR delivery.hondaoflisle.com OR patients.pgsurveying.com OR rachel@strideline.com)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Spam Domains'
            },

            # === ATT MAIL SCAMS ===
            {
                'name': 'ATT Mail Scams',
                'criteria': {
                    'query': 'from:(att-mail.com OR account.att-mail.com OR emailff.att-mail.com) to:brianhenning@gmail.com'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Impersonation'
            },

            # === SOCIAL/NOTIFICATION MANAGEMENT ===
            {
                'name': 'Facebook Notifications',
                'criteria': {'from': 'facebookmail.com'},
                'action': {'addLabelIds': ['TRASH']},  # or whatever you prefer
                'category': 'Social'
            },

            # === POLITICAL/ADVOCACY ===
            {
                'name': 'Political/Advocacy',
                'criteria': {
                    'query': 'from:(noreply@protectmyvote.com OR grassroots@friendsoftheuschamber.com OR camelle@oneheartland.org OR alumni@stcloudstate.edu)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Political'
            },

            # === SPECIAL HANDLING ===
            {
                'name': 'PayPal Price Match (Important)',
                'criteria': {'from': 'customerservice@paypal-pricematch.com'},
                'action': {'addLabelIds': ['IMPORTANT', 'STARRED']},
                'category': 'Important'
            },

            # === PHISHING PROTECTION ===
            {
                'name': 'Advanced Spam Patterns',
                'criteria': {
                    'query': 'from:(*.email.svi*cloud.com OR joannsoukup@comcast.net OR email.totaltools.com.au) OR to:(*@LBJBPTAMQSGFJ* OR *@Q5QZrF* OR *BRoss719* OR *xtPart_*)'
                },
                'action': {'addLabelIds': ['TRASH']},
                'category': 'Advanced Spam'
            }
        ]

        return essential_filters

    def recreate_filters(self):
        """Create the essential filter set."""
        essential_filters = self.create_essential_filters()

        print(f"\n🏗️  Creating {len(essential_filters)} essential filters...")
        print("=" * 50)

        created_count = 0
        failed_count = 0

        # Group by category for better display
        by_category = {}
        for f in essential_filters:
            category = f.get('category', 'Other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(f)

        for category, filters in by_category.items():
            print(f"\n📂 {category} ({len(filters)} filters):")

            for filter_def in filters:
                name = filter_def['name']
                criteria = filter_def['criteria']
                action = filter_def['action']

                try:
                    # Create the filter
                    filter_body = {
                        'criteria': criteria,
                        'action': action
                    }

                    result = self.service.users().settings().filters().create(
                        userId='me',
                        body=filter_body
                    ).execute()

                    filter_id = result.get('id', 'Unknown')[:8]
                    print(f"  ✅ {name} (ID: {filter_id})")
                    created_count += 1

                except Exception as e:
                    print(f"  ❌ {name}: {str(e)[:50]}...")
                    failed_count += 1

        print(f"\n📊 RECREATION SUMMARY")
        print("=" * 30)
        print(f"✅ Successfully created: {created_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"📧 Your inbox is now protected by {created_count} optimized filters")

        return created_count, failed_count

    def show_deletion_instructions(self):
        """Show instructions for manual deletion."""
        print("\n🗑️  MANUAL DELETION INSTRUCTIONS")
        print("=" * 40)
        print("1. Go to: https://mail.google.com/mail/u/0/#settings/filters")
        print("2. Select all filters (click checkbox at top)")
        print("3. Click 'Delete' button")
        print("4. Confirm deletion")
        print("5. Run this script with --recreate")
        print("\n💡 This will give you a completely clean, optimized filter set!")

def main():
    import sys

    manager = FilterRecreationManager()

    if len(sys.argv) < 2:
        print("🔧 Gmail Filter Backup & Recreation Tool")
        print("=" * 45)
        print("Usage:")
        print("  python backup_and_recreate_filters.py --backup    # Backup current filters")
        print("  python backup_and_recreate_filters.py --recreate  # Recreate essential filters")
        print("  python backup_and_recreate_filters.py --delete-instructions  # Show deletion steps")
        return

    command = sys.argv[1]

    try:
        manager.setup_gmail_service()

        if command == '--backup':
            filters = manager.backup_current_filters()
            print(f"\n💡 Next steps:")
            print(f"1. Review the backup file: {manager.backup_file}")
            print(f"2. Delete all filters manually in Gmail")
            print(f"3. Run: python {sys.argv[0]} --recreate")

        elif command == '--recreate':
            print("🏗️  Recreating optimized filter set...")
            created, failed = manager.recreate_filters()

            if created > 0:
                print(f"\n🎉 SUCCESS! Created {created} optimized filters")
                print("Your Gmail is now protected with a clean, efficient filter set!")

        elif command == '--delete-instructions':
            manager.show_deletion_instructions()

        else:
            print(f"❌ Unknown command: {command}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()