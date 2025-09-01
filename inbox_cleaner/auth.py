"""OAuth2 authentication module for Gmail API access."""

import json
import keyring
from typing import Optional, Dict, Any
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials as OAuth2Credentials


class AuthenticationError(Exception):
    """Custom exception for authentication failures."""
    pass


class GmailAuthenticator:
    """Handles OAuth2 authentication for Gmail API access."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize authenticator with OAuth config."""
        if not config.get('client_id'):
            raise ValueError("client_id is required")
        if not config.get('client_secret'):
            raise ValueError("client_secret is required")
        if not config.get('scopes'):
            raise ValueError("scopes is required")
            
        self.client_id = config['client_id']
        self.client_secret = config['client_secret'] 
        self.scopes = config['scopes']
        self.redirect_uri = config.get('redirect_uri', 'http://localhost:8080/')
        
        # OAuth client config for the flow
        self.client_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uris": [self.redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://accounts.google.com/o/oauth2/token"
            }
        }
    
    def save_credentials(self, credentials: Credentials) -> None:
        """Save credentials to secure storage."""
        try:
            creds_json = credentials.to_json()
            keyring.set_password("inbox-cleaner", "gmail-token", creds_json)
        except Exception as e:
            raise AuthenticationError(f"Failed to save credentials: {e}")
    
    def load_credentials(self) -> Optional[Credentials]:
        """Load credentials from secure storage."""
        try:
            creds_json = keyring.get_password("inbox-cleaner", "gmail-token")
            if creds_json:
                creds_data = json.loads(creds_json)
                return OAuth2Credentials.from_authorized_user_info(creds_data)
            return None
        except Exception:
            # If anything goes wrong, return None to trigger re-auth
            return None
    
    def authenticate(self) -> Credentials:
        """Perform OAuth2 authentication flow."""
        try:
            flow = InstalledAppFlow.from_client_config(self.client_config, self.scopes)
            # Try different ports if 8080 is busy
            for port in [8080, 8081, 8082, 0]:  # 0 means random available port
                try:
                    credentials = flow.run_local_server(port=port)
                    self.save_credentials(credentials)
                    return credentials
                except OSError as port_error:
                    if "Address already in use" in str(port_error) and port != 0:
                        continue  # Try next port
                    else:
                        raise port_error
            raise Exception("No available ports found")
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {e}")
    
    def get_valid_credentials(self) -> Credentials:
        """Get valid credentials, refreshing or re-authenticating if needed."""
        try:
            # Try to load existing credentials
            credentials = self.load_credentials()
            
            # Check if existing credentials have the right scopes
            if credentials and hasattr(credentials, 'scopes'):
                requested_scopes = set(self.scopes)
                actual_scopes = set(credentials.scopes) if credentials.scopes else set()
                
                if not requested_scopes.issubset(actual_scopes):
                    print(f"⚠️  Stored credentials have insufficient scopes")
                    print(f"   Requested: {requested_scopes}")
                    print(f"   Available: {actual_scopes}")
                    print(f"   Missing: {requested_scopes - actual_scopes}")
                    print(f"   🔄 Re-authenticating with new scopes...")
                    credentials = None  # Force re-authentication
            
            if credentials is None:
                # No existing credentials, need to authenticate
                return self.authenticate()
            
            if credentials.valid:
                # Credentials are still valid
                return credentials
            
            if credentials.expired and credentials.refresh_token:
                # Credentials expired but can be refreshed
                try:
                    credentials.refresh(Request())
                    self.save_credentials(credentials)
                    return credentials
                except Exception:
                    # Refresh failed, need to re-authenticate
                    return self.authenticate()
            
            # Credentials are invalid and can't be refreshed
            return self.authenticate()
            
        except AuthenticationError:
            # Re-raise AuthenticationError as-is
            raise
        except Exception as e:
            raise AuthenticationError(f"Failed to authenticate: {e}")