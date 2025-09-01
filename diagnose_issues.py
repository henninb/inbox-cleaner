#!/usr/bin/env python3
"""
Comprehensive diagnostic tool for Gmail Inbox Cleaner issues.

Run this when you encounter problems to get detailed troubleshooting information.
"""

import yaml
import sys
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from inbox_cleaner.auth import GmailAuthenticator, AuthenticationError


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "="*50)
    print(f"🔍 {title}")
    print("="*50)


def diagnose_config():
    """Check configuration file."""
    print_header("Configuration Check")
    
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found!")
        print("💡 Run: python setup_credentials.py")
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        print("✅ config.yaml found and readable")
        
        # Check required fields
        gmail_config = config.get('gmail', {})
        client_id = gmail_config.get('client_id', '')
        client_secret = gmail_config.get('client_secret', '')
        
        if not client_id:
            print("❌ client_id missing from config")
            return None
        elif not client_id.endswith('.apps.googleusercontent.com'):
            print(f"⚠️  client_id doesn't look right: {client_id[:20]}...")
            print("   Should end with '.apps.googleusercontent.com'")
        else:
            print(f"✅ client_id looks valid: {client_id[:20]}...googleusercontent.com")
        
        if not client_secret:
            print("❌ client_secret missing from config")
            return None
        elif not client_secret.startswith('GOCSPX-'):
            print(f"⚠️  client_secret doesn't look right: {client_secret[:10]}...")
            print("   Should start with 'GOCSPX-'")
        else:
            print(f"✅ client_secret looks valid: GOCSPX-{client_secret[7:15]}...")
        
        scopes = gmail_config.get('scopes', [])
        print(f"✅ OAuth scopes: {scopes}")
        
        return config
        
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return None


def diagnose_authentication(config):
    """Test authentication."""
    print_header("Authentication Test")
    
    if not config:
        print("❌ Skipping authentication test (no valid config)")
        return None
    
    try:
        authenticator = GmailAuthenticator({
            'client_id': config['gmail']['client_id'],
            'client_secret': config['gmail']['client_secret'],
            'scopes': config['gmail']['scopes']
        })
        
        print("🔄 Testing credential loading...")
        credentials = authenticator.load_credentials()
        
        if credentials:
            print("✅ Found existing credentials")
            if credentials.valid:
                print("✅ Credentials are valid")
            elif credentials.expired:
                print("⚠️  Credentials expired, will try to refresh")
            else:
                print("❌ Credentials invalid")
        else:
            print("⚠️  No existing credentials found")
            print("   You'll need to run OAuth flow")
        
        print("🔄 Getting valid credentials...")
        valid_credentials = authenticator.get_valid_credentials()
        print("✅ Authentication successful!")
        
        return valid_credentials
        
    except AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("\n💡 TROUBLESHOOTING:")
        
        if "invalid_client" in str(e).lower():
            print("   • Check your Client ID and Client Secret")
            print("   • Make sure you selected 'Desktop application' not 'Web'")
            print("   • Verify same Google account for GCP and Gmail")
        else:
            print("   • Try: rm config.yaml && python setup_credentials.py")
            print("   • Check OAuth consent screen has your email as test user")
            
        return None
    except Exception as e:
        print(f"❌ Unexpected authentication error: {e}")
        return None


