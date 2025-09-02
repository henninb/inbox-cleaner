"""Command line interface for inbox cleaner."""

import click
import yaml
from pathlib import Path
from googleapiclient.discovery import build

from .auth import GmailAuthenticator, AuthenticationError
from .database import DatabaseManager
from .extractor import GmailExtractor
from .unsubscribe_engine import UnsubscribeEngine


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Gmail Inbox Cleaner - Privacy-focused email management with AI assistance."""
    pass


@main.command()
@click.option('--setup', is_flag=True, help='Set up OAuth2 authentication')
@click.option('--status', is_flag=True, help='Check authentication status')
def auth(setup, status):
    """Manage authentication."""
    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found. Please create it from config.yaml.example")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        authenticator = GmailAuthenticator(gmail_config)

        if setup:
            click.echo("🔐 Setting up OAuth2 authentication...")
            try:
                credentials = authenticator.authenticate()
                click.echo("✅ Authentication successful!")
                click.echo("Credentials saved securely.")
            except AuthenticationError as e:
                click.echo(f"❌ Authentication failed: {e}")
                return
        elif status:
            click.echo("🔍 Checking authentication status...")
            try:
                credentials = authenticator.load_credentials()
                if credentials:
                    if getattr(credentials, 'valid', False):
                        click.echo("✅ Valid credentials found")
                    elif credentials.expired:
                        click.echo("⚠️  Credentials expired - will refresh automatically")
                    else:
                        click.echo("⚠️  Credentials found but status unclear")
                else:
                    click.echo("❌ No credentials found - run 'auth --setup'")
            except Exception as e:
                click.echo(f"❌ Error checking credentials: {e}")
        else:
            # Default: check status
            click.echo("🔍 Checking authentication status...")
            try:
                credentials = authenticator.load_credentials()
                if credentials and getattr(credentials, 'valid', False):
                    click.echo("✅ Authentication valid")
                else:
                    click.echo("❌ Authentication needed - run 'auth --setup'")
            except Exception as e:
                click.echo(f"❌ Error: {e}")

    except Exception as e:
        click.echo(f"❌ Configuration error: {e}")


@main.command()
@click.option('--initial', is_flag=True, help='Initial sync of all emails')
@click.option('--batch-size', default=1000, help='Batch size for processing')
@click.option('--with-progress', is_flag=True, help='Show progress bar')
@click.option('--limit', default=None, type=int, help='Limit number of emails to sync')
def sync(initial, batch_size, with_progress, limit):
    """Sync emails from Gmail."""
    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        db_path = config['database']['path']

        # Initialize components
        authenticator = GmailAuthenticator(gmail_config)

        click.echo("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError:
            click.echo("❌ Authentication failed. Run 'auth --setup' first.")
            return

        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)

        # Initialize extractor and database
        extractor = GmailExtractor(service, batch_size=batch_size)

        with DatabaseManager(db_path) as db:
            if initial:
                click.echo(f"📥 Starting initial sync (batch size: {batch_size})...")
                if limit:
                    click.echo(f"📊 Limited to {limit} emails")
            else:
                click.echo("📥 Syncing recent emails...")

            def progress_callback(current: int, total: int) -> None:
                if with_progress:
                    percentage = (current / total) * 100 if total > 0 else 0
                    click.echo(f"Progress: {current}/{total} ({percentage:.1f}%)", nl=False)
                    click.echo("\r", nl=False)

            try:
                emails = extractor.extract_all(
                    progress_callback=progress_callback if with_progress else None,
                    max_results=limit
                )

                click.echo(f"\n📊 Extracted {len(emails)} emails")

                # Save to database
                click.echo("💾 Saving to database...")
                saved_count = 0
                for email in emails:
                    try:
                        db.insert_email(email)
                        saved_count += 1
                    except Exception as e:
                        # Skip duplicates silently
                        if "UNIQUE constraint" not in str(e):
                            click.echo(f"⚠️  Warning: {e}")

                click.echo(f"✅ Saved {saved_count} emails to database")

                # Show summary
                stats = db.get_statistics()
                click.echo(f"📈 Database now contains {stats['total_emails']} emails")

            except Exception as e:
                click.echo(f"❌ Sync failed: {e}")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@main.command()
@click.option('--start', is_flag=True, help='Start web interface')
@click.option('--port', default=8000, help='Port for web interface')
@click.option('--host', default='127.0.0.1', help='Host to bind to')
def web(start, port, host):
    """Manage web interface."""
    if start:
        try:
            # Load configuration
            config_path = Path("config.yaml")
            if not config_path.exists():
                click.echo("❌ Error: config.yaml not found")
                return

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            db_path = config['database']['path']

            click.echo(f"🌐 Starting web interface...")
            click.echo(f"📍 Host: {host}:{port}")
            click.echo(f"💾 Database: {db_path}")
            click.echo(f"🌍 Open: http://{host}:{port}")
            click.echo("Press Ctrl+C to stop")
            click.echo()

            # Import and start the web app
            from .web import create_app
            import uvicorn

            app = create_app(db_path=db_path)
            uvicorn.run(app, host=host, port=port, log_level="info")

        except KeyboardInterrupt:
            click.echo("\n🛑 Web interface stopped")
        except Exception as e:
            click.echo(f"❌ Error starting web interface: {e}")
    else:
        click.echo("🌐 Web interface management")
        click.echo("Available commands:")
        click.echo("  --start    Start web interface")
        click.echo("  --port     Specify port (default: 8000)")
        click.echo("  --host     Specify host (default: 127.0.0.1)")
        click.echo()
        click.echo("Example: python -m inbox_cleaner.cli web --start --port 8080")


@main.command()
def diagnose():
    """Run diagnostic tool to troubleshoot issues."""
    click.echo("🔍 Running diagnostics...")
    click.echo()

    # Check config file
    config_path = Path("config.yaml")
    if config_path.exists():
        click.echo("✅ config.yaml found")
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            if 'gmail' in config and config['gmail'].get('client_id'):
                click.echo("✅ Gmail configuration found")
            else:
                click.echo("❌ Gmail configuration missing or incomplete")
        except Exception as e:
            click.echo(f"❌ Error reading config: {e}")
    else:
        click.echo("❌ config.yaml not found")

    # Check authentication
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        gmail_config = config['gmail']
        authenticator = GmailAuthenticator(gmail_config)
        credentials = authenticator.load_credentials()

        if credentials:
            click.echo("✅ Stored credentials found")
            if getattr(credentials, 'valid', False):
                click.echo("✅ Credentials are valid")
            else:
                click.echo("⚠️  Credentials may need refresh")
        else:
            click.echo("❌ No stored credentials - run 'auth --setup'")
    except Exception as e:
        click.echo(f"❌ Authentication check failed: {e}")

    # Check database
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        db_path = config['database']['path']

        if Path(db_path).exists():
            with DatabaseManager(db_path) as db:
                stats = db.get_statistics()
                click.echo(f"✅ Database found with {stats['total_emails']} emails")
        else:
            click.echo("⚠️  Database not found - run 'sync' to create")
    except Exception as e:
        click.echo(f"❌ Database check failed: {e}")

    click.echo()
    click.echo("💡 For comprehensive troubleshooting, run:")
    click.echo("   python diagnose_issues.py")
    click.echo()
    click.echo("🔧 Common issues:")
    click.echo("   • Gmail API not enabled: Most common cause of 'No emails found'")
    click.echo("   • Wrong credentials: Check Client ID and Secret")
    click.echo("   • Authentication errors: Email not added as test user")
    click.echo()
    click.echo("📖 See README.md 'Common Setup Issues' for detailed solutions")


@main.command()
def status():
    """Show overall system status."""
    click.echo("📊 Inbox Cleaner Status")
    click.echo("=" * 25)

    # Configuration
    config_path = Path("config.yaml")
    if config_path.exists():
        click.echo("✅ Configuration: Ready")
    else:
        click.echo("❌ Configuration: Missing (run setup)")
        return

    # Authentication
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        gmail_config = config['gmail']
        authenticator = GmailAuthenticator(gmail_config)
        credentials = authenticator.load_credentials()

        if credentials and getattr(credentials, 'valid', False):
            click.echo("✅ Authentication: Valid")
        else:
            click.echo("❌ Authentication: Setup needed")
    except Exception:
        click.echo("❌ Authentication: Error")

    # Database
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        db_path = config['database']['path']

        if Path(db_path).exists():
            with DatabaseManager(db_path) as db:
                stats = db.get_statistics()
                click.echo(f"✅ Database: {stats['total_emails']} emails")
        else:
            click.echo("⚠️  Database: Empty (run sync)")
    except Exception:
        click.echo("❌ Database: Error")

    # Features
    click.echo()
    click.echo("📋 Available Features:")
    click.echo("  ✅ Email sync and extraction")
    click.echo("  ✅ Privacy-safe data processing")
    click.echo("  ✅ Command-line interface")
    click.echo("  ❌ Web interface (in development)")
    click.echo("  ❌ AI-powered cleanup (in development)")


@main.command('apply-filters')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes')
@click.option('--execute', is_flag=True, help='Actually apply filters and delete emails')
def apply_filters(dry_run, execute):
    """Apply existing auto-delete filters to clean the inbox."""

    if not dry_run and not execute:
        dry_run = True  # Default behavior
    elif execute:
        dry_run = False

    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found. Please create it from config.yaml.example")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        db_path = config['database']['path']

        # Initialize components
        authenticator = GmailAuthenticator(gmail_config)

        click.echo("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            click.echo(f"❌ Authentication failed: {e}")
            click.echo("Run 'auth --setup' first.")
            return

        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        db_manager = DatabaseManager(db_path)
        unsubscribe_engine = UnsubscribeEngine(service, db_manager)

        if dry_run:
            click.echo("💡 DRY RUN MODE - No changes will be made")
        else:
            click.echo("⚠️ EXECUTE MODE - Changes will be made to Gmail")

        # Execute deletion workflow
        results = unsubscribe_engine.apply_filters(dry_run=dry_run)

        # Display results
        click.echo(f"\n📋 Results:")
        click.echo(f"   Processed {results['processed_filters']} auto-delete filters.")

        if dry_run:
            click.echo(f"   Would delete {results['total_deleted']} emails.")
            click.echo(f"\n💡 To execute these actions, run with --execute")
        else:
            click.echo(f"   Deleted {results['total_deleted']} emails.")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@main.command('list-filters')

def list_filters():
    """List existing Gmail filters."""
    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found. Please create it from config.yaml.example")
            raise click.ClickException("config.yaml not found")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        db_path = config['database']['path']

        # Initialize components
        authenticator = GmailAuthenticator(gmail_config)

        click.echo("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            click.echo(f"❌ Authentication failed: {e}")
            click.echo("Run 'auth --setup' first.")
            raise click.ClickException("Authentication failed")

        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        db_manager = DatabaseManager(db_path)
        unsubscribe_engine = UnsubscribeEngine(service, db_manager)

        click.echo("📋 Existing Gmail Filters:")
        click.echo()

        # Get filters
        filters = unsubscribe_engine.list_existing_filters()

        if not filters:
            click.echo("   No filters found")
            return

        for i, f in enumerate(filters, 1):
            criteria = f.get('criteria', {})
            actions = f.get('action', {})

            filter_id = f.get('id', 'unknown')[:15]
            click.echo(f"   Filter {i} (ID: {filter_id}...):")

            if 'from' in criteria:
                click.echo(f"      From: {criteria['from']}")
            if 'to' in criteria:
                click.echo(f"      To: {criteria['to']}")
            if 'query' in criteria:
                click.echo(f"      Query: {criteria['query']}")

            if 'addLabelIds' in actions:
                labels = actions['addLabelIds']
                if 'TRASH' in labels:
                    click.echo(f"      Action: Auto-delete")
                else:
                    click.echo(f"      Action: Add labels {labels}")
            click.echo()

    except Exception as e:
        click.echo(f"❌ Error: {e}")
        raise click.ClickException(str(e))


@main.command('delete-emails')
@click.option('--domain', required=True, help='Domain to delete emails from')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes')
@click.option('--execute', is_flag=True, help='Actually delete emails')
def delete_emails(domain, dry_run, execute):
    """Delete emails from specified domain."""

    # Handle conflicting flags - default to dry_run if neither is specified
    if not dry_run and not execute:
        dry_run = True  # Default behavior
    elif execute:
        dry_run = False

    if not domain:
        click.echo("❌ Error: domain is required")
        return

    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found. Please create it from config.yaml.example")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        db_path = config['database']['path']

        # Initialize components
        authenticator = GmailAuthenticator(gmail_config)

        click.echo("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            click.echo(f"❌ Authentication failed: {e}")
            click.echo("Run 'auth --setup' first.")
            return

        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        db_manager = DatabaseManager(db_path)
        unsubscribe_engine = UnsubscribeEngine(service, db_manager)

        if dry_run:
            click.echo("💡 DRY RUN MODE - No changes will be made")
        else:
            click.echo("⚠️ EXECUTE MODE - Changes will be made to Gmail")

        click.echo(f"🎯 Processing domain: {domain}")

        # Execute deletion workflow
        results = unsubscribe_engine.unsubscribe_and_block_domain(domain, dry_run=dry_run)

        # Display results
        click.echo(f"\n📋 Results for {domain}:")

        for step in results['steps']:
            step_name = step['step'].replace('_', ' ').title()

            if step['success']:
                click.echo(f"   ✅ {step_name}: Success")

                if step['step'] == 'delete_existing':
                    result = step['result']
                    found = result.get('found_count', 0)
                    deleted = result.get('deleted_count', 0)

                    if dry_run:
                        click.echo(f"      Would delete {found} existing emails")
                    else:
                        click.echo(f"      Deleted {deleted} of {found} emails")

            else:
                click.echo(f"   ❌ {step_name}: Failed")
                if 'message' in step:
                    click.echo(f"      {step['message']}")

        if dry_run:
            click.echo(f"\n💡 To execute these actions, run with --execute")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@main.command('find-unsubscribe')
@click.option('--domain', required=True, help='Domain to find unsubscribe links for')
def find_unsubscribe(domain):
    """Find unsubscribe links in emails from specified domain."""

    if not domain:
        click.echo("❌ Error: domain is required")
        return

    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found. Please create it from config.yaml.example")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        gmail_config = config['gmail']
        db_path = config['database']['path']

        # Initialize components
        authenticator = GmailAuthenticator(gmail_config)

        click.echo("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            click.echo(f"❌ Authentication failed: {e}")
            click.echo("Run 'auth --setup' first.")
            return

        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials)
        db_manager = DatabaseManager(db_path)
        unsubscribe_engine = UnsubscribeEngine(service, db_manager)

        click.echo(f"🔍 Finding unsubscribe links for: {domain}")

        # Find unsubscribe links
        unsubscribe_info = unsubscribe_engine.find_unsubscribe_links(domain)

        if not unsubscribe_info:
            click.echo("❌ No unsubscribe links found")
            return

        click.echo(f"\n📧 Found unsubscribe links:")
        for info in unsubscribe_info:
            click.echo(f"\n   Email: {info['subject']}")
            click.echo(f"   Links found:")
            for i, link in enumerate(info['unsubscribe_links'][:3], 1):  # Show first 3
                if link.startswith('mailto:'):
                    click.echo(f"      {i}. 📧 {link}")
                else:
                    click.echo(f"      {i}. 🔗 {link}")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


if __name__ == "__main__":
    main()