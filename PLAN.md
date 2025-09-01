# Gmail Inbox Cleaner - Project Plan

## Overview
A privacy-focused Gmail inbox cleanup tool that extracts only metadata (no email content) and leverages AI assistance for intelligent inbox management while keeping sensitive data local.

## Core Principles
- **Privacy First**: No email body content ever leaves your machine
- **Metadata Only**: Extract sender, subject, date, labels, thread info
- **Human-in-the-Loop**: All actions require explicit user approval
- **Local Control**: All data processing happens on your local machine

## Architecture

### Technology Stack
- **Language**: Python 3.9+
- **Database**: SQLite (local storage)
- **Gmail Access**: Google API Client Library with OAuth2
- **Data Processing**: pandas, numpy
- **Web Interface**: FastAPI with HTML templates (primary interface)
- **CLI Interface**: Click (for batch operations)
- **AI Service**: Anthropic Claude API
- **Testing**: pytest with TDD approach
- **Content Analysis**: Local NLP processing (spaCy/nltk)

### Components

#### 1. Authentication Module (`auth.py`)
- OAuth2 flow implementation
- Token management and refresh
- Secure credential storage
- Gmail API client initialization

#### 2. Data Extraction Module (`extractor.py`)
- Fetch email metadata via Gmail API
- Extract: sender, subject, date, labels, thread_id, message_id
- Batch processing for large inboxes
- Rate limiting and error handling
- Local SQLite database storage

#### 3. Data Analysis Module (`analyzer.py`)
- Pattern recognition in senders/subjects
- Frequency analysis
- Newsletter/promotional email detection
- Duplicate/similar email identification
- Email categorization
- **Local content analysis** for better categorization (content never leaves machine)

#### 4. AI Interface Module (`ai_interface.py`)
- Generate sanitized data summaries for AI
- Send anonymized patterns to AI for recommendations
- Parse AI recommendations back into actionable items
- Never send: email addresses, personal names, email content

#### 5. Action Engine Module (`actions.py`)
- Delete unnecessary emails
- Apply/create Gmail labels
- Archive emails
- Generate unsubscribe lists
- Batch operation support with rollback capability

#### 6. User Interface Module (`ui.py`)
- CLI for power users
- Optional web interface for visual management
- Review and approve AI recommendations
- Manual action triggers

## Data Privacy Strategy

### What Gets Stored Locally
```sql
emails_metadata:
- message_id (Gmail ID)
- thread_id
- sender_domain (e.g., "example.com")
- sender_hash (hashed email for tracking, not reversible)
- subject_keywords (extracted keywords only)
- date_received
- labels
- estimated_importance_score
- category (newsletter, personal, work, etc.)
```

### What Gets Shared with AI
- Aggregate statistics (e.g., "50 emails from shopping sites")
- Pattern summaries (e.g., "Daily newsletter pattern detected")
- Anonymized sender domains
- Subject keyword clusters
- **Never**: actual email addresses, names, or content

## Implementation Phases (Test-Driven Development)

### Phase 1: Foundation & TDD Setup (Week 1-2) ✅ COMPLETED
- [x] Set up project structure with pytest
- [x] Write tests for OAuth2 authentication
- [x] Implement OAuth2 authentication (TDD)
- [x] Write tests for Gmail API connection
- [x] Create basic Gmail API connection (TDD)
- [x] Write tests for SQLite schema operations
- [x] Design and create SQLite schema (TDD)
- [x] Write tests for metadata extraction
- [x] Build metadata extraction pipeline (TDD)

### Phase 2: Core Analysis (Week 2-3) ⚠️ PARTIALLY COMPLETED
- [x] Implement pattern recognition algorithms (basic email categorization)
- [x] Build email categorization system (newsletter detection, sender analysis)
- [x] Create data anonymization functions (sender hashing, domain extraction)
- [x] Develop AI prompt templates (basic AI analyzer module)

### Phase 3: AI Integration (Week 3-4) ⚠️ PARTIALLY COMPLETED
- [x] Build AI interface module (ai_analyzer.py implemented)
- [x] Create recommendation parsing system (basic cleanup recommendations)
- [ ] Implement feedback loop for AI learning
- [x] Add safety checks for AI recommendations (privacy-preserving data sharing)

### Phase 4: Action Engine (Week 4-5) ⚠️ PARTIALLY COMPLETED
- [x] Implement Gmail modification operations (cleanup_engine.py)
- [x] Build batch processing with rollback (basic unsubscribe_engine.py)
- [x] Create unsubscribe detection/automation (unsubscribe_engine.py)
- [ ] Add dry-run mode for testing

### Phase 5: Web Interface (Week 5-6) ❌ NOT STARTED
- [ ] Write tests for FastAPI web interface
- [ ] Build FastAPI web application (TDD)
- [ ] Create HTML templates for email review
- [ ] Implement progress tracking and logging
- [x] Build CLI interface for batch operations (cli.py fully implemented and tested)
- [ ] Add approval workflow for 40k+ email processing

## Security Considerations

