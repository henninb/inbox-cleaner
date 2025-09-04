# Inbox Cleaner (Gmail)

Privacy‑focused Gmail inbox management with local storage, rich CLI, and strong test coverage. No email content leaves your machine.

## Highlights

- Extracts privacy‑safe metadata (domains, subjects, dates, labels)
- Stores locally in SQLite (`inbox_cleaner.db`)
- Robust CLI for sync, spam cleanup, retention, and utilities
- OAuth2 authentication with refresh; credentials never leave your device
- Test suite with ≥90% coverage gate

## Privacy Guarantees

- No email content sent externally
- Email addresses can be hashed using SHA‑256 (privacy‑safe)
- All data is stored locally (SQLite)
- OAuth2 flows only against Google APIs

## Project Structure

```
inbox-cleaner/
├── inbox_cleaner/
│   ├── auth.py                 # OAuth2 authentication
│   ├── extractor.py            # Gmail metadata extraction
│   ├── database.py             # SQLite DB manager
│   ├── cli.py                  # CLI entry point (inbox-cleaner)
│   ├── retention.py            # Retention manager and config
│   ├── retention_manager.py    # Retention helpers
│   ├── spam_rules.py           # Spam rule engine
│   ├── spam_filters.py         # Spam filter manager
│   ├── cleanup_engine.py       # Unsubscribe/delete workflows
│   ├── sync.py                 # Synchronizer (Gmail ↔ DB)
│   └── web.py                  # Dev web server (optional)
├── tests/                      # Pytest suite
├── config.yaml.example         # Copy to config.yaml
├── setup_credentials.py        # OAuth local setup wizard
├── real_demo.py                # Demo script (optional)
├── demo.py                     # Mock demo (optional)
├── pyproject.toml              # Packaging and entry point
└── README.md
```

## Install (Dev)

```bash
pip install -e .[dev]
```

## Configuration

1) Create `config.yaml` from the example template:

```bash
cp config.yaml.example config.yaml
```

2) Run OAuth setup (desktop flow or web server flow) to populate credentials:

```bash
python setup_credentials.py
```

This configures Gmail OAuth and writes client settings into `config.yaml`. Your tokens are stored securely (e.g., OS keyring).

## CLI Usage

Entry point: `inbox-cleaner` (configured in `pyproject.toml`).

```bash
inbox-cleaner --help
```

### Auth

```bash
inbox-cleaner auth --setup           # interactive authentication
inbox-cleaner auth --status          # show status
inbox-cleaner auth --logout          # clear credentials
inbox-cleaner auth --device-flow     # device flow (desktop OAuth client)
inbox-cleaner auth --web-server      # temporary local web server flow
```

### Sync

```bash
inbox-cleaner sync --initial                 # initial sync from Gmail
inbox-cleaner sync --limit 500               # limit synced messages
inbox-cleaner sync --with-progress           # show progress
inbox-cleaner sync --fast                    # minimal output
```

### Filters and Unsubscribe

```bash
inbox-cleaner list-filters                   # list existing Gmail filters
inbox-cleaner apply-filters --dry-run        # default behavior (no changes)
inbox-cleaner apply-filters --execute        # apply auto-delete filters
inbox-cleaner find-unsubscribe --domain example.com
```

### Spam Cleanup and Rules

```bash
# Analyze emails in DB for spam patterns
inbox-cleaner spam-cleanup --analyze --limit 1000

# Create predefined spam rules file
inbox-cleaner spam-cleanup --setup-rules

# Create Gmail filters based on detected spam domains
inbox-cleaner create-spam-filters --create-filters --dry-run
inbox-cleaner create-spam-filters --create-filters

# Update config.yaml with retention rules for spam domains
inbox-cleaner create-spam-filters --update-config --dry-run
inbox-cleaner create-spam-filters --update-config
```

### Mark as Read

```bash
inbox-cleaner mark-read                      # dry-run by default
inbox-cleaner mark-read --query "from:news@site.com is:unread" --execute
inbox-cleaner mark-read --batch-size 300 --limit 1000
```

