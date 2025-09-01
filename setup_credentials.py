#!/usr/bin/env python3
"""
Interactive setup script for Gmail API credentials.

This script helps you set up the Gmail Inbox Cleaner by:
1. Creating the config.yaml file
2. Prompting for your Gmail API credentials
3. Testing the configuration

Run: python setup_credentials.py
"""

import yaml
from pathlib import Path


def main():
    """Interactive credential setup."""
    print("🔐 Gmail Inbox Cleaner - Credential Setup")
    print("=" * 50)
    print()
    
    config_path = Path("config.yaml")
    if config_path.exists():
        response = input("⚠️  config.yaml already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("❌ Setup cancelled")
            return
    
    print("📝 Please provide your Gmail API credentials from Google Cloud Console:")
    print("   (If you haven't set them up yet, see the README for instructions)")
    print()
    
    # Get credentials from user
    client_id = input("🔑 Client ID (ends with .googleusercontent.com): ").strip()
    if not client_id:
        print("❌ Client ID is required")
        return
    
    client_secret = input("🔒 Client Secret: ").strip()
    if not client_secret:
        print("❌ Client Secret is required")
        return
    
    print()
    print("⚙️  Additional settings:")
    
    # Database path
    db_path = input("💾 Database path (press Enter for default './inbox_cleaner.db'): ").strip()
    if not db_path:
        db_path = "./inbox_cleaner.db"
    
    # Batch size
    batch_input = input("📦 Batch size (press Enter for default 1000): ").strip()
    try:
        batch_size = int(batch_input) if batch_input else 1000
    except ValueError:
        batch_size = 1000
    
    # Max emails per run
    max_input = input("🔢 Max emails per run (press Enter for default 5000): ").strip()
    try:
        max_emails = int(max_input) if max_input else 5000
    except ValueError:
        max_emails = 5000
    
    # Create configuration
    config = {
        'gmail': {
            'client_id': client_id,
            'client_secret': client_secret,
            'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
        },
        'database': {
            'path': db_path
        },
        'app': {
            'batch_size': batch_size,
            'max_emails_per_run': max_emails
        }
    }
    
    # Save configuration
    try:
        with open(config_path, 'w') as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        
        print()
        print("✅ Configuration saved to config.yaml")
        print()
        print("🎉 Setup complete! You can now run:")
        print("   python real_demo.py --auth      # Test authentication")
        print("   python real_demo.py --extract 5 # Extract 5 emails")
        print("   python real_demo.py --stats     # Show statistics")
        print()
        print("🔒 Security note: Your credentials are stored locally in config.yaml")
        print("   Make sure to keep this file secure and don't share it!")
        
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")


if __name__ == '__main__':
    main()