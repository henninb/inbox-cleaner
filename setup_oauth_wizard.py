#!/usr/bin/env python3
"""
OAuth Setup Wizard - walks through fixing OAuth consent screen setup.
"""

import webbrowser
import time

def print_step(step_num, title, description):
    """Print a formatted step."""
    print(f"\n📋 STEP {step_num}: {title}")
    print("=" * (len(title) + 15))
    print(description)

def wait_for_user(message="Press Enter when complete..."):
    """Wait for user input."""
    try:
        input(f"\n⏳ {message}")
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled")
        exit(1)

def main():
    """OAuth setup wizard."""

    print("🎯 Gmail OAuth Setup Wizard")
    print("=" * 50)
    print("This wizard will fix your OAuth consent screen to enable email deletion and filter creation.")
    print()

    # Step 1: Open Google Cloud Console
    print_step(1, "Open Google Cloud Console",
        "We'll open your Google Cloud Console project where your Gmail API credentials are configured.")

    wait_for_user("Ready to open Google Cloud Console? Press Enter...")

    try:
        webbrowser.open("https://console.cloud.google.com/")
        print("✅ Opened Google Cloud Console in your browser")
    except:
        print("❌ Couldn't open browser automatically")
        print("🔗 Please manually go to: https://console.cloud.google.com/")

    # Step 2: Navigate to OAuth consent screen
    print_step(2, "Navigate to OAuth Consent Screen",
        """In Google Cloud Console:
1. Make sure you've selected the correct project (top left dropdown)
2. In the left sidebar, click: APIs & Services → OAuth consent screen
3. You should see your existing OAuth app configuration""")

    wait_for_user("Found your OAuth consent screen? Press Enter...")

    # Step 3: Edit the app
    print_step(3, "Edit Your OAuth App",
        """On the OAuth consent screen page:
1. Click the "EDIT APP" button
2. This will open the OAuth consent screen editor""")

    wait_for_user("Clicked 'EDIT APP' and in the editor? Press Enter...")

    # Step 4: Add scopes
    print_step(4, "Add Required Scopes",
        """In the OAuth consent screen editor:
1. Scroll down to find the "Scopes" section
2. Click "ADD OR REMOVE SCOPES" button
3. A popup will appear with available scopes""")

    wait_for_user("Found the scopes section and clicked 'ADD OR REMOVE SCOPES'? Press Enter...")

    print_step(5, "Select Required Gmail Scopes",
        """In the scope selection popup, you need to find and select these scopes:

REQUIRED SCOPES:
✅ https://www.googleapis.com/auth/gmail.readonly
   (You probably already have this one)

🔄 https://www.googleapis.com/auth/gmail.modify
   Description: "Manage drafts and send emails"

🔄 https://www.googleapis.com/auth/gmail.settings.basic
   Description: "Manage your basic mail settings"

SEARCH TIPS:
• Use the search box at the top of the scope popup
• Search for "gmail.modify" to find the modify scope
• Search for "gmail.settings" to find the settings scope
• Check the boxes next to each scope to select them""")

    wait_for_user("Found and selected both gmail.modify and gmail.settings.basic scopes? Press Enter...")

    # Step 5: Save changes
    print_step(6, "Save Your Changes",
        """Now save the scope changes:
1. Click "UPDATE" in the scope selection popup
2. This will add the scopes to your OAuth app
3. Click "SAVE AND CONTINUE" to proceed through any remaining screens
4. On the final screen, click "BACK TO DASHBOARD" """)

    wait_for_user("Saved all changes and back to the dashboard? Press Enter...")

    # Step 6: Wait for propagation
    print_step(7, "Wait for Google's Systems to Update",
        """Google needs 2-3 minutes to propagate the scope changes across their systems.

Let's wait 3 minutes to ensure everything is ready...""")

    print("⏳ Waiting 3 minutes for Google systems to update...")
    for i in range(180, 0, -30):
        mins = i // 60
        secs = i % 60
        print(f"   ⏱️  {mins:02d}:{secs:02d} remaining...")
        time.sleep(30)

    print("✅ Wait complete! Google's systems should be updated.")

    # Step 7: Clear credentials and test
    print_step(8, "Clear Old Credentials",
        """Now we need to clear your old credentials that have insufficient scopes:""")

    print("🧹 Clearing stored credentials...")

    try:
        import keyring
        keyring.delete_password('inbox-cleaner', 'gmail-token')
        print("✅ Cleared oauth credentials")
    except:
        print("⚠️  No stored credentials found (that's OK)")

    # Step 8: Test the setup
    print_step(9, "Test OAuth Setup",
        """Let's test if the OAuth setup is working correctly:""")

    print("🧪 Running OAuth diagnostics...")

    try:
        import subprocess
        result = subprocess.run(["python", "diagnose_oauth.py"], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)

        if "ALL PERMISSION TESTS PASSED" in result.stdout:
            print("\n🎉 SUCCESS! OAuth is configured correctly!")
            print("✅ You can now run the automated cleanup tools:")
            print("   python unsubscribe_and_block.py --all-domains --execute --force")
        else:
            print("\n⚠️  OAuth test didn't fully pass.")
            print("💡 Try running: python diagnose_oauth.py")

    except Exception as e:
        print(f"❌ Couldn't run diagnostics automatically: {e}")
        print("💡 Please run manually: python diagnose_oauth.py")

    print_step(10, "Next Steps",
        """If OAuth diagnostics passed, you're ready for automated cleanup!

AUTOMATED CLEANUP:
• python unsubscribe_and_block.py --all-domains --dry-run    (preview)
• python unsubscribe_and_block.py --all-domains --execute    (execute)

MANUAL CLEANUP:
• python manual_cleanup_guide.py    (if automation still doesn't work)

TROUBLESHOOTING:
• python diagnose_oauth.py    (check OAuth status)""")

    print("\n🎊 Setup wizard complete!")
    print("You should now be able to programmatically clean up your 1,490 spam emails!")

if __name__ == '__main__':
    main()