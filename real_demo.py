#!/usr/bin/env python3
"""
Real Gmail inbox cleaner demo with actual Gmail API integration.

This script uses real Gmail API credentials to:
1. Authenticate with your Gmail account
2. Extract email metadata (privacy-protected)
3. Store in local SQLite database
4. Show statistics and analysis

Setup required:
1. Copy config.yaml.example to config.yaml
2. Add your Gmail API credentials from Google Cloud Console
3. Run this script

Usage:
    python real_demo.py --auth         # Set up authentication
    python real_demo.py --extract 10   # Extract 10 recent emails
    python real_demo.py --stats        # Show analysis
"""

import argparse
import sys
import yaml
from pathlib import Path
from googleapiclient.discovery import build

from inbox_cleaner.auth import GmailAuthenticator, AuthenticationError
from inbox_cleaner.extractor import GmailExtractor, ExtractionError
from inbox_cleaner.database import DatabaseManager


def load_config():
    """Load configuration from config.yaml."""
    config_path = Path("config.yaml")
    
    if not config_path.exists():
        print("❌ Configuration file not found!")
        print("📝 Please:")
        print("   1. Copy config.yaml.example to config.yaml")
        print("   2. Add your Gmail API credentials")
        print("   3. Run this script again")
        return None
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None


def setup_gmail_service(config):
    """Set up authenticated Gmail service."""
    print("🔐 Setting up Gmail authentication...")
    
    # Create authenticator
    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'],
        'scopes': config['gmail']['scopes']
    })
    
    try:
        # Get valid credentials (will prompt for OAuth if needed)
        print("🔄 Getting valid credentials...")
        credentials = authenticator.get_valid_credentials()
        print("✅ Authentication successful!")
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        
        # Test Gmail API access with a simple call
        try:
            profile = service.users().getProfile(userId='me').execute()
            print(f"📧 Connected to Gmail: {profile.get('emailAddress')}")
            print(f"📊 Total messages in account: {profile.get('messagesTotal', 'Unknown')}")
            return service
        except Exception as api_error:
            print(f"❌ Gmail API access failed: {api_error}")
            print()
            print("🔧 TROUBLESHOOTING HINTS:")
            
            if "Gmail API has not been used" in str(api_error) or "disabled" in str(api_error):
                print("   🚨 MOST LIKELY ISSUE: Gmail API not enabled in Google Cloud Console")
                print("   📋 SOLUTION:")
                print("      1. Go to: https://console.cloud.google.com/")
                print("      2. Select your project")
                print("      3. Navigate to: APIs & Services → Library")
                print("      4. Search for 'Gmail API' and click it")
                print("      5. Click the blue 'ENABLE' button")
                print("      6. Wait 2-3 minutes and try again")
                print()
                print("   📖 See README.md 'Common Setup Issues' section for detailed help")
                
            elif "403" in str(api_error):
                print("   🔑 POSSIBLE ISSUES:")
                print("      • Gmail API not enabled (most common)")
                print("      • Wrong OAuth scope permissions")
                print("      • Account access restrictions")
                print()
                print("   🛠️ TRY:")
                print("      python direct_test.py  # For detailed diagnosis")
                
            else:
                print("   🔍 GENERAL DEBUGGING:")
                print("      • Check your internet connection")
                print("      • Verify you're using the correct Google account")
                print("      • Try running: python direct_test.py")
                print("      • Check README.md troubleshooting section")
            
            return None
        
    except AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print()
        print("🔧 TROUBLESHOOTING HINTS:")
        
        if "invalid_client" in str(e).lower():
            print("   🔑 OAuth Client Issue:")
            print("      • Check your Client ID ends with '.apps.googleusercontent.com'")
            print("      • Check your Client Secret starts with 'GOCSPX-'")
            print("      • Ensure you selected 'Desktop application' not 'Web application'")
            print("      • Verify you're using the same Google account for GCP and Gmail")
            
        elif "access_denied" in str(e).lower():
            print("   🚫 Access Denied:")
            print("      • Make sure you added your email as a test user in OAuth consent screen")
            print("      • Check if you clicked 'Allow' during the OAuth flow")
            print("      • Try: python setup_credentials.py (to reconfigure)")
            
        else:
            print("   🔍 General Authentication Issues:")
            print("      • Delete config.yaml and run setup_credentials.py again")
            print("      • Check Google Cloud Console OAuth consent screen setup")
            print("      • Ensure Gmail account has emails to access")
            
        print("   📖 See README.md 'Common Setup Issues' section for detailed solutions")
        return None