### Authentication Security
- Store OAuth tokens in OS keychain/credential store
- Implement token rotation
- Scope limitation (read-only initially, modify only when needed)

### Data Protection
- Local SQLite encryption at rest
- No cloud storage of any email data
- Clear data retention policies
- Audit logging of all actions

### AI Interaction Security
- Data anonymization before AI requests
- No PII in AI prompts
- Rate limiting on AI API calls
- Clear logging of what data is shared

## Sample Workflow

1. **Initial Setup (40k+ emails)**
   ```bash
   python inbox_cleaner.py auth --setup
   python inbox_cleaner.py sync --initial --batch-size 1000 --with-progress
   python inbox_cleaner.py web --start  # Launch web interface
   ```

2. **Batch Cleanup (User-initiated)**
   ```bash
   python inbox_cleaner.py analyze --full-inbox --with-content-analysis
   python inbox_cleaner.py ai-recommend --category all --via-web-interface
   # Review via web interface at localhost:8000
   python inbox_cleaner.py execute --approved-actions
   ```

3. **Quick CLI Cleanup**
   ```bash
   python inbox_cleaner.py quick-clean --recent 30d --auto-newsletters
   ```

3. **AI Interaction Example**
   ```
   User → Tool: "Help me clean up newsletters"
   Tool → AI: "User has 150 emails from 15 newsletter domains,
              daily frequency, mostly unread, suggest cleanup strategy"
   AI → Tool: "Recommend: unsubscribe from 8 inactive newsletters,
              create 'Weekly Digest' label for 4 active ones, archive 2mo+ old"
   Tool → User: "AI suggests [actions]. Approve? (y/n/modify)"
   ```

## Success Metrics
- Inbox size reduction (target: 80%+ reduction)
- Time savings (target: <5 min daily maintenance)
- Privacy maintained (zero PII leakage to AI)
- User satisfaction with AI recommendations

## Next Steps
1. Review and approve this plan
2. Set up development environment
3. Begin Phase 1 implementation
4. Establish testing strategy with a small subset of emails

## Technical Considerations for 40k+ Emails

### Performance Optimizations
- **Batch Processing**: 1000 emails per batch with progress tracking
- **Database Indexing**: Optimize SQLite for large datasets
- **Memory Management**: Stream processing to avoid memory issues
- **Caching**: Cache AI responses for similar email patterns
- **Progressive Loading**: Web interface loads data progressively

### Web Interface Features
- **Pagination**: Handle large result sets efficiently
- **Bulk Actions**: Select/approve hundreds of actions at once
- **Progress Tracking**: Real-time progress bars for long operations
- **Preview Mode**: Quick preview of actions before execution
- **Search/Filter**: Find specific emails or patterns quickly

## TDD Development Approach
- **Test First**: Write failing tests before implementation
- **Red-Green-Refactor**: Standard TDD cycle
- **Test Coverage**: Aim for >90% test coverage
- **Integration Tests**: Test Gmail API interactions with mocked responses
- **Performance Tests**: Validate handling of large email volumes

## Current Project Status (Updated: 2025-09-01)

### ✅ Completed Components
- **Core Foundation**: Full OAuth2 authentication system with token management
- **Data Layer**: SQLite database with optimized schema for large email volumes
- **Email Extraction**: Gmail API integration with batch processing and metadata extraction
- **Privacy Protection**: Email content hashing, domain extraction, no PII storage
- **AI Integration**: Anthropic Claude integration with privacy-safe data sharing
- **Action Engines**: Basic cleanup and unsubscribe automation engines
- **CLI Interface**: Fully functional command-line interface with auth, sync, status, and diagnostics
- **Testing**: Comprehensive test suite (49 tests passing) with TDD approach

### ⚠️ Partially Completed Components
- **AI Feedback Loop**: Basic recommendations implemented, learning system pending
- **Dry-Run Mode**: Action simulation needs implementation
- **Batch Processing**: Core functionality exists, needs approval workflow for large datasets

### ❌ Missing Components (High Priority)
1. **Web Interface**: FastAPI application with HTML templates for 40k+ email management
2. **Progress Tracking**: Real-time progress bars for long-running operations
3. **Approval Workflow**: Bulk action review and approval system
4. **Performance Optimization**: Database indexing and memory management for large datasets

### Next Development Priorities
1. **Phase 5A**: Implement FastAPI web application with basic email review interface
2. **Phase 5B**: Add progress tracking and bulk action approval workflow  
3. **Dry-Run Mode**: Add action simulation and preview capabilities
4. **Optimization**: Database indexing and performance tuning for 40k+ emails
5. **Production Ready**: Comprehensive error handling and edge case management

### Test Coverage Status
- **49/49 tests passing** (100% pass rate)
- Coverage includes: Authentication, Database operations, Email extraction, Integration tests
- All core modules have comprehensive test coverage

## User Decisions Made
✅ **Batch processing** (user-initiated via CLI)
✅ **Anthropic Claude** for AI service
✅ **Web interface** as primary UI
✅ **Content analysis** (local only)
✅ **TDD approach** for development
✅ **~40k emails** scale optimization