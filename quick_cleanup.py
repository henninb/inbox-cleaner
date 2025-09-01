#!/usr/bin/env python3
"""
Quick cleanup script for Brian's specific spam domains.

Based on analysis of 3,739 emails, this script targets the biggest offenders:
- trulieve.com (464 emails) 
- email.totaltools.com.au (426 emails)
- t.timberland.com (338 emails)  
- info.curaleaf.com (262 emails)

Total: 1,490 emails (40% of inbox!)
"""

import argparse
import sys
import yaml
from pathlib import Path
from googleapiclient.discovery import build

from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.database import DatabaseManager
from inbox_cleaner.cleanup_engine import EmailCleanupEngine


# Your specific spam domains based on analysis
SPAM_DOMAINS = {
    'trulieve.com': {'count': 464, 'type': 'Cannabis dispensary spam'},
    'email.totaltools.com.au': {'count': 426, 'type': 'Australian tool retailer spam'},
    't.timberland.com': {'count': 338, 'type': 'Clothing retailer excessive promos'},
    'info.curaleaf.com': {'count': 262, 'type': 'Cannabis company spam'}
}

# Potentially spammy domains to review
REVIEW_DOMAINS = {
    'spotify.com': {'count': 110, 'type': 'Music recommendations'},
    'm.jabra.com': {'count': 76, 'type': 'Headphone company promotions'}
}

# Keep these domains (legitimate services)
KEEP_DOMAINS = {
    'privacy.com': {'count': 275, 'type': 'Financial service'},
    'usps.com': {'count': 124, 'type': 'Package delivery notifications'},
    'email.informeddelivery.usps.com': {'count': 89, 'type': 'USPS service'},
    'hulumail.com': {'count': 84, 'type': 'Streaming service'}
}


