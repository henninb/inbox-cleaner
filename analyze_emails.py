#!/usr/bin/env python3
"""
AI-powered email analysis for spam detection and cleanup recommendations.

This script analyzes your extracted emails to identify:
- Spam and suspicious domains
- Newsletters to unsubscribe from
- Security risks (phishing, social engineering)
- Bulk cleanup opportunities

Usage:
    python analyze_emails.py --anthropic-key YOUR_KEY
    python analyze_emails.py --anthropic-key YOUR_KEY --save-report
"""

import argparse
import sys
import yaml
from pathlib import Path

from inbox_cleaner.database import DatabaseManager
from inbox_cleaner.ai_analyzer import AIEmailAnalyzer


def load_config():
    """Load configuration."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ config.yaml not found. Run setup_credentials.py first.")
        return None

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Main analysis function."""
    parser = argparse.ArgumentParser(
        description="AI-powered Gmail cleanup analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze_emails.py --anthropic-key sk-ant-...
    python analyze_emails.py --anthropic-key sk-ant-... --save-report
    python analyze_emails.py --anthropic-key sk-ant-... --domains-only

Privacy Notes:
    • No email content is sent to AI
    • Only domain patterns and subject lines are analyzed
    • Email addresses are never shared (they're hashed locally)
        """
    )

    parser.add_argument(
        '--anthropic-key',
        required=True,
        help='Anthropic API key (starts with sk-ant-...)'
    )

    parser.add_argument(
        '--save-report',
        action='store_true',
        help='Save analysis report to file'
    )

    parser.add_argument(
        '--domains-only',
        action='store_true',
        help='Show only domain analysis without AI recommendations'
    )

    args = parser.parse_args()

    print("🎯 Gmail Inbox AI Analysis")
    print("=" * 40)
    print()

    # Load configuration
    config = load_config()
    if not config:
        sys.exit(1)

    # Initialize database
    db_path = config['database']['path']
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("💡 Extract emails first: python real_demo.py --extract 100")
        sys.exit(1)

    db_manager = DatabaseManager(db_path)
    stats = db_manager.get_statistics()
    total_emails = stats.get('total_emails', 0)

    if total_emails == 0:
        print("❌ No emails in database")
        print("💡 Extract emails first: python real_demo.py --extract 100")
        sys.exit(1)

    print(f"📧 Found {total_emails} emails in database")
    print()

    if args.domains_only:
        # Just show domain statistics
        print("🌐 TOP EMAIL DOMAINS:")
        domain_stats = db_manager.get_domain_statistics()

        for i, (domain, count) in enumerate(list(domain_stats.items())[:20], 1):
            percentage = (count / total_emails) * 100
            print(f"  {i:2}. {domain:30} {count:4} emails ({percentage:4.1f}%)")

        print()
        print("💡 Run with --anthropic-key for AI analysis of these domains")
        return

    # Validate API key format
    if not args.anthropic_key.startswith('sk-ant-'):
        print("❌ Invalid Anthropic API key format")
        print("💡 API key should start with 'sk-ant-'")
        print("🔗 Get your API key at: https://console.anthropic.com/")
        sys.exit(1)

    # Initialize AI analyzer
    try:
        analyzer = AIEmailAnalyzer(args.anthropic_key, db_manager)
        print("🤖 AI analyzer initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize AI analyzer: {e}")
        sys.exit(1)

    # Perform analysis
    try:
        print("🔍 Analyzing email patterns...")
        print("🤖 Getting AI recommendations...")
        print("📊 Generating cleanup report...")
        print()
        print("⏳ This may take 30-60 seconds...")
        print()

        report, recommendations = analyzer.full_analysis()

        # Display report
        print(report)

        # Save report if requested
        if args.save_report:
            report_file = f"gmail_cleanup_report.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"\n💾 Report saved to: {report_file}")

        # Show next steps
        print("\n🚀 NEXT STEPS:")
        print("1. Review the recommendations above")
        print("2. Start with high-confidence spam domains")
        print("3. Manually verify suspicious domains in Gmail")
        print("4. Use Gmail's unsubscribe links for newsletters")
        print("5. Consider setting up Gmail filters for future cleanup")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        print()
        print("🔧 Troubleshooting:")
        print("• Check your Anthropic API key")
        print("• Ensure you have internet connection")
        print("• Try with fewer emails first")
        sys.exit(1)


if __name__ == '__main__':
    main()