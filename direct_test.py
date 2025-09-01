#!/usr/bin/env python3
"""Direct Gmail API test to see what's actually happening."""

import yaml
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator

# Authenticate
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

authenticator = GmailAuthenticator({
    'client_id': config['gmail']['client_id'],
    'client_secret': config['gmail']['client_secret'],
    'scopes': config['gmail']['scopes']
})

credentials = authenticator.get_valid_credentials()
service = build('gmail', 'v1', credentials=credentials)

print("🔍 Direct Gmail API Test")
print("=" * 30)

# Test 1: Get profile
print("1. Getting Gmail profile...")
try:
    profile = service.users().getProfile(userId='me').execute()
    print(f"   Email: {profile.get('emailAddress')}")
    print(f"   Messages Total: {profile.get('messagesTotal')}")
    print(f"   Threads Total: {profile.get('threadsTotal')}")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# Test 2: Raw API call - most permissive
print("2. Testing raw messages.list() call...")
try:
    result = service.users().messages().list(userId='me', maxResults=10).execute()
    messages = result.get('messages', [])
    estimate = result.get('resultSizeEstimate', 0)
    next_token = result.get('nextPageToken', 'None')
    
    print(f"   Messages returned: {len(messages)}")
    print(f"   Result size estimate: {estimate}")
    print(f"   Next page token: {next_token}")
    
    if messages:
        print(f"   First message ID: {messages[0]['id']}")
        print("   ✅ SUCCESS - API is working!")
    else:
        print("   ❌ No messages in response")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

# Test 3: Check if it's a threading vs messages issue
print("3. Testing threads instead of messages...")
try:
    result = service.users().threads().list(userId='me', maxResults=10).execute()
    threads = result.get('threads', [])
    print(f"   Threads found: {len(threads)}")
    if threads:
        print("   ✅ Threads API works!")
    print()
except Exception as e:
    print(f"   Error: {e}")
    print()

print("🎯 Test complete!")