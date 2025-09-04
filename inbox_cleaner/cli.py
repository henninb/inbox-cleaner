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
from .spam_filters import SpamFilterManager
from .retention import GmailRetentionManager, RetentionConfig
from .sync import GmailSynchronizer


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
@click.option('--fast', is_flag=True, help='Fast mode: sync in background and show progress summary')
def sync(initial, batch_size, with_progress, limit, fast):
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

        # Initialize extractor, database, and synchronizer
        extractor = GmailExtractor(service, batch_size=batch_size)

        with DatabaseManager(db_path) as db:
            synchronizer = GmailSynchronizer(service, db, extractor)

            if initial:
                click.echo(f"📥 Starting initial sync with Gmail as source of truth...")
                if limit:
                    click.echo(f"📊 Limited to {limit} emails")
            else:
                click.echo("📥 Syncing with Gmail (true bi-directional sync)...")

            def progress_callback(operation: str, current: int, total: int) -> None:
                if with_progress and not fast:
                    percentage = (current / total) * 100 if total > 0 else 0
                    click.echo(f"{operation}: {percentage:.1f}% ({current}/{total})", nl=False)
                    click.echo("\r", nl=False)
                elif fast and "batch" in operation.lower():
                    # In fast mode, only show batch progress
                    click.echo(f"⚡ {operation}")

            if fast:
                click.echo("⚡ Fast mode enabled - sync will run efficiently with minimal output")

            try:
                # Perform true sync
                result = synchronizer.sync(
                    query="",  # Empty query to sync all emails
                    max_results=limit,  # Pass limit directly to sync method
                    progress_callback=progress_callback if with_progress else None
                )

                if with_progress:
                    click.echo()  # New line after progress

                # Show sync results
                if result.get('error'):
                    click.echo(f"⚠️  Sync completed with warnings: {result['error']}")
                else:
                    click.echo("✅ Sync completed successfully")

                click.echo(f"📊 Sync results:")
                click.echo(f"  • Added: {result['added']} new emails")
                click.echo(f"  • Removed: {result['removed']} deleted emails")

                # Show final database stats
                stats = db.get_statistics()
                click.echo(f"📈 Database now contains {stats['total_emails']} emails")

                # Validate sync if no errors
                if not result.get('error'):
                    click.echo("\n🔍 Validating sync...")
                    validation = synchronizer.validate_sync(query="", max_results=limit)
                    if validation['in_sync']:
                        click.echo("✅ Database is perfectly synced with Gmail")
                    else:
                        click.echo(f"⚠️  Sync validation found differences:")
                        click.echo(f"  • Gmail: {validation['gmail_count']} emails")
                        click.echo(f"  • Database: {validation['db_count']} emails")

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

        # Check for duplicate filters
        from .spam_filters import SpamFilterManager
        spam_filter_manager = SpamFilterManager(db_manager)
        duplicates = spam_filter_manager.identify_duplicate_filters(filters)

        if duplicates:
            click.echo("⚠️  DUPLICATE FILTERS FOUND:")
            click.echo()
            for duplicate_group in duplicates:
                criteria = duplicate_group['criteria']
                duplicate_filters = duplicate_group['filters']

                # Show the criteria that's duplicated
                criteria_desc = []
                if 'from' in criteria:
                    criteria_desc.append(f"From: {criteria['from']}")
                if 'to' in criteria:
                    criteria_desc.append(f"To: {criteria['to']}")
                if 'subject' in criteria:
                    criteria_desc.append(f"Subject: {criteria['subject']}")
                if 'query' in criteria:
                    criteria_desc.append(f"Query: {criteria['query']}")

                criteria_text = ", ".join(criteria_desc) if criteria_desc else str(criteria)
                click.echo(f"   🔍 Duplicate criteria: {criteria_text}")
                click.echo(f"   📄 Found in {len(duplicate_filters)} filters:")

                for dup_filter in duplicate_filters:
                    filter_id = dup_filter.get('id', 'unknown')[:15]
                    click.echo(f"      • Filter ID: {filter_id}...")
                click.echo()
        else:
            click.echo("✅ No duplicate filters found")
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
@click.option('--analyze', is_flag=True, help='Analyze database for spam patterns (default)')
@click.option('--create-filters', is_flag=True, help='Create Gmail filters for spam domains')
@click.option('--update-config', is_flag=True, help='Update config.yaml with retention rules')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes')
def create_spam_filters(analyze, create_filters, update_config, dry_run):
    """Automatically detect spam patterns and create filtering rules."""

    if not any([analyze, create_filters, update_config]):
        analyze = True  # Default action

    try:
        # Load configuration
        config_path = Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found. Please create it from config.yaml.example")
            return

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        db_path = config['database']['path']
        gmail_config = config['gmail']

        # Initialize database and spam filter manager
        db_manager = DatabaseManager(db_path)
        spam_filter_manager = SpamFilterManager(db_manager)

        if analyze:
            click.echo("🔍 Analyzing emails for spam patterns...")

            # Perform comprehensive spam analysis
            spam_report = spam_filter_manager.analyze_spam()

            if spam_report['total_spam'] == 0:
                click.echo("✅ No spam emails detected in database")
                return

            click.echo(f"\n📊 Spam Analysis Results:")
            click.echo(f"  • Total spam emails: {spam_report['total_spam']}")
            click.echo(f"  • Unique spam domains: {len(spam_report['spam_domains'])}")

            # Show spam categories
            if spam_report['categories']:
                click.echo(f"\n📋 Spam Categories:")
                for category, count in spam_report['categories'].items():
                    click.echo(f"  • {category}: {count} emails")

            # Show most problematic domains
            domain_counts = {}
            for email in spam_report['spam_emails']:
                domain = email['domain']
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

            if domain_counts:
                click.echo(f"\n🎯 Top Spam Domains:")
                sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
                for domain, count in sorted_domains[:10]:
                    click.echo(f"  • {domain}: {count} emails")

            if create_filters or update_config:
                click.echo(f"\nTo create filters: --create-filters")
                click.echo(f"To update config: --update-config")

        if create_filters:
            # Need authentication for creating Gmail filters
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

            click.echo("🛡️  Creating Gmail filters for spam domains...")

            # Get spam domains
            spam_domains = set(spam_filter_manager.identify_spam_domains())
            gmail_filters = spam_filter_manager.create_gmail_filters(spam_domains)

            if not gmail_filters:
                click.echo("✅ No spam filters to create")
                return

            if dry_run:
                click.echo(f"💡 DRY RUN - Would create {len(gmail_filters)} Gmail filters:")
                for filter_config in gmail_filters[:10]:  # Show first 10
                    criteria = filter_config['criteria']
                    if 'from' in criteria:
                        click.echo(f"  • Auto-delete from: {criteria['from']}")
                    elif 'subject' in criteria:
                        click.echo(f"  • Auto-delete subject: {criteria['subject']}")

                if len(gmail_filters) > 10:
                    click.echo(f"  ... and {len(gmail_filters) - 10} more")

                click.echo("Re-run without --dry-run to create filters")
                return

            # Create filters in Gmail
            created_count = 0
            failed_count = 0

            # Get existing filters to avoid duplicates
            existing = service.users().settings().filters().list(userId='me').execute()
            existing_filters = existing.get('filter', [])

            # Use proper duplicate detection
            non_duplicate_filters = spam_filter_manager.filter_out_duplicates(gmail_filters, existing_filters)

            duplicates_skipped = len(gmail_filters) - len(non_duplicate_filters)
            if duplicates_skipped > 0:
                click.echo(f"⏭️  Skipped {duplicates_skipped} duplicate filters")

            for filter_config in non_duplicate_filters:
                try:
                    service.users().settings().filters().create(
                        userId='me',
                        body={
                            'criteria': filter_config['criteria'],
                            'action': filter_config['action']
                        }
                    ).execute()
                    created_count += 1

                except Exception as e:
                    click.echo(f"❌ Failed to create filter: {e}")
                    failed_count += 1

            click.echo(f"✅ Created {created_count} Gmail filters")
            if failed_count > 0:
                click.echo(f"⚠️  Failed to create {failed_count} filters")

        if update_config:
            click.echo("📝 Updating config.yaml with spam retention rules...")

            # Generate retention rules
            spam_domains = set(spam_filter_manager.identify_spam_domains())
            retention_rules = spam_filter_manager.generate_retention_rules(spam_domains)

            if not retention_rules:
                click.echo("✅ No spam retention rules to add")
                return

            if dry_run:
                click.echo(f"💡 DRY RUN - Would add {len(retention_rules)} retention rules:")
                for rule in retention_rules[:10]:
                    click.echo(f"  • {rule['domain']}: {rule['retention_days']} days ({rule['description']})")

                if len(retention_rules) > 10:
                    click.echo(f"  ... and {len(retention_rules) - 10} more")

                click.echo("Re-run without --dry-run to update config")
                return

            # Save retention rules to config
            spam_filter_manager.save_filters_to_config(str(config_path), retention_rules)

            click.echo(f"✅ Added {len(retention_rules)} spam retention rules to config.yaml")
            click.echo("📋 Rules added for immediate deletion (0 days retention)")

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
@click.option('--cleanup', is_flag=True, help='Delete old emails based on retention rules')
@click.option('--config', 'config_path_override', type=click.Path(exists=True), help='Path to a custom config.yaml file')
@click.option('--override', help='Override retention days for specific rules, e.g., "usps.com:7,spotify.com:14"')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes')
@click.option('--show-retained', is_flag=True, help='Show retained emails after cleanup operations')
def retention(analyze, cleanup, config_path_override, override, dry_run, show_retained):
    """Configurable, rule-based email retention manager."""
    try:
        if not any([analyze, cleanup]):
            analyze = True  # Default action

        # Load configuration
        config_path = Path(config_path_override) if config_path_override else Path("config.yaml")
        if not config_path.exists():
            click.echo("❌ Error: config.yaml not found.")
            return

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        # Parse overrides
        overrides_dict = {}
        if override:
            for item in override.split(','):
                domain, days = item.split(':')
                overrides_dict[domain.strip()] = int(days.strip())

        gmail_config = config_data.get('gmail', {})
        retention_config = RetentionConfig(config_data, overrides=overrides_dict)
        manager = GmailRetentionManager(retention_config, gmail_config)

        if analyze:
            click.echo("📊 Analyzing email retention based on rules...")
            analysis_results = manager.analyze_retention()
            total_found = sum(res.messages_found for res in analysis_results.values())
            click.echo(f"Found {total_found} emails matching retention rules.")
            for key, result in analysis_results.items():
                click.echo(f"  - {key}: {result.messages_found} emails found")

        if cleanup:
            if dry_run:
                click.echo('💡 DRY RUN MODE - No changes will be made')
            else:
                click.echo('⚠️  EXECUTE MODE - Changes will be made to Gmail')

            analysis_results = manager.analyze_retention()
            cleanup_summary = manager.cleanup_old_emails(analysis_results, dry_run=dry_run)

            total_cleaned = sum(cleanup_summary.values())
            click.echo(f"✅ Cleaned up {total_cleaned} emails.")
            for key, count in cleanup_summary.items():
                click.echo(f"  - {key}: {count} emails removed")

            # Show retained emails if requested
            if show_retained:
                click.echo("\n" + "="*50)
                click.echo("📋 Retained emails (emails being kept under retention policy):")
                retained_results = manager.analyze_retained_emails()
                manager.print_retained_emails(retained_results)

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@main.command('cleanup-filters')
@click.option('--dry-run', is_flag=True, help='Preview actions without making changes (default)')
@click.option('--execute', is_flag=True, help='Actually perform cleanup operations')
@click.option('--optimize', is_flag=True, help='Include filter optimization (merge similar domain filters)')
def cleanup_filters(dry_run, execute, optimize):
    """Remove duplicates and optimize existing Gmail filters."""

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

        click.echo("🧹 Analyzing existing filters for cleanup opportunities...")

        # Get existing filters
        filters = unsubscribe_engine.list_existing_filters()

        if not filters:
            click.echo("✅ No filters found to clean up")
            return

        # Initialize spam filter manager for analysis
        from .spam_filters import SpamFilterManager
        spam_filter_manager = SpamFilterManager(db_manager)

        # Find duplicates
        duplicates = spam_filter_manager.identify_duplicate_filters(filters)

        # Find optimization opportunities
        optimizations = spam_filter_manager.optimize_filters(filters)

        # Report findings
        if duplicates:
            click.echo(f"🔍 Found {len(duplicates)} duplicate filter groups:")
            duplicate_count = 0
            for duplicate_group in duplicates:
                criteria = duplicate_group['criteria']
                duplicate_filters = duplicate_group['filters']

                # Show criteria
                criteria_desc = []
                if 'from' in criteria:
                    criteria_desc.append(f"From: {criteria['from']}")
                if 'to' in criteria:
                    criteria_desc.append(f"To: {criteria['to']}")
                if 'subject' in criteria:
                    criteria_desc.append(f"Subject: {criteria['subject']}")

                criteria_text = ", ".join(criteria_desc) if criteria_desc else str(criteria)
                click.echo(f"  • {criteria_text} ({len(duplicate_filters)} filters)")
                duplicate_count += len(duplicate_filters) - 1  # Keep one, remove others
        else:
            duplicate_count = 0

        if optimizations:
            click.echo(f"🎯 Found {len(optimizations)} optimization opportunities:")
            for opt in optimizations:
                if opt['type'] == 'consolidate_domain':
                    click.echo(f"  • {opt['description']}")

        # Summary
        click.echo(f"\n📊 Summary:")
        if dry_run:
            click.echo(f"  Would remove {duplicate_count} duplicate filters")
            if optimize:
                total_to_merge = sum(len(opt['filters_to_remove']) for opt in optimizations)
                click.echo(f"  Would apply {len(optimizations)} filter optimizations")
                click.echo(f"  Would merge {total_to_merge} filters into wildcard filters")
            else:
                click.echo(f"  Would optimize {len(optimizations)} filter groups (use --optimize to apply)")
        else:
            # Execute cleanup
            removed_count = 0

            # Remove duplicates (keep first filter in each group)
            for duplicate_group in duplicates:
                filters_to_remove = duplicate_group['filters'][1:]  # Keep first, remove rest
                for filter_to_remove in filters_to_remove:
                    filter_id = filter_to_remove.get('id')
                    if unsubscribe_engine.delete_filter(filter_id):
                        removed_count += 1
                    else:
                        click.echo(f"⚠️ Failed to remove filter {filter_id}")

            click.echo(f"  Removed {removed_count} duplicate filters")

            # Apply optimizations if requested
            if optimize and optimizations:
                click.echo(f"🔄 Applying {len(optimizations)} filter optimizations...")
                optimization_result = spam_filter_manager.apply_filter_optimizations(service, optimizations)

                if optimization_result['success']:
                    click.echo(f"  Applied {optimization_result['optimizations_applied']} filter optimizations")
                    click.echo(f"  Merged {optimization_result['total_merged']} filters into 1 wildcard filter")

                    if optimization_result['errors']:
                        click.echo(f"  ⚠️ {len(optimization_result['errors'])} optimizations failed")
                        for error in optimization_result['errors']:
                            click.echo(f"    • {error['optimization']}: {error['error']}")
                else:
                    click.echo(f"  ❌ Failed to apply optimizations")
            elif optimize:
                click.echo(f"  No filter optimizations available")
            else:
                if optimizations:
                    click.echo(f"  Found {len(optimizations)} optimization opportunities (use --optimize to apply)")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


@main.command('export-filters')
@click.option('--filename', default=None, help='Output filename (default: gmail_filters_TIMESTAMP.xml)')
def export_filters(filename):
    """Export Gmail filters to XML format for backup/restore."""

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

        # Get existing filters
        filters = unsubscribe_engine.list_existing_filters()

        click.echo(f"📥 Found {len(filters)} filters to export")

        # Generate filename if not provided
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gmail_filters_{timestamp}.xml"

        # Export to XML
        from .spam_filters import SpamFilterManager
        spam_filter_manager = SpamFilterManager(db_manager)
        xml_content = spam_filter_manager.export_filters_to_xml(filters)

        # Write to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        click.echo(f"✅ Exported {len(filters)} filters to {filename}")
        click.echo(f"💡 You can import this file in Gmail Settings > Filters and Blocked Addresses > Import filters")

    except Exception as e:
        click.echo(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