### Retention

```bash
inbox-cleaner retention --analyze
inbox-cleaner retention --cleanup --dry-run
inbox-cleaner retention --cleanup --override "usps.com:7,spotify.com:14"
inbox-cleaner retention --cleanup --show-retained
```

### Web (Development)

```bash
inbox-cleaner web --start --host 127.0.0.1 --port 8000
```

### Status

```bash
inbox-cleaner status
```

## CLI Options

Below is a quick reference of CLI options per command.

### auth

| Option          | Type        | Default | Description                                                   |
|-----------------|-------------|---------|---------------------------------------------------------------|
| `--setup`       | flag        | false   | Perform interactive authentication and save credentials.      |
| `--status`      | flag        | false   | Show authentication status.                                   |
| `--logout`      | flag        | false   | Clear stored credentials (keyring and file).                  |
| `--device-flow` | flag        | false   | Use device flow (requires a desktop OAuth client).            |
| `--web-server`  | flag        | false   | Use a temporary local web server for authentication.          |

### sync

| Option            | Type        | Default | Description                                                   |
|-------------------|-------------|---------|---------------------------------------------------------------|
| `--initial`       | flag        | false   | Initial sync (Gmail as source of truth).                      |
| `--batch-size`    | int         | 1000    | Batch size for processing (internal extraction).              |
| `--with-progress` | flag        | false   | Show progress updates.                                        |
| `--limit`         | int         | None    | Limit the number of emails to sync.                           |
| `--fast`          | flag        | false   | Minimal output; focus on high‑level progress.                 |

### list-filters

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| —      | —    | —       | Lists existing Gmail filters. |

### apply-filters

| Option       | Type | Default | Description                                       |
|--------------|------|---------|---------------------------------------------------|
| `--dry-run`  | flag | true    | Preview actions; no changes made (default mode).  |
| `--execute`  | flag | false   | Apply auto‑delete filters and delete matching email. |

Note: If neither `--dry-run` nor `--execute` is provided, the command defaults to dry‑run.

### find-unsubscribe

| Option      | Type   | Default | Description                                 |
|-------------|--------|---------|---------------------------------------------|
| `--domain`  | string | —       | Domain to search for unsubscribe links (req). |

### spam-cleanup

| Option          | Type | Default | Description                                        |
|-----------------|------|---------|----------------------------------------------------|
| `--analyze`     | flag | true*   | Analyze emails in DB for spam patterns.            |
| `--setup-rules` | flag | false   | Create and save predefined spam rules file.        |
| `--dry-run`     | flag | false   | Preview deletion based on spam rules.              |
| `--execute`     | flag | false   | Delete emails matching active spam rules.          |
| `--limit`       | int  | 1000    | Limit number of emails to analyze/process.         |

*If no flags are provided, `--analyze` is assumed by default.

### create-spam-filters

| Option              | Type | Default | Description                                                  |
|---------------------|------|---------|--------------------------------------------------------------|
| `--analyze`         | flag | true*   | Run analysis of DB to identify spam domains.                 |
| `--create-filters`  | flag | false   | Create Gmail filters for detected spam domains.              |
| `--update-config`   | flag | false   | Write retention rules for spam domains into `config.yaml`.   |
| `--dry-run`         | flag | false   | Preview actions (filters/config changes) without applying.   |

*If no action flags are provided, `--analyze` runs by default.

### mark-read

| Option                   | Type   | Default                  | Description                                                      |
|--------------------------|--------|--------------------------|------------------------------------------------------------------|
| `--query`                | string | None                     | Gmail search query (default selects all unread).                  |
| `--batch-size`           | int    | 500                      | Batch size for API calls (clamped to 1..500).                     |
| `--limit`                | int    | None                     | Optional maximum messages to process.                             |
| `--inbox-only`           | flag   | false                    | Restrict default query to Inbox only.                             |
| `--include-spam-trash`   | flag   | false                    | Include Spam/Trash in default query.                              |
| `--execute`              | flag   | false                    | Apply changes (otherwise dry‑run prints what would be changed).   |

