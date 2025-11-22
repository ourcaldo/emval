# Bulk Email Validator

## Project Overview
A high-performance, modular Python CLI tool for bulk email validation. Features DNS deliverability checks, disposable email blocking, automatic deduplication, and well-known domain separation. Built with a clean, testable architecture.

## Project Type
Command-line application (CLI tool) with modular architecture

## Key Features
- **RFC 5322 compliant** email syntax validation
- **DNS deliverability checks** with retry logic (3 attempts)
- **Disposable email blocking** (4,765+ domains)
- **Automatic deduplication** (case-insensitive)
- **Well-known domain separation** (173+ popular email providers)
- **DNS caching** with LRU cache (up to 10,000 domains)
- **Concurrent processing** with configurable job count
- **Modular architecture** for easy testing and maintenance
- **External configuration** via YAML file
- **Structured logging** to file and console

## Architecture

### Modular Design
- **validator.py** - Main entry point and orchestrator
- **validators/** - Modular validation package
  - `core.py` - Email validation service with retry logic
  - `dns_checker.py` - DNS verification with caching
  - `disposable.py` - Disposable domain checker
  - `io_handler.py` - File I/O operations with deduplication
- **config/settings.yaml** - External configuration file
- **config/well_known_domains.txt** - 173 well-known email providers

### Technology Stack
- **Language**: Python 3.11
- **Dependencies**: emval (email validation), PyYAML (configuration)
- **Concurrency**: ThreadPoolExecutor for parallel validation
- **Caching**: LRU cache for DNS lookups

## File Structure
```
.
├── validator.py                  # Main entry point
├── validators/                   # Modular validation package
│   ├── core.py                   # Email validation service
│   ├── dns_checker.py            # DNS verification with caching
│   ├── disposable.py             # Disposable domain checker
│   └── io_handler.py             # File I/O operations
├── config/                       # Configuration files
│   ├── settings.yaml             # Main configuration
│   └── well_known_domains.txt    # 173 well-known email providers
├── data/                         # Input files
│   ├── emails.txt                # Input emails (one per line)
│   └── disposable_domains.txt    # Blocklist of 4,765+ disposable domains
├── output/                       # Output files (generated)
│   ├── valid/                    # Valid emails by domain
│   │   ├── gmail.com.txt         # Well-known domain
│   │   ├── yahoo.com.txt         # Well-known domain
│   │   └── other.txt             # All other domains
│   └── invalid.txt               # Invalid emails
├── requirements.txt              # Python dependencies
├── ANALYSIS_REPORT.md            # Comprehensive analysis of architecture
└── README.md                     # User-facing documentation
```

## How to Use
1. Add email addresses to `data/emails.txt` (one email per line)
   - Duplicates are automatically removed (case-insensitive)
2. Run the workflow or execute: `python validator.py`
3. Check results in the `output/` directory:
   - `output/valid/<domain>.txt` - Well-known domains (separate files)
   - `output/valid/other.txt` - All other domains
   - `output/invalid.txt` - Invalid emails
4. All output files contain **email addresses only** (no reasons or metadata)

## Configuration
All settings are externalized in `config/settings.yaml`:

### Validation Rules
- ASCII-only characters (no Unicode)
- No empty local parts
- No quoted strings
- No IP addresses as domains
- DNS deliverability checks enabled
- No special domains allowed

### Performance Settings
- `max_workers`: 1000 (concurrent validation jobs)
- `batch_size`: 1000 (emails per batch)
- `retry.attempts`: 3 (DNS failure retries)
- `retry.delay`: 0.5 (delay between retries)
- `dns_cache.max_size`: 10000 (cached domains)

**⚠️ Note:** 1000 concurrent jobs may overwhelm DNS resolvers. Consider 50-100 for production.

## Recent Changes

### 2025-11-22: Major Refactoring - Modular Architecture
- **Refactored to modular architecture** addressing all weaknesses from ANALYSIS_REPORT.md:
  - ✅ Separated into validators/ package with clean module separation
  - ✅ Core validation, DNS checking, disposable checking, and I/O now independent modules
  - ✅ All components independently testable
  - ✅ Configuration externalized to config/settings.yaml
  - ✅ Loosely coupled, highly cohesive design

- **Added email deduplication**:
  - Case-insensitive duplicate detection
  - Preserves order of first occurrence
  - Reports number of duplicates removed

- **Simplified output format**:
  - Valid emails: email-only (no reasons)
  - Invalid emails: email-only (no reasons)
  - Removed summary file functionality

- **Well-known domain separation**:
  - 173 popular email providers in config/well_known_domains.txt
  - Individual files for well-known domains
  - other.txt for all other domains

- **Implemented all ANALYSIS_REPORT.md recommendations**:
  - ✅ DNS caching with LRU cache (10,000 domains)
  - ✅ Retry logic for DNS failures (3 attempts, 0.5s delay)
  - ✅ Structured logging to file and console
  - ✅ Enhanced filename sanitization with regex
  - ✅ Error categorization (syntax, dns, disposable, valid)

### 2025-11-22: Directory-Based Output Structure
- Valid emails organized by domain in `output/valid/` directory
- Each well-known domain gets its own file
- Emails sorted alphabetically within each domain file
- Created comprehensive ANALYSIS_REPORT.md with architecture analysis

### 2025-11-22: Project Import Completed
- Installed emval and PyYAML dependencies
- Configured Email Validator workflow
- Verified project functionality

### 2025-11-08: Initial Project Setup
- Created data/ and output/ directories
- Enhanced progress display with real-time updates
- Added live statistics and ETA calculation
- Created requirements.txt

## User Preferences
None specified yet.

## Technical Notes
- All configuration in `config/settings.yaml` - no hardcoded settings
- Modular architecture allows easy unit testing
- DNS caching significantly improves performance for duplicate domains
- Retry logic handles transient DNS failures gracefully
- Structured logging provides detailed audit trail
- Case-insensitive deduplication prevents duplicate processing
