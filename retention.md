# Retention Cleanup Architecture

## Overview

The retention cleanup process is designed to be a robust, configurable, and reliable way to manage email retention policies directly with Gmail. It uses a rule-based system defined in `config.yaml` to identify and clean up old emails, without relying on a local database.

## Goals

1.  **Single robust cleanup process** using live Gmail search.
2.  **File-based configuration** integrated into `config.yaml`.
3.  **Domain-specific retention periods** configurable per domain.
4.  **Pure Gmail-based reporting** (no DB dependency).
5.  **TDD implementation** with comprehensive test coverage.

## New Architecture

### Configuration File Format (in `config.yaml`)

Retention rules are defined in the main `config.yaml` file under the `retention_rules` key.

```yaml
# In config.yaml
retention_rules:
  - domain: "usps.com"
    retention_days: 7
    description: "USPS delivery notifications"

  - domain: "hulumail.com"
    retention_days: 14
    description: "Hulu marketing emails"

  - sender: "no-reply@spotify.com"
    retention_days: 30
    description: "Spotify notifications"

  - sender: "support@privacy.com"
    retention_days: 60
    description: "Privacy.com support"

  - domain: "accounts.google.com"
    retention_days: 90
    subject_contains: ["security alert", "sign-in"]
    description: "Google security alerts"

  - sender: "veteransaffairs@messages.va.gov"
    retention_days: 365
    description: "Veterans Affairs communications"
```

### New Command Structure

```bash
# Single cleanup command using rules from the default config.yaml
python -m inbox_cleaner.cli retention --cleanup

# Override retention for specific domains (comma-separated list)
python -m inbox_cleaner.cli retention --cleanup --override "usps.com:3,spotify.com:14"

# Use a non-default config file
python -m inbox_cleaner.cli retention --cleanup --config /path/to/other_config.yaml

# Analysis only
python -m inbox_cleaner.cli retention --analyze
```

### Design Decisions

1.  **Config File**: Retention rules are integrated into the main `config.yaml` file under the `retention_rules` key.
2.  **Override Syntax**: The command-line override syntax is `--override "usps.com:7,spotify.com:14"`.
3.  **Default Retention**: If a retention period is not specified for a rule, it defaults to **30 days**.
4.  **Default Rules**: The existing hardcoded domains are migrated to become the default rule set in the `config.yaml.example` file.

## Benefits of New Approach

1.  **Reliability**: No DB sync issues - works directly with Gmail.
2.  **Flexibility**: Easy to add/modify retention rules via `config.yaml`.
3.  **Performance**: Batch operations handle large volumes efficiently.
4.  **Maintainability**: Clean separation of config and logic.
5.  **Testability**: Pure functions are easy to test with TDD.
6.  **User-Friendly**: Clear configuration format, no hardcoded values.

## Features

-   [x] Single `retention --cleanup` command that's more robust than the current implementation.
-   [x] File-based configuration in `config.yaml` is working correctly.
-   [x] Domain-specific retention periods are configurable.
-   [x] No dependency on the local database for cleanup operations.
-   [x] All new functionality is covered by TDD tests.
-   [x] User documentation (`README.md`, `config.yaml.example`) is clear and updated.
