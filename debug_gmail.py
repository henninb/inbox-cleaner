#!/usr/bin/env python3
"""
Debug script to test Gmail API connectivity and find out why no emails are returned.
"""

import yaml
from pathlib import Path
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator


def load_config():
    """Load configuration."""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


def debug_gmail_connection():
    """Debug Gmail API connection and queries."""
    print("🔍 Gmail API Debug Tool")
    print("=" * 40)

    # Load config and authenticate
    config = load_config()
    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'],
        'scopes': config['gmail']['scopes']
    })

    credentials = authenticator.get_valid_credentials()
    service = build('gmail', 'v1', credentials=credentials)

    print("✅ Authentication successful!")
    print()

    # Test 1: Get user profile
    print("📋 Test 1: User Profile")
    try:
        profile = service.users().getProfile(userId='me').execute()
        print(f"   Email: {profile.get('emailAddress')}")
        print(f"   Total messages: {profile.get('messagesTotal', 'Unknown')}")
        print(f"   Total threads: {profile.get('threadsTotal', 'Unknown')}")
        print()
    except Exception as e:
        print(f"   ❌ Error getting profile: {e}")
        print()

    # Test 2: Try different queries
    queries_to_test = [
        ("All emails", ""),
        ("Inbox only", "in:inbox"),
        ("Unread emails", "is:unread"),
        ("Recent emails", "newer_than:7d"),
        ("Any emails", "has:userlabels OR has:nouserlabels")
    ]

    for query_name, query in queries_to_test:
        print(f"📧 Test: {query_name}")
        print(f"   Query: '{query}' (empty = all emails)")

        try:
            # Get message list
            result = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=10
            ).execute()

            messages = result.get('messages', [])
            result_size = result.get('resultSizeEstimate', 0)

            print(f"   📊 Result size estimate: {result_size}")
            print(f"   📨 Messages returned: {len(messages)}")

            if messages:
                print(f"   ✅ Found {len(messages)} messages!")
                # Get details of first message
                first_msg = service.users().messages().get(
                    userId='me',
                    id=messages[0]['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()

                headers = {}
                for header in first_msg.get('payload', {}).get('headers', []):
                    headers[header['name']] = header['value']

                print(f"   📧 Sample email:")
                print(f"      From: {headers.get('From', 'Unknown')[:50]}...")
                print(f"      Subject: {headers.get('Subject', 'Unknown')[:50]}...")
                print(f"      Date: {headers.get('Date', 'Unknown')}")
                break  # Found working query
            else:
                print(f"   ❌ No messages found")
            print()

        except Exception as e:
            print(f"   ❌ Error: {e}")
            print()

    # Test 3: Check labels
    print("🏷️  Test: Available Labels")
    try:
        labels_result = service.users().labels().list(userId='me').execute()
        labels = labels_result.get('labels', [])

        print(f"   📋 Total labels: {len(labels)}")
        system_labels = [l['name'] for l in labels if l['type'] == 'system']
        user_labels = [l['name'] for l in labels if l['type'] == 'user']

        print(f"   🔧 System labels: {', '.join(system_labels[:10])}")
        if user_labels:
            print(f"   👤 User labels: {', '.join(user_labels[:10])}")
        else:
            print("   👤 User labels: None")
        print()

    except Exception as e:
        print(f"   ❌ Error getting labels: {e}")
        print()

    print("🎯 Debug complete!")
    print()
    print("💡 If all queries returned 0 messages:")
    print("   1. Check if your Gmail account actually has emails")
    print("   2. Verify you're using the correct Google account")
    print("   3. Check Gmail web interface to confirm emails exist")


if __name__ == '__main__':
    debug_gmail_connection()