### retention

| Option            | Type         | Default | Description                                                            |
|-------------------|--------------|---------|------------------------------------------------------------------------|
| `--analyze`       | flag         | true*   | Analyze retention candidates (default action).                          |
| `--cleanup`       | flag         | false   | Delete emails according to retention rules.                             |
| `--config`        | path (exist) | None    | Use an alternate `config.yaml` file.                                    |
| `--override`      | string       | None    | Override rules like `"usps.com:7,spotify.com:14"`.                     |
| `--dry-run`       | flag         | false   | Preview cleanup without deleting.                                      |
| `--show-retained` | flag         | false   | After cleanup, show retained emails under the policy.                   |

*If neither `--analyze` nor `--cleanup` is provided, `--analyze` is assumed.

### web

| Option     | Type   | Default       | Description                            |
|------------|--------|---------------|----------------------------------------|
| `--start`  | flag   | false         | Start the development web interface.   |
| `--host`   | string | 127.0.0.1     | Host interface to bind.                |
| `--port`   | int    | 8000          | Port to bind.                          |

### status

| Option | Type | Default | Description               |
|--------|------|---------|---------------------------|
| —      | —    | —       | Prints overall status.    |

## Gmail API Setup (Summary)

1) Create a Google Cloud project and enable the Gmail API
2) Configure the OAuth Consent Screen (External) and add yourself as a Test User
3) Create OAuth client credentials (Desktop Application)
4) Run `python setup_credentials.py` and follow prompts

That’s it — your `config.yaml` will be updated and credentials stored securely.

## 🚨 Common Setup Issues & Solutions

### Issue: "Gmail API has not been used in project before or it is disabled"

**Cause**: Gmail API not enabled (Step 2 skipped)

**Solution**:
1. Go to: https://console.cloud.google.com/
2. Select your project
3. Go to APIs & Services → Library
4. Search "Gmail API" → Click it → Click "ENABLE"
5. Wait 2-3 minutes for propagation

### Issue: "Access blocked: Authorization Error - OAuth client was not found"

**Cause**: Wrong credentials or client type

**Solutions**:
- Verify Client ID ends with `.apps.googleusercontent.com`
- Verify Client Secret starts with `GOCSPX-`
- Ensure you selected "Desktop application" not "Web application"
- Check you're using the same Google account for GCP and Gmail

### Issue: "Access blocked: inbox-cleaner has not completed the Google verification process"

**Cause**: Your email not added as test user

**Solution**:
1. Go to OAuth consent screen in Google Cloud Console
2. Scroll to "Test users" section
3. Click "ADD USERS"
4. Add your Gmail address
5. Click "SAVE"

### Issue: "This app isn't verified" warning

**This is normal for personal projects**

**Solution**:
- Click "Advanced"
- Click "Go to Gmail Inbox Cleaner (unsafe)"
- This warning appears because you haven't submitted for Google verification (not needed for personal use)

### Issue: "No emails found" after successful authentication

**Possible causes**:
1. Gmail API not enabled (most common)
2. Wrong Google account authenticated
3. Empty Gmail account
4. API propagation delay

**Solution**:
```bash
python direct_test.py  # This will show the exact error
```

## 💡 Pro Tips

1. **Use the same Google account** for GCP setup and Gmail access
2. **Wait 2-3 minutes** after enabling Gmail API before testing
3. **Keep your config.yaml secure** - it contains your API credentials
4. **The free tier is sufficient** - Gmail API readonly access is free with 1 billion requests/day limit

## 🖥️ Usage

### Extract Emails
```bash
# Extract 50 recent emails
python real_demo.py --extract 50

# Extract with progress tracking
python real_demo.py --extract 1000
```

### View Statistics
```bash
python real_demo.py --stats
```

