#!/usr/bin/env python3
"""
Unsubscribe and block spam domains tool.

This script will:
1. Find unsubscribe links in emails from spam domains
2. Create Gmail filters to automatically delete future emails
3. Delete existing emails from those domains
4. Show you unsubscribe links so you can manually unsubscribe

Usage:
    python unsubscribe_and_block.py --dry-run                    # Preview actions
    python unsubscribe_and_block.py --execute                    # Create filters and delete
    python unsubscribe_and_block.py --domain trulieve.com        # Process specific domain
    python unsubscribe_and_block.py --list-filters               # Show existing filters
"""

import argparse
import sys
import yaml
from pathlib import Path
from googleapiclient.discovery import build

from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.database import DatabaseManager
from inbox_cleaner.unsubscribe_engine import UnsubscribeEngine


# Malicious spam/phishing domains to delete
SPAM_DOMAINS = {
    'jazzyue.com': {'count': 1, 'type': 'Fake bonus scam with Unicode manipulation'},
    'gpelectricos.com': {'count': 1, 'type': 'Jackpot prize scam'},
    'planetbrandy.com': {'count': 1, 'type': 'Uses user name in fake bonus scam'},
    'mathewyoga.com': {'count': 1, 'type': 'Jackpot winner scam'}
}


def load_config():
    """Load configuration."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found. Run setup_credentials.py first.")
        return None

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def print_unsubscribe_links(unsubscribe_info: list):
    """Print found unsubscribe links in a user-friendly format."""
    if not unsubscribe_info:
        print("   ❌ No unsubscribe links found")
        return

    print(f"\n📧 Found unsubscribe links:")
    for info in unsubscribe_info:
        print(f"\n   Email: {info['subject']}")
        print(f"   Links found:")
        for i, link in enumerate(info['unsubscribe_links'][:3], 1):  # Show first 3
            if link.startswith('mailto:'):
                print(f"      {i}. 📧 {link}")
            else:
                print(f"      {i}. 🔗 {link}")


def main():
    """Main unsubscribe and block function."""
    parser = argparse.ArgumentParser(
        description="Unsubscribe and block spam domains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Malicious Spam/Phishing Domains to Delete:
  • jazzyue.com - Fake bonus scam with Unicode manipulation
  • gpelectricos.com - Jackpot prize scam  
  • planetbrandy.com - Uses user name in fake bonus scam
  • mathewyoga.com - Jackpot winner scam

This tool will:
  1. Create Gmail filters to auto-delete future emails
  2. Delete existing emails from these malicious domains
  3. Block future phishing/scam attempts

Examples:
  python unsubscribe_and_block.py --dry-run
  python unsubscribe_and_block.py --execute
  python unsubscribe_and_block.py --domain jazzyue.com --dry-run
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Preview actions without making changes (SAFE)'
    )

    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually create filters and delete emails'
    )

    parser.add_argument(
        '--domain',
        type=str,
        choices=list(SPAM_DOMAINS.keys()),
        help='Process specific spam domain'
    )

    parser.add_argument(
        '--all-domains',
        action='store_true',
        help='Process all spam domains'
    )

    parser.add_argument(
        '--list-filters',
        action='store_true',
        help='List existing Gmail filters'
    )

    parser.add_argument(
        '--find-unsubscribe-only',
        action='store_true',
        help='Only find unsubscribe links (no filters or deletion)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts (use with caution)'
    )

    args = parser.parse_args()

    print("🚫 Gmail Unsubscribe and Block Tool")
    print("=" * 50)

    # Load config and setup services
    config = load_config()
    if not config:
        sys.exit(1)

    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'],
        'scopes': config['gmail']['scopes']
    })

    credentials = authenticator.get_valid_credentials()
    service = build('gmail', 'v1', credentials=credentials)

    db_path = config['database']['path']
    db_manager = DatabaseManager(db_path)

    unsubscribe_engine = UnsubscribeEngine(service, db_manager)

    print("✅ Connected to Gmail")

    # Handle list filters
    if args.list_filters:
        print("\n📋 Existing Gmail Filters:")
        filters = unsubscribe_engine.list_existing_filters()

        if not filters:
            print("   No filters found")
        else:
            for i, f in enumerate(filters, 1):
                criteria = f.get('criteria', {})
                actions = f.get('action', {})

                print(f"\n   Filter {i} (ID: {f.get('id', 'unknown')[:10]}...):")
                if 'from' in criteria:
                    print(f"      From: {criteria['from']}")
                if 'addLabelIds' in actions:
                    labels = actions['addLabelIds']
                    if 'TRASH' in labels:
                        print(f"      Action: Auto-delete")
                    else:
                        print(f"      Action: Add labels {labels}")
        return

    # Determine which domains to process
    domains_to_process = []

    if args.domain:
        domains_to_process = [args.domain]
    elif args.all_domains:
        domains_to_process = list(SPAM_DOMAINS.keys())
    else:
        # Default: show help and recommendations
        print("\n🎯 MALICIOUS DOMAIN ANALYSIS:")
        total_emails = 0
        for domain, info in SPAM_DOMAINS.items():
            print(f"   • {domain:30} {info['count']:3} emails - {info['type']}")
            total_emails += info['count']

        print(f"\n📊 Total malicious emails: {total_emails}")
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   1. Preview deletion process: --all-domains --dry-run")
        print(f"   2. Delete all malicious emails: --all-domains --execute")
        print(f"   3. Process one domain: --domain jazzyue.com --dry-run")
        print(f"   4. Force execution (no prompts): --all-domains --execute --force")
        return

    dry_run = not args.execute

    if dry_run:
        print("\n💡 DRY RUN MODE - No changes will be made")

    # Process domains
    for domain in domains_to_process:
        info = SPAM_DOMAINS[domain]
        print(f"\n" + "="*60)
        print(f"🎯 Processing: {domain}")
        print(f"📊 Expected emails: {info['count']}")
        print(f"🏷️  Type: {info['type']}")

        if args.find_unsubscribe_only:
            # Skip unsubscribe for malicious domains - just note them
            print("\n⚠️  MALICIOUS DOMAIN - DO NOT UNSUBSCRIBE")
            print("   Unsubscribing from malicious domains confirms your email is active")
            print("   and may result in more spam. These emails will be deleted instead.")
            continue

        # Full process: unsubscribe + filter + delete
        if not dry_run and not args.force:
            response = input(f"\n⚠️  Delete malicious emails from {domain}? This will:\n"
                           f"   • Create Gmail filter to auto-delete future emails\n"
                           f"   • Delete existing ~{info['count']} malicious emails\n"
                           f"   • Protect you from future phishing attempts\n"
                           f"   Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Skipped")
                continue

        # Execute full workflow
        results = unsubscribe_engine.unsubscribe_and_block_domain(domain, dry_run=dry_run)

        # Display results
        print(f"\n📋 Results for {domain}:")

        for step in results['steps']:
            step_name = step['step'].replace('_', ' ').title()

            if step['success']:
                print(f"   ✅ {step_name}: Success")

                if step['step'] == 'find_unsubscribe' and 'unsubscribe_links' in step:
                    print(f"      Found links:")
                    for link in step['unsubscribe_links']:
                        if link.startswith('mailto:'):
                            print(f"         📧 {link}")
                        else:
                            print(f"         🔗 {link}")

                elif step['step'] == 'create_filter':
                    if dry_run:
                        print(f"      Would create filter to auto-delete emails from {domain}")
                    else:
                        filter_id = step['result'].get('filter_id', 'unknown')
                        print(f"      Filter created (ID: {filter_id[:10]}...)")

                elif step['step'] == 'delete_existing':
                    result = step['result']
                    found = result.get('found_count', 0)
                    deleted = result.get('deleted_count', 0)

                    if dry_run:
                        print(f"      Would delete {found} existing emails")
                    else:
                        print(f"      Deleted {deleted} of {found} emails")
            else:
                print(f"   ❌ {step_name}: Failed")
                if 'message' in step:
                    print(f"      {step['message']}")

    print(f"\n🎉 Processing complete!")

    if not args.find_unsubscribe_only:
        print(f"\n🛡️ MALICIOUS DOMAIN PROTECTION:")
        print(f"Gmail filters have been {'created' if not dry_run else 'previewed'} to automatically")
        print(f"delete future emails from these malicious domains.")
        print(f"\n⚠️  SECURITY NOTE:")
        print(f"Do NOT unsubscribe from malicious domains as this confirms your email")
        print(f"is active and may result in more phishing attempts.")

    if dry_run:
        print(f"\n💡 To execute these actions, run with --execute")


if __name__ == '__main__':
    main()