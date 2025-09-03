# Retention Cleanup Refactoring Plan

## Current State Analysis

### Existing Cleanup Methods

1. **`--cleanup`** (DB-based):
   - Uses `rm.cleanup_live()` method (confusing naming)
   - Searches Gmail live via API queries
   - More comprehensive coverage
   - Does NOT rely on local database for finding emails
   - Uses batch operations for efficiency

2. **`--cleanup-live`** (also DB-based):
   - Also uses `rm.cleanup_live()` method (identical implementation)
   - **DUPLICATE FUNCTIONALITY** - both options do the same thing!

### Key Findings

- **Both cleanup options are identical** - they both call `rm.cleanup_live()`
- The live Gmail search approach (`cleanup_live()`) is superior because:
  - ✅ No dependency on local database sync
  - ✅ Finds ALL emails in Gmail regardless of DB state
  - ✅ Uses efficient batch operations (500 emails at a time)
  - ✅ Handles pagination automatically
  - ✅ More robust for large cleanups
- The DB-based method (`cleanup_db()`) is inferior because:
  - ❌ Only finds emails that were previously synced to local DB
  - ❌ Misses emails if DB is outdated or incomplete
  - ❌ Single email operations (slower)

## Proposed Refactoring

### Goals
1. **Single robust cleanup process** using live Gmail search
2. **File-based configuration** instead of hardcoded domains
3. **Domain-specific retention periods** configurable per domain
4. **Pure Gmail-based reporting** (no DB dependency)
5. **TDD implementation** with comprehensive test coverage

### New Architecture

#### 1. Configuration File Format (`retention_config.yaml`)
```yaml
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

#### 2. New Command Structure
```bash
# Single cleanup command with file configuration
python -m inbox_cleaner.cli retention --cleanup --config retention_config.yaml

# Override retention for specific domains
python -m inbox_cleaner.cli retention --cleanup --config retention_config.yaml --override "usps.com:3"

# Analysis only (no DB dependency)
python -m inbox_cleaner.cli retention --analyze --config retention_config.yaml
```

#### 3. Implementation Plan

##### Phase 1: TDD Test Setup
- [ ] Write failing tests for configuration file parsing
- [ ] Write failing tests for Gmail query generation
- [ ] Write failing tests for live email discovery
- [ ] Write failing tests for batch cleanup operations
- [ ] Write failing tests for CLI integration

##### Phase 2: Core Implementation
- [ ] Create `RetentionConfig` class for file parsing
- [ ] Create `GmailRetentionManager` class (replace current)
- [ ] Implement live Gmail search with custom queries
- [ ] Implement batch cleanup operations
- [ ] Remove DB dependencies from cleanup process

##### Phase 3: CLI Integration
- [ ] Refactor CLI command to single `--cleanup` option
- [ ] Add `--config` parameter for file path
- [ ] Add `--override` parameter for runtime changes
- [ ] Remove deprecated `--cleanup-live` option
- [ ] Update help text and documentation

##### Phase 4: Testing & Validation
- [ ] Run all tests to ensure TDD compliance
- [ ] Test with real Gmail account (dry-run mode)
- [ ] Validate performance with large email volumes
- [ ] Ensure backward compatibility where possible

## Technical Implementation Details

### New Classes

#### `RetentionConfig`
```python
@dataclass
class RetentionRule:
    domain: Optional[str] = None
    sender: Optional[str] = None
    retention_days: int = 30
    subject_contains: Optional[List[str]] = None
    description: str = ""

class RetentionConfig:
    def load_from_file(self, path: str) -> List[RetentionRule]
    def generate_gmail_query(self, rule: RetentionRule) -> str
    def validate_rules(self, rules: List[RetentionRule]) -> bool
```

#### `GmailRetentionManager`
```python
class GmailRetentionManager:
    def __init__(self, config_path: str, overrides: Dict[str, int] = None)
    def analyze_retention(self) -> Dict[str, RetentionAnalysis]
    def cleanup_old_emails(self, dry_run: bool = True) -> Dict[str, int]
    def _build_queries(self) -> Dict[str, str]
    def _search_gmail_live(self, query: str) -> List[str]
    def _batch_cleanup(self, message_ids: List[str]) -> int
```

### Gmail Query Generation
```python
def generate_query(rule: RetentionRule) -> str:
    parts = []

    if rule.domain:
        parts.append(f"from:{rule.domain}")
    elif rule.sender:
        parts.append(f"from:{rule.sender}")

    if rule.subject_contains:
        subject_parts = [f'subject:"{term}"' for term in rule.subject_contains]
        parts.append(f"({' OR '.join(subject_parts)})")

    parts.append(f"older_than:{rule.retention_days}d")
    parts.append("-in:spam -in:trash")

    return " ".join(parts)
```

## Benefits of New Approach

1. **Reliability**: No DB sync issues - works directly with Gmail
2. **Flexibility**: Easy to add/modify retention rules via config file
3. **Performance**: Batch operations handle large volumes efficiently
4. **Maintainability**: Clean separation of config and logic
5. **Testability**: Pure functions easy to test with TDD
6. **User-Friendly**: Clear configuration format, no hardcoded values

## Migration Strategy

1. **Deprecation Warning**: Add warning for `--cleanup-live` usage
2. **Backward Compatibility**: Continue supporting old command temporarily
3. **Documentation**: Update README with new configuration format
4. **Example Config**: Provide sample `retention_config.yaml`
5. **Gradual Rollout**: Recommend new approach, support both during transition

## Questions for Clarification

1. **Config File Location**: Should the retention config be separate from `config.yaml` or integrated?
2. **Override Syntax**: Is `--override "domain:days"` format acceptable for command line overrides?
3. **Default Retention**: What should be the default retention period if not specified?
4. **Error Handling**: How should we handle Gmail API rate limits during large cleanups?
5. **Logging**: Do you want detailed logging of what emails are being processed/deleted?

## Success Criteria

- [ ] Single `--cleanup` command that's more robust than current implementation
- [ ] File-based configuration working correctly
- [ ] Domain-specific retention periods configurable
- [ ] No dependency on local database for cleanup operations
- [ ] All functionality covered by TDD tests
- [ ] Performance suitable for large email volumes
- [ ] Clear user documentation and examples



  Before I start the TDD implementation, please clarify:

  1. Config file format: Should I use a separate retention_config.yaml or integrate into existing config.yaml?
  2. Override syntax: Is this acceptable for command-line overrides?
  --override "usps.com:7,spotify.com:14"
  3. Default retention: What default retention period if not specified? (Currently hardcoded at 30 days)
  4. Example domains: Should I migrate your current hardcoded domains (USPS, Hulu, Spotify, etc.) as the default config file?
  5. Backward compatibility: Should I keep the old commands during transition with deprecation warnings?

  The plan is ready for TDD implementation once you provide these clarifications! 🚀

> update the plan again with adjustments based on my answers.  1. config.yaml 2. overrides are acceptable 3. 30 is the default retention 4. yes 5. yes