def extract_emails(service, db_manager, num_emails=10):
    """Extract emails from Gmail and store in database."""
    print(f"📧 Extracting {num_emails} emails from Gmail...")
    
    try:
        # Create extractor
        extractor = GmailExtractor(service, batch_size=100)
        
        # Track progress
        def progress_callback(current, total):
            percentage = (current / total) * 100 if total > 0 else 0
            print(f"⏳ Progress: {current}/{total} emails ({percentage:.1f}%)")
        
        # Extract emails with progress tracking
        print("🔄 Starting extraction...")
        emails = extractor.extract_all(
            query="in:inbox",  # Get inbox emails (more reliable than empty query)
            max_results=num_emails,
            progress_callback=progress_callback
        )
        
        if not emails:
            print("❌ No emails found")
            print()
            print("🔧 TROUBLESHOOTING HINTS:")
            print("   🔍 POSSIBLE CAUSES:")
            print("      • Gmail API not properly enabled (most common)")
            print("      • Wrong Gmail query (try different search terms)")
            print("      • Empty Gmail account or no emails in inbox")
            print("      • API rate limits or temporary issues")
            print()
            print("   🛠️ DEBUGGING STEPS:")
            print("      1. Run: python direct_test.py")
            print("         (This will show exactly what the API can see)")
            print("      2. Check Gmail web interface - do you have emails?")
            print("      3. Try: python smart_demo.py --extract 10")
            print("         (This tries different queries automatically)")
            print("      4. Wait 2-3 minutes if you just enabled Gmail API")
            print()
            print("   📖 See README.md 'Common Setup Issues' for detailed solutions")
            return False
        
        print(f"📥 Extracted {len(emails)} emails")
        print("💾 Storing in database...")
        
        # Store in database
        inserted = db_manager.insert_batch(emails)
        print(f"✅ Stored {inserted} emails in database")
        
        # Show sample of what was extracted (privacy-safe)
        print("\n📋 Sample of extracted data:")
        for i, email in enumerate(emails[:3]):
            print(f"   {i+1}. Domain: {email.sender_domain}")
            print(f"      Subject: {email.subject[:50]}...")
            print(f"      Date: {email.date_received.strftime('%Y-%m-%d %H:%M')}")
            print(f"      Labels: {', '.join(email.labels[:3])}")
            print()
        
        return True
        
    except ExtractionError as e:
        print(f"❌ Email extraction failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def show_statistics(db_manager):
    """Show database statistics and analysis."""
    print("📊 Email Analysis Results")
    print("=" * 40)
    
    # Basic statistics
    stats = db_manager.get_statistics()
    print(f"📧 Total emails analyzed: {stats['total_emails']}")
    
    if stats['total_emails'] == 0:
        print("💡 No emails in database. Run --extract first!")
        return
    
    # Category breakdown
    if stats['categories']:
        print("\n🏷️ Email Categories:")
        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
            print(f"   {category}: {count}")
    
    # Top labels
    if stats['labels']:
        print("\n📨 Top Labels:")
        top_labels = sorted(stats['labels'].items(), key=lambda x: x[1], reverse=True)[:10]
        for label, count in top_labels:
            print(f"   {label}: {count}")
    
    # Domain analysis
    print("\n🌐 Top Email Domains:")
    domain_stats = db_manager.get_domain_statistics()
    top_domains = list(domain_stats.items())[:10]
    for domain, count in top_domains:
        print(f"   {domain}: {count} emails")
    
    # Cleanup suggestions
    print("\n💡 Cleanup Suggestions:")
    promotional_count = stats['labels'].get('CATEGORY_PROMOTIONS', 0)
    if promotional_count > 0:
        print(f"   📢 {promotional_count} promotional emails could be archived")
    
    social_count = stats['labels'].get('CATEGORY_SOCIAL', 0)
    if social_count > 0:
        print(f"   👥 {social_count} social emails could be organized")
    
    # Show domains with many emails (potential newsletter cleanup)
    newsletter_domains = [(d, c) for d, c in domain_stats.items() if c > 5]
    if newsletter_domains:
        print(f"   📰 {len(newsletter_domains)} domains with 5+ emails (potential newsletters)")


def main():
    """Main application function."""
    parser = argparse.ArgumentParser(
        description="Gmail Inbox Cleaner - Real Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--auth', action='store_true', help='Test authentication only')
    parser.add_argument('--extract', type=int, metavar='N', help='Extract N emails')
    parser.add_argument('--stats', action='store_true', help='Show email statistics')
    
    args = parser.parse_args()
    
    if not any([args.auth, args.extract, args.stats]):
        parser.print_help()
        return
    
    print("🎯 Gmail Inbox Cleaner - Real Demo")
    print("=" * 40)
    
    # Load configuration
    config = load_config()
    if not config:
        sys.exit(1)
    
    # Set up database
    db_path = config['database']['path']
    print(f"💾 Database: {db_path}")
    db_manager = DatabaseManager(db_path)
    
    if args.stats:
        show_statistics(db_manager)
        return
    
    # Set up Gmail service (needed for auth and extract)
    service = setup_gmail_service(config)
    if not service:
        sys.exit(1)
    
    if args.auth:
        print("✅ Authentication test completed successfully!")
        print("🔑 Your credentials are now saved securely")
        return
    
    if args.extract:
        success = extract_emails(service, db_manager, args.extract)
        if success:
            print("\n🎉 Extraction completed successfully!")
            print("💡 Run --stats to see analysis")
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()