def load_config():
    """Load configuration."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found. Run setup_credentials.py first.")
        return None
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Quick cleanup for Brian's inbox."""
    parser = argparse.ArgumentParser(
        description="Quick cleanup for Brian's spam domains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Spam Domains to Delete (1,490 emails total):
  • trulieve.com - 464 emails (Cannabis dispensary)
  • email.totaltools.com.au - 426 emails (Tool retailer)  
  • t.timberland.com - 338 emails (Clothing promos)
  • info.curaleaf.com - 262 emails (Cannabis company)

Review Domains (186 emails):
  • spotify.com - 110 emails (Music recommendations)
  • m.jabra.com - 76 emails (Headphone promos)

Keep Domains (572 emails):
  • privacy.com - 275 emails (Financial service)
  • usps.com - 124 emails (Delivery notifications)
  • email.informeddelivery.usps.com - 89 emails (USPS)
  • hulumail.com - 84 emails (Streaming service)
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true', 
        default=True,
        help='Preview actions (default, SAFE)'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually delete the spam emails'
    )
    
    parser.add_argument(
        '--delete-all-spam',
        action='store_true',
        help='Delete all 4 major spam domains'
    )
    
    parser.add_argument(
        '--delete-domain',
        type=str,
        choices=list(SPAM_DOMAINS.keys()),
        help='Delete emails from specific spam domain'
    )
    
    parser.add_argument(
        '--archive-old-promos', 
        action='store_true',
        help='Archive promotional emails older than 6 months'
    )
    
    args = parser.parse_args()
    
    print("🎯 Brian's Gmail Quick Cleanup Tool")
    print("=" * 50)
    print("📊 Targeting 1,490 spam emails (40% of your inbox)")
    print()
    
    # Load config
    config = load_config()
    if not config:
        sys.exit(1)
    
    # Set up services
    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'], 
        'scopes': config['gmail']['scopes']
    })
    
    credentials = authenticator.get_valid_credentials()
    service = build('gmail', 'v1', credentials=credentials)
    
    db_path = config['database']['path']
    db_manager = DatabaseManager(db_path)
    
    cleanup_engine = EmailCleanupEngine(service, db_manager)
    
    print("✅ Connected to Gmail")
    
    # Show domain analysis
    print("\n📋 DOMAIN ANALYSIS:")
    print("\n🚫 SPAM DOMAINS (RECOMMENDED FOR DELETION):")
    total_spam = 0
    for domain, info in SPAM_DOMAINS.items():
        print(f"   • {domain:30} {info['count']:3} emails - {info['type']}")
        total_spam += info['count']
    
    print(f"\n🔍 REVIEW DOMAINS (CHECK BEFORE DELETING):")
    for domain, info in REVIEW_DOMAINS.items():
        print(f"   • {domain:30} {info['count']:3} emails - {info['type']}")
    
    print(f"\n✅ KEEP DOMAINS (LEGITIMATE SERVICES):")
    for domain, info in KEEP_DOMAINS.items():
        print(f"   • {domain:30} {info['count']:3} emails - {info['type']}")
    
    print(f"\n📈 Total spam to delete: {total_spam} emails")
    
    # Handle specific actions
    dry_run = not args.execute
    
    if args.delete_domain:
        domain = args.delete_domain
        info = SPAM_DOMAINS[domain]
        
        print(f"\n🎯 Targeting domain: {domain}")
        print(f"📧 Expected emails: {info['count']}")
        print(f"🏷️  Type: {info['type']}")
        
        if not dry_run:
            response = input(f"\n⚠️  DELETE all emails from {domain}? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
        
        result = cleanup_engine.delete_emails_by_domain(domain, dry_run=dry_run)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
        else:
            if dry_run:
                print(f"✅ DRY RUN: Would delete {result.get('found_count', 0)} emails")
            else:
                print(f"✅ Deleted {result.get('deleted_count', 0)} emails")
        
        return
    
    if args.delete_all_spam:
        print(f"\n🎯 Deleting ALL spam domains ({total_spam} emails)")
        
        if not dry_run:
            print("\n⚠️  WARNING: This will delete emails from:")
            for domain in SPAM_DOMAINS:
                print(f"   • {domain}")
            
            response = input(f"\nDelete {total_spam} spam emails? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
        
        # Delete each spam domain
        total_deleted = 0
        for domain, info in SPAM_DOMAINS.items():
            print(f"\n📧 Processing {domain}...")
            
            result = cleanup_engine.delete_emails_by_domain(domain, dry_run=dry_run)
            
            if 'error' in result:
                print(f"   ❌ Error: {result['error']}")
            else:
                deleted = result.get('deleted_count', 0)
                found = result.get('found_count', 0)
                
                if dry_run:
                    print(f"   ✅ DRY RUN: Would delete {found} emails")
                else:
                    print(f"   ✅ Deleted {deleted} emails")
                    total_deleted += deleted
        
        if not dry_run:
            print(f"\n🎉 Total deleted: {total_deleted} emails")
            print("💡 Run 'python real_demo.py --stats' to see updated stats")
        
        return
    
    if args.archive_old_promos:
        print("\n📦 Archiving old promotional emails...")
        
        if not dry_run:
            response = input("Archive promotional emails older than 6 months? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                return
        
        result = cleanup_engine.archive_emails_by_criteria(
            "category:promotions older_than:6m",
            dry_run=dry_run
        )
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
        else:
            if dry_run:
                print(f"✅ DRY RUN: Would archive {result.get('found_count', 0)} emails")
            else:
                print(f"✅ Archived {result.get('archived_count', 0)} emails")
        
        return
    
    # Default: show summary and recommendations
    print(f"\n💡 QUICK CLEANUP RECOMMENDATIONS:")
    print(f"   1. Delete all spam: python quick_cleanup.py --delete-all-spam --dry-run")
    print(f"   2. Delete one domain: python quick_cleanup.py --delete-domain trulieve.com --dry-run")
    print(f"   3. Archive old promos: python quick_cleanup.py --archive-old-promos --dry-run")
    print(f"\n⚠️  Always run with --dry-run first, then add --execute to actually delete")
    
    print(f"\n🎯 IMPACT ESTIMATE:")
    print(f"   • Deleting spam: -{total_spam} emails (40% reduction)")
    print(f"   • Archiving old promos: -~800 emails (additional 20% reduction)")
    print(f"   • Total cleanup potential: ~2,300 emails (60% of inbox)")


if __name__ == '__main__':
    main()