def diagnose_gmail_api(credentials):
    """Test Gmail API access."""
    print_header("Gmail API Access Test")
    
    if not credentials:
        print("❌ Skipping Gmail API test (no valid credentials)")
        return None
    
    try:
        service = build('gmail', 'v1', credentials=credentials)
        print("✅ Gmail service built successfully")
        
        # Test 1: Get profile
        print("\n🔄 Testing profile access...")
        try:
            profile = service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress')
            total_messages = profile.get('messagesTotal', 0)
            total_threads = profile.get('threadsTotal', 0)
            
            print(f"✅ Connected to Gmail: {email}")
            print(f"📊 Total messages: {total_messages}")
            print(f"🧵 Total threads: {total_threads}")
            
            if total_messages == 0:
                print("⚠️  No messages found in Gmail account")
                print("   Check if this is the correct Gmail account")
            
        except HttpError as e:
            if "Gmail API has not been used" in str(e) or "disabled" in str(e):
                print("❌ Gmail API not enabled!")
                print("\n🚨 CRITICAL ISSUE: Gmail API is disabled")
                print("📋 SOLUTION:")
                print("   1. Go to: https://console.cloud.google.com/")
                print("   2. Select your project")
                print("   3. Navigate to: APIs & Services → Library")
                print("   4. Search 'Gmail API' and click it")
                print("   5. Click the blue 'ENABLE' button")
                print("   6. Wait 2-3 minutes and try again")
                return None
            else:
                print(f"❌ Gmail API error: {e}")
                return None
        
        # Test 2: Try to get messages
        print("\n🔄 Testing message list access...")
        test_queries = [
            ("in:inbox", "Inbox messages"),
            ("", "All messages"),
            ("in:anywhere", "All messages (anywhere)"),
            ("is:unread", "Unread messages")
        ]
        
        working_query = None
        for query, description in test_queries:
            try:
                result = service.users().messages().list(
                    userId='me', 
                    q=query, 
                    maxResults=5
                ).execute()
                
                messages = result.get('messages', [])
                estimate = result.get('resultSizeEstimate', 0)
                
                print(f"   Query '{query}' ({description}): {len(messages)} messages, estimate: {estimate}")
                
                if messages and not working_query:
                    working_query = query
                    
            except Exception as e:
                print(f"   Query '{query}' failed: {e}")
        
        if working_query:
            print(f"\n✅ Found working query: '{working_query}'")
            print("🎉 Gmail API is working correctly!")
            
            # Get sample message
            result = service.users().messages().list(userId='me', q=working_query, maxResults=1).execute()
            if result.get('messages'):
                msg_id = result['messages'][0]['id']
                msg = service.users().messages().get(userId='me', id=msg_id, format='metadata').execute()
                
                headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
                print("\n📧 Sample message:")
                print(f"   From: {headers.get('From', 'Unknown')[:50]}...")
                print(f"   Subject: {headers.get('Subject', 'Unknown')[:50]}...")
                print(f"   Date: {headers.get('Date', 'Unknown')}")
        else:
            print("\n❌ No working query found!")
            print("💡 This could mean:")
            print("   • Gmail account is empty")
            print("   • API permissions issue")
            print("   • Account type incompatibility")
        
        return service
        
    except Exception as e:
        print(f"❌ Failed to build Gmail service: {e}")
        return None


def diagnose_labels(service):
    """Test label access."""
    print_header("Gmail Labels Check")
    
    if not service:
        print("❌ Skipping labels test (no Gmail service)")
        return
    
    try:
        labels_result = service.users().labels().list(userId='me').execute()
        labels = labels_result.get('labels', [])
        
        system_labels = [l['name'] for l in labels if l['type'] == 'system']
        user_labels = [l['name'] for l in labels if l['type'] == 'user']
        
        print(f"📋 Total labels: {len(labels)}")
        print(f"🔧 System labels ({len(system_labels)}): {', '.join(system_labels)}")
        
        if user_labels:
            print(f"👤 User labels ({len(user_labels)}): {', '.join(user_labels)}")
        else:
            print("👤 No custom labels found")
            
    except Exception as e:
        print(f"❌ Failed to get labels: {e}")


def main():
    """Run comprehensive diagnosis."""
    print("🎯 Gmail Inbox Cleaner - Issue Diagnosis Tool")
    print("This tool will help identify and solve common problems")
    
    # Step 1: Check configuration
    config = diagnose_config()
    
    # Step 2: Test authentication
    credentials = diagnose_authentication(config)
    
    # Step 3: Test Gmail API
    service = diagnose_gmail_api(credentials)
    
    # Step 4: Check labels
    diagnose_labels(service)
    
    # Final summary
    print_header("Summary & Next Steps")
    
    if service:
        print("🎉 DIAGNOSIS COMPLETE - Everything looks good!")
        print("💡 You should be able to extract emails successfully:")
        print("   python real_demo.py --extract 10")
    elif credentials and not service:
        print("⚠️  DIAGNOSIS: Gmail API Issue")
        print("🔧 Most likely: Gmail API not enabled")
        print("📋 Next steps: Follow the Gmail API enabling instructions above")
    elif not credentials:
        print("❌ DIAGNOSIS: Authentication Issue")
        print("🔧 Most likely: OAuth configuration problem")
        print("📋 Next steps: Fix Client ID/Secret or re-run setup")
    else:
        print("❌ DIAGNOSIS: Configuration Issue")
        print("🔧 Next steps: Run python setup_credentials.py")
    
    print("\n📖 For detailed solutions, see README.md 'Common Setup Issues' section")


if __name__ == '__main__':
    main()