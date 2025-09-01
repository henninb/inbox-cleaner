#!/usr/bin/env python3
"""
Programmatic email cleanup tool.

This script can automatically delete spam emails, archive old promotions,
and clean up your inbox based on analysis of your extracted email data.

Usage:
    python cleanup_emails.py --dry-run                    # Preview actions
    python cleanup_emails.py --execute                    # Actually perform cleanup  
    python cleanup_emails.py --delete-domain trulieve.com # Delete specific domain
    python cleanup_emails.py --archive-old-promos         # Archive old promotions
"""

import argparse
import sys
import yaml
from pathlib import Path
from googleapiclient.discovery import build

from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.database import DatabaseManager  
from inbox_cleaner.cleanup_engine import EmailCleanupEngine


def load_config():
    """Load configuration."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found. Run setup_credentials.py first.")
        return None
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def setup_services(config):
    """Set up Gmail and database services."""
    # Set up Gmail service
    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'],
        'scopes': config['gmail']['scopes']
    })
    
    credentials = authenticator.get_valid_credentials()
    service = build('gmail', 'v1', credentials=credentials)
    
    # Set up database
    db_path = config['database']['path']
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("💡 Extract emails first: python real_demo.py --extract 1000")
        return None, None
    
    db_manager = DatabaseManager(db_path)
    
    return service, db_manager


def main():
    """Main cleanup function."""
    parser = argparse.ArgumentParser(
        description="Programmatic Gmail cleanup tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python cleanup_emails.py --dry-run
        Preview all recommended cleanup actions

    python cleanup_emails.py --execute  
        Execute all recommended cleanup actions
        
    python cleanup_emails.py --delete-domain trulieve.com --dry-run
        Preview deleting all emails from trulieve.com
        
    python cleanup_emails.py --delete-domain trulieve.com
        Actually delete all emails from trulieve.com
        
    python cleanup_emails.py --archive-old-promos
        Archive promotional emails older than 6 months

Safety Notes:
    • Always run with --dry-run first to preview actions
    • Deleted emails cannot be recovered easily
    • Archived emails are moved out of inbox but kept in Gmail
    • The tool respects Gmail API rate limits
        """
    )
    
    # Action modes
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Preview actions without making changes (RECOMMENDED FIRST)'
    )
    
    parser.add_argument(
        '--execute',
        action='store_true', 
        help='Execute recommended cleanup actions'
    )
    
    # Specific actions
    parser.add_argument(
        '--delete-domain',
        type=str,
        help='Delete all emails from specific domain'
    )
    
    parser.add_argument(
        '--archive-old-promos',
        action='store_true',
        help='Archive promotional emails older than 6 months'
    )
    
    parser.add_argument(
        '--archive-old-social', 
        action='store_true',
        help='Archive social media emails older than 3 months'
    )
    
    # Safety options
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts (use with caution)'
    )
    
    args = parser.parse_args()
    
    # Default to dry-run if no action specified
    if not any([args.dry_run, args.execute, args.delete_domain, 
                args.archive_old_promos, args.archive_old_social]):
        args.dry_run = True
    
    print("🧹 Gmail Programmatic Cleanup Tool")
    print("=" * 50)
    
    # Load config and set up services
    config = load_config()
    if not config:
        sys.exit(1)
    
    service, db_manager = setup_services(config)
    if not service or not db_manager:
        sys.exit(1)
    
    # Initialize cleanup engine
    cleanup_engine = EmailCleanupEngine(service, db_manager)
    
    print("✅ Connected to Gmail and database")
    
    # Handle specific actions
    if args.delete_domain:
        print(f"\n🎯 Domain Deletion: {args.delete_domain}")
        
        if not args.dry_run and not args.force:
            response = input(f"⚠️  DELETE all emails from {args.delete_domain}? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                sys.exit(0)
        
        result = cleanup_engine.delete_emails_by_domain(
            args.delete_domain, 
            dry_run=args.dry_run
        )
        
        print(f"\n📊 Result: {result}")
        return
    
    if args.archive_old_promos:
        print("\n🎯 Archiving old promotional emails...")
        
        if not args.dry_run and not args.force:
            response = input("⚠️  Archive promotional emails older than 6 months? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                sys.exit(0)
        
        result = cleanup_engine.archive_emails_by_criteria(
            "category:promotions older_than:6m",
            dry_run=args.dry_run
        )
        
        print(f"\n📊 Result: {result}")
        return
    
    if args.archive_old_social:
        print("\n🎯 Archiving old social media emails...")
        
        if not args.dry_run and not args.force:
            response = input("⚠️  Archive social emails older than 3 months? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Cancelled")
                sys.exit(0)
        
        result = cleanup_engine.archive_emails_by_criteria(
            "category:social older_than:3m",
            dry_run=args.dry_run
        )
        
        print(f"\n📊 Result: {result}")
        return
    
    # Generate and execute comprehensive cleanup plan
    print("\n🔍 Analyzing your emails for cleanup opportunities...")
    recommendations = cleanup_engine.bulk_cleanup_recommendations()
    
    if not recommendations:
        print("✅ No cleanup recommendations - your inbox looks clean!")
        return
    
    print(f"\n📋 Found {len(recommendations)} cleanup recommendations:")
    
    total_estimated = 0
    for i, rec in enumerate(recommendations, 1):
        confidence = rec.get('confidence', 'medium').upper()
        
        if rec['action'] == 'delete_domain':
            print(f"   {i}. 🗑️  DELETE {rec['email_count']} emails from {rec['domain']}")
            print(f"      Reason: {rec['reason']} [{confidence} CONFIDENCE]")
            total_estimated += rec['email_count']
            
        elif 'archive' in rec['action']:
            print(f"   {i}. 📦 ARCHIVE ~{rec['estimated_count']} emails")
            print(f"      Criteria: {rec['criteria']} [{confidence} CONFIDENCE]")
            total_estimated += rec['estimated_count']
    
    print(f"\n📈 Estimated cleanup: ~{total_estimated} emails")
    
    if args.dry_run:
        print("\n💡 This is a DRY RUN - no emails will be modified")
        print("💡 Add --execute to perform actual cleanup")
    
    if args.execute and not args.force:
        print(f"\n⚠️  WARNING: This will modify ~{total_estimated} emails in your Gmail!")
        print("⚠️  Deleted emails cannot be easily recovered!")
        response = input("\nProceed with cleanup? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("❌ Cancelled")
            sys.exit(0)
    
    # Execute cleanup plan
    print(f"\n🚀 {'EXECUTING' if args.execute else 'SIMULATING'} cleanup plan...")
    
    results = cleanup_engine.execute_cleanup_plan(
        recommendations, 
        dry_run=args.dry_run
    )
    
    # Generate and display report
    report = cleanup_engine.generate_cleanup_report(results)
    print(f"\n{report}")
    
    if args.dry_run:
        print("\n💡 To execute these actions, run:")
        print("   python cleanup_emails.py --execute")
    else:
        print("\n🎉 Cleanup completed! Your inbox should be much cleaner now.")
        print("💡 Run 'python real_demo.py --stats' to see updated statistics")


if __name__ == '__main__':
    main()