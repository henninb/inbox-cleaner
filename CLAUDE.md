# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Inbox Cleaner is a privacy-focused Gmail management tool with local SQLite storage and AI-assisted analysis. The project extracts email metadata (domains, subjects, labels) without storing email content, enabling safe spam cleanup and retention management.

## Development Commands

### Testing
```bash
# Run all tests with coverage (90% minimum required)
pytest

# Run tests excluding slow integration tests
pytest -m "not slow"

# Run specific test modules
pytest tests/test_auth.py -v
pytest tests/test_extractor.py -v

# Run with specific coverage reporting
pytest --cov=inbox_cleaner --cov-report=term-missing

# Timeout tests (useful for integration tests)
timeout 10s python -m pytest tests/test_integration.py -v
```

### Code Quality
```bash
# Format code (follows 88-character line length)
black .

# Lint code
flake8 inbox_cleaner tests

# Type checking
mypy inbox_cleaner
```

### Installation & Setup
```bash
# Development installation
pip install -e .[dev]

# Create config from template
cp config.yaml.example config.yaml

# Set up OAuth credentials (interactive)
python setup_credentials.py
```

### CLI Usage (Main Entry Point)
```bash
# Primary CLI tool (configured in pyproject.toml)
inbox-cleaner --help

# Authentication management
inbox-cleaner auth --setup
inbox-cleaner auth --status
inbox-cleaner auth --logout

# Email synchronization
inbox-cleaner sync --initial
inbox-cleaner sync --limit 500 --with-progress

# Spam and filter management
inbox-cleaner spam-cleanup --analyze --limit 1000
inbox-cleaner create-spam-filters --create-filters --dry-run
inbox-cleaner apply-filters --dry-run

# Retention management
inbox-cleaner retention --analyze
inbox-cleaner retention --cleanup --dry-run
```

## Architecture

### Core Modules
- **auth.py**: OAuth2 authentication with Google APIs, credential storage in OS keyring
- **extractor.py**: Gmail API integration, privacy-safe metadata extraction, batch processing
- **database.py**: SQLite manager with optimized schema for large datasets (40k+ emails)
- **cli.py**: Click-based command-line interface, main entry point
- **sync.py**: Synchronization between Gmail and local database
- **spam_rules.py**: Rule engine for spam detection and pattern matching
- **spam_filters.py**: Gmail filter creation and management
- **retention.py**: Email retention policies with configurable rules
- **cleanup_engine.py**: Unsubscribe and deletion workflows

### Database Schema
- Emails table with indexed fields (message_id, sender_domain, date, labels)
- Privacy features: SHA-256 hashing of email addresses, no content storage
- Optimized for analytics and filtering operations

### Configuration
- **config.yaml**: Main configuration (created from config.yaml.example)
- **gmail_credentials.json**: OAuth credentials (secured, not committed)
- **pytest.ini**: Test configuration with coverage requirements

## Development Patterns

### Error Handling
- AuthenticationError for OAuth failures
- Graceful degradation for API rate limits
- Comprehensive logging throughout

### Privacy & Security
- No email content extraction or storage
- Optional SHA-256 hashing of email addresses
- All data stored locally in SQLite
- OAuth credentials stored in OS keyring

### Testing Strategy
- Pytest with 90% coverage requirement
- Unit tests for core components
- Integration tests marked as "slow" (can be excluded)
- Mock usage for external API calls

### CLI Design
- Click framework with grouped commands
- Dry-run mode as default for destructive operations
- Progress indicators for long-running operations
- Comprehensive help text and examples

## Common Development Tasks

### Adding New Commands
1. Add command function in `cli.py` using `@main.command()` decorator
2. Import required modules at top of file
3. Follow existing patterns for error handling and configuration loading
4. Add corresponding tests in `tests/test_cli.py`

### Database Schema Changes
1. Update `database.py` with new schema
2. Consider migration path for existing databases
3. Update relevant test fixtures in `tests/conftest.py`
4. Test with large datasets

### API Integration
1. Follow patterns in `extractor.py` for Gmail API usage
2. Implement proper rate limiting and batch processing
3. Add comprehensive error handling
4. Mock external calls in tests

## Test Execution Notes
- Integration tests may require OAuth setup
- Use `timeout` wrapper for potentially long-running tests
- Coverage reports available in `htmlcov/` directory
- Tests can be run in parallel but database tests may need isolation