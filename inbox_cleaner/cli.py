"""Command line interface for inbox cleaner."""

import click


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Gmail Inbox Cleaner - Privacy-focused email management with AI assistance."""
    pass


@main.command()
@click.option('--setup', is_flag=True, help='Set up OAuth2 authentication')
def auth(setup):
    """Manage authentication."""
    if setup:
        click.echo("Setting up OAuth2 authentication...")
        # TODO: Implement authentication setup
    else:
        click.echo("Authentication status...")
        # TODO: Implement authentication status check


@main.command()
@click.option('--initial', is_flag=True, help='Initial sync of all emails')
@click.option('--batch-size', default=1000, help='Batch size for processing')
@click.option('--with-progress', is_flag=True, help='Show progress bar')
def sync(initial, batch_size, with_progress):
    """Sync emails from Gmail."""
    if initial:
        click.echo(f"Starting initial sync with batch size {batch_size}...")
    else:
        click.echo("Syncing recent emails...")
    # TODO: Implement email sync


@main.command()
@click.option('--start', is_flag=True, help='Start web interface')
@click.option('--port', default=8000, help='Port for web interface')
def web(start, port):
    """Manage web interface."""
    if start:
        click.echo(f"Starting web interface on port {port}...")
        # TODO: Implement web interface startup
    else:
        click.echo("Web interface management...")


@main.command()
def diagnose():
    """Run diagnostic tool to troubleshoot issues."""
    click.echo("Running diagnostics...")
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


if __name__ == "__main__":
    main()