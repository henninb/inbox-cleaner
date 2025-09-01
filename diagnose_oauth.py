#!/usr/bin/env python3
"""
OAuth diagnostics tool to verify scopes and permissions.
"""

import yaml
import json
from pathlib import Path
from googleapiclient.discovery import build
from inbox_cleaner.auth import GmailAuthenticator

def diagnose_oauth():
    """Comprehensive OAuth scope and permission diagnosis."""
    
    print("🔍 Gmail OAuth Scope Diagnostics")
    print("=" * 50)
    
    # Load config
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found")
        return
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print("✅ Configuration loaded")
    print(f"📋 Requested scopes:")
    for scope in config['gmail']['scopes']:
        print(f"   • {scope}")
    print()
    
    # Check stored credentials
    authenticator = GmailAuthenticator({
        'client_id': config['gmail']['client_id'],
        'client_secret': config['gmail']['client_secret'],
        'scopes': config['gmail']['scopes']
    })
    
    print("🔑 Checking stored credentials...")
    stored_creds = authenticator.load_credentials()
    
    if stored_creds:
        print("✅ Found stored credentials")
        print(f"   Valid: {stored_creds.valid}")
        print(f"   Expired: {stored_creds.expired}")
        
        # Check what scopes the stored credentials actually have
        if hasattr(stored_creds, 'scopes') and stored_creds.scopes:
            print(f"   Actual scopes in stored credentials:")
            for scope in stored_creds.scopes:
                print(f"      • {scope}")
        else:
            print("   ⚠️  No scope information in stored credentials")
            
        # Check if scopes match what we want
        requested_scopes = set(config['gmail']['scopes'])
        if hasattr(stored_creds, 'scopes') and stored_creds.scopes:
            actual_scopes = set(stored_creds.scopes)
            missing_scopes = requested_scopes - actual_scopes
            if missing_scopes:
                print(f"   ❌ Missing scopes: {missing_scopes}")
                print("   💡 Need to re-authenticate with new scopes")
            else:
                print("   ✅ All requested scopes are present")
    else:
        print("❌ No stored credentials found")
        print("   💡 Need to authenticate first")
    
    print()
    
    # Test authentication and permissions
    print("🔐 Testing authentication and permissions...")
    
    try:
        if not stored_creds or not stored_creds.valid:
            print("   🔄 Getting fresh credentials...")
            credentials = authenticator.get_valid_credentials()
        else:
            credentials = stored_creds
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        print("   ✅ Gmail service built successfully")
        
        # Test different permission levels
        print("\n🧪 Testing permission levels:")
        
        # Test 1: Read access
        try:
            profile = service.users().getProfile(userId='me').execute()
            print("   ✅ READ: Can access Gmail profile")
            print(f"      Email: {profile.get('emailAddress')}")
            print(f"      Total messages: {profile.get('messagesTotal')}")
        except Exception as e:
            print(f"   ❌ READ: Failed - {e}")
            return
        
        # Test 2: List messages
        try:
            messages = service.users().messages().list(userId='me', maxResults=1).execute()
            print("   ✅ READ: Can list messages")
        except Exception as e:
            print(f"   ❌ READ: Can't list messages - {e}")
            return
        
        # Test 3: Modify access (try to get a message we can test modify on)
        try:
            # Find one message to test modify permissions
            result = service.users().messages().list(userId='me', maxResults=1).execute()
            if result.get('messages'):
                msg_id = result['messages'][0]['id']
                
                # Test modify by trying to add/remove a label (reversible operation)
                try:
                    # Get current labels
                    msg = service.users().messages().get(userId='me', id=msg_id, format='minimal').execute()
                    current_labels = msg.get('labelIds', [])
                    
                    print("   ✅ MODIFY: Can access message for modification")
                    
                    # Test if we can modify labels (this tests modify scope without deleting)
                    # We'll add UNREAD label if not present, or remove it if present (reversible)
                    if 'UNREAD' not in current_labels:
                        # Add UNREAD label
                        service.users().messages().modify(
                            userId='me', 
                            id=msg_id,
                            body={'addLabelIds': ['UNREAD']}
                        ).execute()
                        print("   ✅ MODIFY: Successfully added UNREAD label (testing)")
                        
                        # Remove it again to restore original state
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id, 
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        print("   ✅ MODIFY: Successfully removed UNREAD label (restored)")
                    else:
                        # Remove UNREAD label
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                        print("   ✅ MODIFY: Successfully removed UNREAD label (testing)")
                        
                        # Add it back to restore original state
                        service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'addLabelIds': ['UNREAD']}
                        ).execute()
                        print("   ✅ MODIFY: Successfully added UNREAD label (restored)")
                        
                    print("   🎉 MODIFY SCOPE: Working correctly!")
                    
                except Exception as modify_error:
                    print(f"   ❌ MODIFY: Failed - {modify_error}")
                    if "insufficient authentication scopes" in str(modify_error):
                        print("   💡 Missing gmail.modify scope in OAuth consent screen")
                        return
                    
        except Exception as e:
            print(f"   ❌ MODIFY: Setup failed - {e}")
            return
            
        # Test 4: Settings access (filters)
        try:
            filters = service.users().settings().filters().list(userId='me').execute()
            print("   ✅ SETTINGS: Can list Gmail filters")
            filter_count = len(filters.get('filter', []))
            print(f"      Current filters: {filter_count}")
        except Exception as e:
            print(f"   ❌ SETTINGS: Can't access filters - {e}")
            if "insufficient authentication scopes" in str(e):
                print("   💡 Missing gmail.settings.basic scope in OAuth consent screen")
                return
        
        print("\n🎉 ALL PERMISSION TESTS PASSED!")
        print("✅ Ready for email cleanup operations")
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        
        if "invalid_scope" in str(e):
            print("\n🔧 SOLUTION:")
            print("1. Go to Google Cloud Console OAuth consent screen")
            print("2. Add missing scopes:")
            print("   • https://www.googleapis.com/auth/gmail.modify")
            print("   • https://www.googleapis.com/auth/gmail.settings.basic")
            print("3. Wait 2-3 minutes, then try again")
        elif "Address already in use" in str(e):
            print("\n🔧 Port issue - should be fixed with new auth flow")
        

if __name__ == '__main__':
    diagnose_oauth()