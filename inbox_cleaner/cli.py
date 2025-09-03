"""Command line interface for inbox cleaner."""

import click
import yaml
from pathlib import Path
from googleapiclient.discovery import build

from .auth import GmailAuthenticator, AuthenticationError
from .database import DatabaseManager
from .extractor import GmailExtractor
from .unsubscribe_engine import UnsubscribeEngine
from .spam_rules import SpamRuleManager
from .retention_manager import RetentionManager


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Gmail Inbox Cleaner - Privacy-focused email management with AI assistance."""
    pass


@main.command()
@click.option('--setup', is_flag=True, help='Set up OAuth2 authentication')
@click.option('--status', is_flag=True, help='Check authentication status')
@click.option('--logout', is_flag=True, help='Logout and clear stored credentials')
@click.option('--device-flow', is_flag=True, help='Use device flow for authentication (requires desktop client)')
@click.option('--web-server', is_flag=True, help='Use temporary web server for authentication (recommended)')
def auth(setup, status, logout, device_flow, web_server):
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
            if web_server:
                click.echo("🔐 Setting up OAuth2 authentication using temporary web server...")
                try:
                    credentials = authenticator.authenticate_with_temp_server()
                    click.echo("✅ Authentication successful!")
                    click.echo("Credentials saved securely.")
                except AuthenticationError as e:
                    click.echo(f"❌ Web server authentication failed: {e}")
                    click.echo()
                    click.echo("🔄 Falling back to manual authentication flow...")
                    try:
                        credentials = authenticator.authenticate()
                        click.echo("✅ Fallback authentication successful!")
                        click.echo("Credentials saved securely.")
                    except AuthenticationError as fallback_error:
                        click.echo(f"❌ Fallback authentication also failed: {fallback_error}")
                        return
            elif device_flow:
                click.echo("🔐 Setting up OAuth2 authentication using device flow...")
                try:
                    credentials = authenticator.authenticate_device_flow()
                    click.echo("✅ Authentication successful!")
                    click.echo("Credentials saved securely.")
                except AuthenticationError as e:
                    if "Desktop application" in str(e):
                        click.echo(f"❌ Device flow failed: {e}")
                        click.echo()
                        click.echo("🔄 Falling back to manual authentication flow...")
                        try:
                            credentials = authenticator.authenticate()
                            click.echo("✅ Fallback authentication successful!")
                            click.echo("Credentials saved securely.")
                        except AuthenticationError as fallback_error:
                            click.echo(f"❌ Fallback authentication also failed: {fallback_error}")
                            return
                    else:
                        click.echo(f"❌ Device flow authentication failed: {e}")
                        return
            else:
                click.echo("🔐 Setting up OAuth2 authentication...")
                click.echo("💡 Tip: Use --web-server for the best authentication experience!")
                click.echo("💡 Or use --device-flow if you have a desktop OAuth2 client")
                try:
                    credentials = authenticator.authenticate()
                    click.echo("✅ Authentication successful!")
                    click.echo("Credentials saved securely.")
                except AuthenticationError as e:
                    click.echo(f"❌ Authentication failed: {e}")
                    click.echo("💡 Try using --web-server for easier authentication")
                    return
        elif logout:
            click.echo("🔓 Logging out...")
            try:
                success = authenticator.logout()
                if success:
                    click.echo("✅ Logout successful! Credentials cleared.")
                else:
                    click.echo("⚠️  No stored credentials found to clear.")
            except Exception as e:
                click.echo(f"❌ Logout failed: {e}")
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


@main.command('spam-cleanup')
@click.option('--analyze', is_flag=True, help='Analyze emails for spam patterns')
@click.option('--setup-rules', is_flag=True, help='Set up predefined spam rules')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes')
@click.option('--execute', is_flag=True, help='Actually delete spam emails')
@click.option('--limit', default=1000, type=int, help='Limit number of emails to analyze')
def spam_cleanup(analyze, setup_rules, dry_run, execute, limit):
    """Advanced spam detection and cleanup."""

    if not any([analyze, setup_rules, dry_run, execute]):
        analyze = True  # Default action

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

        # Initialize spam rule manager
        spam_rules = SpamRuleManager()

        if setup_rules:
            click.echo("🛡️  Setting up predefined spam rules...")
            rules = spam_rules.create_predefined_spam_rules()
            spam_rules.save_rules()
            click.echo(f"✅ Created {len(rules)} spam detection rules")

            click.echo("\n📋 Spam detection rules created:")
            for rule in rules:
                rule_type = rule['type']
                pattern = rule.get('pattern', rule.get('domain', 'N/A'))
                reason = rule['reason']
                click.echo(f"  • {rule_type.title()}: {pattern}")
                click.echo(f"    Reason: {reason}")

            spam_rules.save_rules()
            click.echo(f"\n💾 Rules saved to {spam_rules.rules_file}")
            return

        # For analysis, dry-run, or execution, we need authentication
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

        # Get emails from database for analysis
        with DatabaseManager(db_path) as db:
            if analyze:
                click.echo(f"🔍 Analyzing last {limit} emails for spam patterns...")

                # Get recent emails from database
                emails = db.search_emails("", limit=limit)

                if not emails:
                    click.echo("❌ No emails found in database. Run 'sync' first.")
                    return

                # Analyze spam patterns
                analysis = spam_rules.analyze_spam_patterns(emails)

                click.echo(f"\n📊 Spam Analysis Results:")
                click.echo(f"  Total emails analyzed: {analysis['total_emails']}")
                click.echo(f"  Suspicious emails found: {len(analysis['suspicious_emails'])}")

                # Show spam indicators
                indicators = analysis['spam_indicators']
                if indicators['ip_in_sender'] > 0:
                    click.echo(f"  • IPs in sender emails: {indicators['ip_in_sender']}")
                if indicators['misspelled_subjects'] > 0:
                    click.echo(f"  • Misspelled subjects: {indicators['misspelled_subjects']}")
                if indicators['prize_scams'] > 0:
                    click.echo(f"  • Prize/lottery scams: {indicators['prize_scams']}")
                if indicators['urgent_language'] > 0:
                    click.echo(f"  • Urgent language: {indicators['urgent_language']}")
                if indicators['suspicious_domains']:
                    click.echo(f"  • Suspicious domains: {len(indicators['suspicious_domains'])}")

                # Show most suspicious emails
                if analysis['suspicious_emails']:
                    click.echo(f"\n🚨 Most suspicious emails:")
                    sorted_suspicious = sorted(
                        analysis['suspicious_emails'],
                        key=lambda x: x['spam_score'],
                        reverse=True
                    )[:5]

                    for email in sorted_suspicious:
                        click.echo(f"\n  📧 Score: {email['spam_score']}")
                        click.echo(f"     From: {email['sender']}")
                        click.echo(f"     Subject: {email['subject'][:50]}...")
                        click.echo(f"     Indicators: {', '.join(email['indicators'])}")

                # Show suggested rules
                if analysis['suggested_rules']:
                    click.echo(f"\n💡 Suggested spam rules:")
                    for rule in analysis['suggested_rules']:
                        pattern = rule.get('pattern', rule.get('domain', ''))
                        click.echo(f"  • {rule['type'].title()}: {pattern}")
                        click.echo(f"    Reason: {rule['reason']}")

                click.echo(f"\n🛡️  To set up automatic spam rules, run:")
                click.echo(f"   python -m inbox_cleaner.cli spam-cleanup --setup-rules")

            elif dry_run or execute:
                mode = "EXECUTE" if execute else "DRY RUN"
                click.echo(f"🚮 {mode} MODE: Spam cleanup...")

                if not execute:
                    click.echo("💡 No changes will be made (dry run mode)")

                # Get all emails for rule matching
                all_emails = db.search_emails("", limit=limit)
                active_rules = spam_rules.get_active_rules()

                if not active_rules:
                    click.echo("❌ No active spam rules found. Run --setup-rules first.")
                    return

                click.echo(f"📋 Using {len(active_rules)} active spam rules")

                deleted_count = 0
                emails_to_delete = []

                for email in all_emails:
                    matched_rule = spam_rules.matches_spam_rule(email)
                    if matched_rule and matched_rule['action'] == 'delete':
                        emails_to_delete.append({
                            'email': email,
                            'rule': matched_rule
                        })

                if emails_to_delete:
                    click.echo(f"\n🎯 Found {len(emails_to_delete)} emails matching spam rules:")

                    for item in emails_to_delete[:10]:  # Show first 10
                        email = item['email']
                        rule = item['rule']
                        click.echo(f"  • {email.get('sender_email', 'Unknown sender')}")
                        click.echo(f"    Subject: {email.get('subject', 'No subject')[:50]}...")
                        click.echo(f"    Rule: {rule['reason']}")

                    if len(emails_to_delete) > 10:
                        click.echo(f"  ... and {len(emails_to_delete) - 10} more")

                    if execute:
                        click.echo(f"\n🚮 Deleting {len(emails_to_delete)} spam emails...")

                        for item in emails_to_delete:
                            email = item['email']
                            message_id = email.get('message_id')

                            try:
                                # Delete from Gmail
                                service.users().messages().delete(
                                    userId='me',
                                    id=message_id
                                ).execute()

                                # Delete from database
                                db.delete_email(message_id)
                                deleted_count += 1

                            except Exception as e:
                                click.echo(f"⚠️  Failed to delete {message_id}: {e}")

                        click.echo(f"✅ Successfully deleted {deleted_count} spam emails")
                    else:
                        click.echo(f"\n💡 To execute deletion, run with --execute")
                else:
                    click.echo("✅ No spam emails found matching current rules")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@main.command('create-spam-filters')
@click.option('--execute', is_flag=True, help='Create filters in Gmail (default is dry-run)')
@click.option('--dry-run', is_flag=True, help='Preview filters without creating them')
def create_spam_filters(execute, dry_run):
    """Create Gmail auto-delete filters for common spam/fraud patterns."""

    if not dry_run and not execute:
        dry_run = True
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

        # Patterns from user-provided spam examples
        spam_domains = [
            'eleganceaffairs.com',
            'speedytype.com',
            'mineralsbid.com',
            'fp8888.com',
            'pets-tiara.com',
            'koidor.com',
            'delmedicogroup.com',
            'aksuhaliyikama.us.com',
        ]

        subject_keywords = [
            'Free Spins',
            'Your Email Has Been Chosen',
            'YourVip-Pass',
            'Important Update - MUST SEE',
            'Congratulations',
            'Millionaire',
            'Million to win',
            'WinnersList',
            'Instant-Millionaire',
            'BonusOnHold',
        ]

        # Build desired filters list
        desired_filters = []

        # Domain-based delete filters
        for domain in spam_domains:
            desired_filters.append({
                'criteria': {'from': domain},
                'action': {
                    'addLabelIds': ['TRASH'],
                    'removeLabelIds': ['INBOX', 'UNREAD']
                },
                'reason': f'spam domain: {domain}'
            })

        # Subject keyword delete filters (use query with subject operator)
        for kw in subject_keywords:
            desired_filters.append({
                'criteria': {'query': f'subject:"{kw}"'},
                'action': {
                    'addLabelIds': ['TRASH'],
                    'removeLabelIds': ['INBOX', 'UNREAD']
                },
                'reason': f'subject keyword: {kw}'
            })

        # Get existing filters to avoid duplicates
        existing = service.users().settings().filters().list(userId='me').execute()
        existing_filters = existing.get('filter', [])

        def criteria_key(c: dict) -> tuple:
            return (
                c.get('from', ''),
                c.get('to', ''),
                c.get('subject', ''),
                c.get('query', ''),
                c.get('negatedQuery', ''),
                str(c.get('hasAttachment', False)),
                str(c.get('size', '')),
                c.get('sizeComparison', ''),
            )

        existing_keys = set()
        for f in existing_filters:
            existing_keys.add(criteria_key(f.get('criteria', {})))

        to_create = [f for f in desired_filters if criteria_key(f['criteria']) not in existing_keys]

        if not to_create:
            click.echo('✅ No new spam filters to create (all present).')
            return

        if dry_run:
            click.echo('💡 DRY RUN - Filters that would be created:')
            for f in to_create:
                crit = f['criteria']
                if 'from' in crit:
                    click.echo(f"  • Delete from domain: {crit['from']}  ({f['reason']})")
                elif 'query' in crit:
                    click.echo(f"  • Delete by query: {crit['query']}  ({f['reason']})")
            click.echo(f"Total: {len(to_create)} new filters")
            click.echo('Re-run with --execute to create them.')
            return

        # Execute: create filters
        created = 0
        for f in to_create:
            try:
                service.users().settings().filters().create(
                    userId='me',
                    body={
                        'criteria': f['criteria'],
                        'action': f['action']
                    }
                ).execute()
                created += 1
            except Exception as e:
                click.echo(f"❌ Failed to create filter ({f['reason']}): {e}")

        click.echo(f"✅ Created {created} spam filters")
        if created < len(to_create):
            click.echo(f"⚠️  Skipped {len(to_create) - created} due to errors")

    except Exception as e:
        click.echo(f"❌ Error: {e}")

@main.command('mark-read')
@click.option('--query', default=None, help='Gmail search query (default: all unread)')
@click.option('--batch-size', default=500, type=int, help='Batch size for API calls (max 500)')
@click.option('--limit', default=None, type=int, help='Optional max messages to process')
@click.option('--inbox-only', is_flag=True, help='Restrict to Inbox only when using default query')
@click.option('--include-spam-trash', is_flag=True, help='Include Spam/Trash when using default query')
@click.option('--execute', is_flag=True, help='Actually mark as read (default is dry-run)')
def mark_read(query, batch_size, limit, inbox_only, include_spam_trash, execute):
    """Mark Gmail messages as read by removing the UNREAD label."""
    try:
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found")
            return
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        gmail_config = config['gmail']
        authenticator = GmailAuthenticator(gmail_config)
        click.echo("🔐 Getting credentials...")
        try:
            credentials = authenticator.get_valid_credentials()
        except AuthenticationError as e:
            click.echo(f"❌ Authentication failed: {e}")
            click.echo("Run 'auth --setup' first.")
            return
        service = build('gmail', 'v1', credentials=credentials)
        if not query:
            parts = ["is:unread"]
            if inbox_only:
                parts.append("in:inbox")
            if not include_spam_trash:
                parts.append("-in:spam -in:trash")
            query = " ".join(parts)
        click.echo(f"🔍 Selecting messages with query: {query}")
        mode = "EXECUTE" if execute else "DRY RUN"
        click.echo(f"🚩 Mode: {mode}")
        user_id = 'me'
        next_page_token = None
        total_seen = 0
        total_modified = 0
        batch_size = max(1, min(500, int(batch_size)))
        while True:
            params = {'userId': user_id, 'q': query, 'maxResults': batch_size}
            if next_page_token:
                params['pageToken'] = next_page_token
            resp = service.users().messages().list(**params).execute()
            messages = resp.get('messages', [])
            if not messages:
                break
            ids = [m['id'] for m in messages]
            if limit is not None:
                remaining = max(0, limit - total_seen)
                if remaining <= 0:
                    break
                ids = ids[:remaining]
            total_seen += len(ids)
            if execute and ids:
                try:
                    service.users().messages().batchModify(userId=user_id, body={'ids': ids, 'removeLabelIds': ['UNREAD']}).execute()
                    total_modified += len(ids)
                except Exception as e:
                    if 'insufficientPermissions' in str(e) or '403' in str(e):
                        click.echo("❌ Permission error: missing gmail.modify scope.")
                        click.echo("   Re-auth: python -m inbox_cleaner.cli auth --setup")
                        return
                    click.echo(f"⚠️  Failed a batch: {e}")
            next_page_token = resp.get('nextPageToken')
            if not next_page_token or (limit is not None and total_seen >= limit):
                break
        if execute:
            click.echo(f"✅ Marked {total_modified} messages as read.")
        else:
            click.echo(f"✅ Would mark {total_seen} messages as read. Re-run with --execute to apply.")
    except Exception as e:
        click.echo(f"❌ Error: {e}")




@main.command('retention')
@click.option('--analyze', is_flag=True, help='Analyze retention candidates (default)')
@click.option('--cleanup', is_flag=True, help='Delete old emails via live Gmail search')
@click.option('--cleanup-live', 'cleanup_live', is_flag=True, help='Delete old emails via live Gmail search (bypass DB)')
@click.option('--sync-db', is_flag=True, help='Remove orphaned emails from database that no longer exist in Gmail')
@click.option('--days', default=30, type=int, help='Retention window in days (default: 30)')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes')
def retention(analyze, cleanup, cleanup_live, sync_db, days, dry_run):
    """Retention manager for USPS, Security alerts, Hulu, Privacy.com, Spotify, Acorns, Veterans Affairs."""
    try:
        if not any([analyze, cleanup, cleanup_live, sync_db]):
            analyze = True

        rm = RetentionManager(retention_days=days)
        rm.setup_services()

        if analyze:
            results = rm.analyze()
            total_old = sum(len(results[k].old) for k in results)
            total_recent = sum(len(results[k].recent) for k in results)
            click.echo('📊 Retention Analysis:')
            click.echo('=' * 40)
            for k in ['usps','security','hulu','privacy','spotify','acorns','va']:
                r = results[k]
                click.echo(f"{k.title():<10} • Recent: {len(r.recent):<5} • Old: {len(r.old):<5}")
            click.echo(f"\nTotal kept: {total_recent}  |  Total old: {total_old}")
            return

        if cleanup:
            if dry_run:
                click.echo('💡 DRY RUN MODE - No changes will be made')
            else:
                click.echo('⚠️  EXECUTE MODE - Changes will be made to Gmail')
            counts = rm.cleanup_live(dry_run=dry_run, verbose=True)
            rm.print_kept_summary()
            if dry_run and counts.get('total', 0) > 0:
                click.echo(f"\n💡 To execute these actions, re-run without --dry-run")
            return

        if cleanup_live:
            if dry_run:
                click.echo('💡 DRY RUN MODE - No changes will be made')
            else:
                click.echo('⚠️  EXECUTE MODE - Changes will be made to Gmail')
            counts = rm.cleanup_live(dry_run=dry_run, verbose=True)
            rm.print_kept_summary()
            if dry_run and counts.get('total', 0) > 0:
                click.echo(f"\n💡 To execute these actions, re-run without --dry-run")
            return

        if sync_db:
            click.echo('🧹 Syncing database with Gmail (removing orphaned emails)...')
            orphaned_count = rm.cleanup_orphaned_emails(verbose=True)
            if orphaned_count > 0:
                click.echo(f"\n✅ Cleaned up {orphaned_count} orphaned emails from database.")
                click.echo("💡 Re-run --analyze to see updated counts.")
            return

    except Exception as e:
        click.echo(f"❌ Error: {e}")




if __name__ == "__main__":
    main()