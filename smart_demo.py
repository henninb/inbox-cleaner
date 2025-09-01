#!/usr/bin/env python3
"""
Smart demo that tries different Gmail queries to find emails.
"""

import argparse
import yaml
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator
from inbox_cleaner.extractor import GmailExtractor
from inbox_cleaner.database import DatabaseManager


def find_working_query(service):
    """Find a Gmail query that actually returns emails."""
    queries_to_try = [
        ("in:inbox", "Inbox emails"),
        ("is:unread", "Unread emails"), 
        ("in:anywhere", "All emails (alternative syntax)"),
        ("", "All emails (empty query)"),
        ("has:attachment", "Emails with attachments"),
        ("from:*", "All emails with from field")
    ]
    
    print("🔍 Testing different queries to find your emails...")
    
    for query, description in queries_to_try:
        print(f"   Testing: {description} (query: '{query}')")
        try:
            result = service.users().messages().list(
                userId='me', 
                q=query, 
                maxResults=5
            ).execute()
            
            messages = result.get('messages', [])
            estimate = result.get('resultSizeEstimate', 0)
            
            if messages and estimate > 0:
                print(f"   ✅ SUCCESS! Found {estimate} emails with query: '{query}'")
                return query
            else:
                print(f"   ❌ No emails found")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("❌ Could not find any working query!")
    return None


def main():
    parser = argparse.ArgumentParser(description="Smart Gmail Demo")
    parser.add_argument('--extract', type=int, help='Extract N emails')
    args = parser.parse_args()
    
    if not args.extract:
        parser.print_help()
        return
    
    # Load config and authenticate
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'],
        'scopes': config['gmail']['scopes']
    })
    
    credentials = authenticator.get_valid_credentials()
    service = build('gmail', 'v1', credentials=credentials)
    
    # Find working query
    working_query = find_working_query(service)
    if not working_query:
        return
    
    print(f"\n📧 Using query: '{working_query}' to extract {args.extract} emails...")
    
    # Extract emails
    extractor = GmailExtractor(service, batch_size=100)
    
    def progress_callback(current, total):
        percentage = (current / total) * 100 if total > 0 else 0
        print(f"⏳ Progress: {current}/{total} emails ({percentage:.1f}%)")
    
    emails = extractor.extract_all(
        query=working_query,
        max_results=args.extract,
        progress_callback=progress_callback
    )
    
    if emails:
        print(f"📥 Extracted {len(emails)} emails!")
        
        # Store in database
        db_manager = DatabaseManager("./inbox_cleaner.db")
        inserted = db_manager.insert_batch(emails)
        print(f"💾 Stored {inserted} emails in database")
        
        # Show sample
        print("\n📋 Sample extracted data:")
        for i, email in enumerate(emails[:3]):
            print(f"   {i+1}. Domain: {email.sender_domain}")
            print(f"      Subject: {email.subject[:50]}...")
            print()
    else:
        print("❌ No emails extracted")


if __name__ == '__main__':
    main()