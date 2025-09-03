import pytest

from inbox_cleaner.auth import GmailAuthenticator


def test_init_with_placeholder_client_id():
    # Placeholder from example config
    placeholder = {
        "client_id": "your-client-id.apps.googleusercontent.com",
        "client_secret": "secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }
    with pytest.raises(ValueError) as exc:
        GmailAuthenticator(placeholder)
    assert "Invalid Gmail OAuth client configuration" in str(exc.value)

    # Note: We only strictly reject the known placeholder pattern
    # to avoid breaking tests that use dummy client IDs.


def test_client_config_uses_v2_endpoints_and_localhost_redirects():
    auth_config = {
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }
    auth = GmailAuthenticator(auth_config)
    installed = auth.client_config["installed"]
    assert installed["auth_uri"].endswith("/o/oauth2/v2/auth")
    assert "oauth2.googleapis.com/token" in installed["token_uri"]
    assert "http://localhost" in installed["redirect_uris"]
