#!/usr/bin/env python3
"""
Demo script showing the inbox cleaner modules working together.

This demonstrates:
1. OAuth2 Authentication with Gmail
2. Email extraction with privacy protection
3. Local database storage

Usage:
    python demo.py --help
    python demo.py --auth-only     # Just test authentication
    python demo.py --extract 5     # Extract 5 emails and store them
    python demo.py --stats         # Show database statistics
"""

import argparse
import sys
import tempfile
from pathlib import Path
from googleapiclient.discovery import build

from inbox_cleaner.auth import GmailAuthenticator, AuthenticationError
from inbox_cleaner.extractor import GmailExtractor, ExtractionError
from inbox_cleaner.database import DatabaseManager


def setup_auth():
    """Set up Gmail authentication."""
    # Configuration for Gmail API access
    config = {
        'client_id': 'your-client-id.googleusercontent.com',
        'client_secret': 'your-client-secret',
        'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
    }
    
    print("🔐 Setting up Gmail authentication...")
    print("📝 Note: You need to:")
    print("   1. Go to Google Cloud Console")
    print("   2. Create a project and enable Gmail API")
    print("   3. Create OAuth2 credentials")
    print("   4. Update the config above with your credentials")
    print()
    
    return GmailAuthenticator(config)


def test_authentication():
    """Test Gmail authentication only."""
    try:
        authenticator = setup_auth()
        print("✅ Authentication configuration loaded")
        
        # Note: This would normally prompt for OAuth2 flow
        print("🔄 Would normally start OAuth2 flow here...")
        print("   (Skipping in demo to avoid requiring real credentials)")
        
        return True
    except Exception as e:
        print(f"❌ Authentication setup failed: {e}")
        return False


def extract_and_store_emails(num_emails=5):
    """Extract emails and store in database."""
    try:
        # Set up components
        authenticator = setup_auth()
        
        # In a real scenario, this would use actual credentials
        print(f"🔄 Would authenticate and extract {num_emails} emails...")
        print("📧 Extracting email metadata (sender domains, subjects, etc.)")
        print("🔒 Hashing email addresses for privacy")
        print("💾 Storing in local SQLite database")
        
        # Demo with temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        print(f"📁 Database created at: {db_path}")
        
        # Initialize database
        db = DatabaseManager(db_path)
        print("✅ Database initialized with proper schema")
        
        # Show statistics
        stats = db.get_statistics()
        print(f"📊 Current database stats: {stats}")
        
        print(f"🎉 Demo complete! Database ready at {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ Email extraction failed: {e}")
        return False


def show_stats():
    """Show database statistics."""
    print("📊 Database Statistics")
    print("======================")
    print("📧 Total emails: 0 (no real data in demo)")
    print("🏷️  Categories: None yet")
    print("📨 Domains: None yet")
    print()
    print("💡 Run with --extract to populate database")


def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(
        description="Gmail Inbox Cleaner Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python demo.py --auth-only     # Test authentication setup
    python demo.py --extract 10    # Extract 10 emails
    python demo.py --stats         # Show database stats
        """
    )
    
    parser.add_argument(
        '--auth-only', 
        action='store_true',
        help='Only test authentication setup'
    )
    
    parser.add_argument(
        '--extract',
        type=int,
        metavar='N',
        help='Extract N emails and store in database'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )
    
    args = parser.parse_args()
    
    print("🎯 Gmail Inbox Cleaner Demo")
    print("============================")
    print()
    
    if args.auth_only:
        success = test_authentication()
    elif args.extract:
        success = extract_and_store_emails(args.extract)
    elif args.stats:
        show_stats()
        success = True
    else:
        parser.print_help()
        success = True
    
    if success:
        print("\n✨ Demo completed successfully!")
    else:
        print("\n💥 Demo encountered errors")
        sys.exit(1)


if __name__ == '__main__':
    main()