Example output:
```
📊 Email Analysis Results
========================================
📧 Total emails analyzed: 1,250
🏷️ Email Categories:
   newsletter: 420
   personal: 380
   work: 310
   social: 140

🌐 Top Email Domains:
   github.com: 45 emails
   linkedin.com: 38 emails
   amazon.com: 32 emails

💡 Cleanup Suggestions:
   📢 420 promotional emails could be archived
   👥 140 social emails could be organized
   📰 12 domains with 5+ emails (potential newsletters)
```

### Test Authentication
```bash
python real_demo.py --auth
```

## 🏗️ Architecture

### Core Modules (✅ Complete)

1. **Authentication** (`inbox_cleaner/auth.py`)
   - OAuth2 flow with Google
   - Secure credential storage (keyring)
   - Automatic token refresh

2. **Email Extraction** (`inbox_cleaner/extractor.py`)
   - Gmail API integration
   - Privacy-focused metadata extraction
   - Batch processing with progress tracking
   - Email content analysis (local only)

3. **Database** (`inbox_cleaner/database.py`)
   - SQLite storage with proper indexing
   - Optimized for large datasets (40k+ emails)
   - Full-text search capabilities
   - Statistics and analytics

### Future Modules (🚧 Planned)

4. **AI Interface** - Anthropic Claude integration for recommendations
5. **Web Dashboard** - FastAPI interface for reviewing actions
6. **Action Engine** - Execute cleanup actions (delete, label, archive)

## Development & Testing

Common workflow:

```bash
pip install -e .[dev]

# Format, lint, type-check
black .
flake8 inbox_cleaner tests
mypy inbox_cleaner

# Run tests
pytest -m "not slow" --cov=inbox_cleaner --cov-report=term-missing
```

Notes:
- Coverage gate is set to 90% (mirrored locally via pytest.ini)
- Pytest marks available: `unit`, `integration`, `slow`

## ⚙️ Configuration

Edit `config.yaml` (created by `setup_credentials.py`):

```yaml
gmail:
  client_id: "your-client-id.googleusercontent.com"
  client_secret: "your-client-secret"
  scopes:
    - "https://www.googleapis.com/auth/gmail.readonly"

database:
  path: "./inbox_cleaner.db"

app:
  batch_size: 1000              # Emails per batch
  max_emails_per_run: 5000      # Safety limit
```

## Security Notes

- Never commit real `config.yaml` or tokens — use `config.yaml.example` as a template
- OAuth tokens are stored in the OS keyring (Keychain/Credential Manager/Secret Service)
- Email data is metadata-only and stored locally in SQLite
- Optional hashing (SHA‑256) preserves privacy where required

## Troubleshooting

Authentication failed
- Verify Client ID/Secret and OAuth client type (Desktop)
- Ensure Gmail API is enabled in Google Cloud Console
- Re-run `inbox-cleaner auth --setup`

No emails found
- Double-check Gmail API enablement and that you authenticated the right account
- Try a small limit first (e.g., `--limit 5`) and check logs

Database errors
- Check permissions for the database path
- Ensure the directory exists or adjust `database.path` in `config.yaml`

## Roadmap

- [x] Core architecture (auth, extraction, DB)
- [x] Privacy protection (hashing, local‑only storage)
- [x] Batch processing and sync
- [x] Comprehensive tests with coverage gate
- [ ] Web interface enhancements
- [ ] AI‑assisted cleanup recommendations

## Contributing

We aim for a small, testable surface area with clear interfaces.

General guidance:
- Prefer small, focused functions with type hints
- Keep modules inside `inbox_cleaner/`
- Write or update tests alongside changes; keep CI green (lint, type, tests)

Run locally:
```bash
black . && flake8 inbox_cleaner tests && mypy inbox_cleaner
pytest --cov=inbox_cleaner
```

## 📄 License

MIT License - see LICENSE file for details.

## ⚡ Performance Notes

**Tested with 40,000+ emails:**
- ✅ Extraction: ~2-3 emails/second (Gmail API rate limits)
- ✅ Database storage: ~1000 emails/second batch insert
- ✅ Analysis: Sub-second query performance
- ✅ Memory usage: <100MB for large datasets
