# Bulk Email Validator

## Project Overview
A high-performance, self-hosted Python CLI tool for bulk email validation. Features self-hosted RFC 5322 syntax validation, HTTP DNS API verification, disposable email blocking, automatic deduplication, and well-known domain separation. Built with a clean, testable architecture with no external validation dependencies.

## Project Type
Command-line application (CLI tool) with modular self-hosted architecture

## Key Features
- **Self-hosted RFC 5322 compliant** email syntax validation
- **HTTP DNS API verification** using networkcalc.com API with retry logic
- **Proxy support** for HTTP DNS API requests (optional)
- **Disposable email blocking** (4,765+ domains)
- **Automatic deduplication** (case-insensitive)
- **Well-known domain separation** (173+ popular email providers)
- **DNS caching** with LRU cache (up to 10,000 domains)
- **Concurrent processing** with configurable job count
- **Modular architecture** for easy testing and maintenance
- **External configuration** via YAML file
- **Structured logging** to file and console
- **Configurable validation options** (Unicode, quoted strings, IP addresses, special domains)

## Architecture

### Modular Self-Hosted Design
- **validator.py** - Main entry point and orchestrator
- **validators/** - Modular validation package
  - `syntax_validator.py` - Self-hosted RFC 5322 email syntax validation
  - `http_dns_checker.py` - HTTP DNS API verification with caching and proxy support
  - `core.py` - Email validation service orchestrating all checks
  - `disposable.py` - Disposable domain checker
  - `io_handler.py` - File I/O operations with deduplication
- **config/settings.yaml** - External configuration file (includes network/proxy settings)
- **config/well_known_domains.txt** - 173 well-known email providers

### Technology Stack
- **Language**: Python 3.11
- **Dependencies**: requests (HTTP client), PyYAML (configuration)
- **Validation**: Self-hosted RFC 5322 compliant (no external validation libraries)
- **DNS**: networkcalc.com HTTP API for MX record verification
- **Concurrency**: ThreadPoolExecutor for parallel validation
- **Caching**: LRU cache for DNS lookups
- **Proxy**: Optional HTTP/HTTPS proxy support

## File Structure
```
.
├── validator.py                   # Main entry point
├── validators/                    # Modular validation package
│   ├── syntax_validator.py        # Self-hosted RFC 5322 syntax validation
│   ├── http_dns_checker.py        # HTTP DNS API with caching
│   ├── core.py                    # Email validation service
│   ├── disposable.py              # Disposable domain checker
│   └── io_handler.py              # File I/O operations
├── config/                        # Configuration files
│   ├── settings.yaml              # Main configuration (includes network/proxy)
│   └── well_known_domains.txt     # 173 well-known email providers
├── data/                          # Input files
│   ├── emails.txt                 # Input emails (one per line)
│   └── disposable_domains.txt     # Blocklist of 4,765+ disposable domains
├── output/                        # Output files (generated)
│   ├── valid/                     # Valid emails by domain
│   │   ├── gmail.com.txt          # Well-known domain
│   │   ├── yahoo.com.txt          # Well-known domain
│   │   └── other.txt              # All other domains
│   └── invalid.txt                # Invalid emails
├── requirements.txt               # Python dependencies (requests, pyyaml)
├── pyproject.toml                 # Project metadata
└── README.md                      # User-facing documentation
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
- `allow_smtputf8`: Allow Unicode/internationalized characters (default: false)
- `allow_empty_local`: Allow empty local parts (default: false)
- `allow_quoted_local`: Allow quoted strings (default: false)
- `allow_domain_literal`: Allow IP addresses as domains (default: false)
- `deliverable_address`: Enable HTTP DNS API checks (default: true)
- `allowed_special_domains`: List of special-use domains to allow (default: [])

### Network Settings (HTTP DNS API)
- `network.timeout`: API request timeout (default: 10s)
- `network.max_retries`: Maximum retry attempts (default: 3)
- `network.retry_delay`: Delay between retries (default: 1.0s)
- `network.rate_limit_delay`: Delay between requests (default: 0.1s)
- `network.proxy`: Optional proxy configuration (http/https)

### Performance Settings
- `max_workers`: 1000 (concurrent validation jobs)
- `batch_size`: 1000 (emails per batch)
- `retry.attempts`: 3 (validation failure retries)
- `retry.delay`: 0.5 (delay between retries)
- `dns_cache.max_size`: 10000 (cached domains)

**⚠️ Note:** 1000 concurrent jobs may cause API rate limiting. Consider 50-100 for production.

## Recent Changes

### 2025-11-22: Self-Hosted Validation - Removed External Dependencies
- **Replaced emval with self-hosted validation**:
  - ✅ Created `validators/syntax_validator.py` with RFC 5322 compliant email syntax validation
  - ✅ Replaced `validators/dns_checker.py` with `validators/http_dns_checker.py` using networkcalc.com API
  - ✅ Updated `validators/core.py` to orchestrate syntax, disposable, and DNS checks
  - ✅ Removed emval dependency, added requests library
  - ✅ No external validation libraries required

- **Added network configuration**:
  - HTTP DNS API with timeout and retry settings
  - Optional proxy support (HTTP/HTTPS)
  - Rate limiting to avoid API abuse
  - All network settings in config/settings.yaml

- **Enhanced validation options**:
  - `allow_smtputf8`: Unicode/internationalized email addresses
  - `allow_empty_local`: Empty local parts (@domain.com)
  - `allow_quoted_local`: Quoted local parts ("user name"@domain.com)
  - `allow_domain_literal`: Domain literals ([192.168.0.1])
  - `allowed_special_domains`: Whitelist special-use domains (e.g., ['localhost', 'test'])

- **Validation flow**:
  1. Syntax validation (self-hosted RFC 5322 compliance)
  2. Disposable domain check
  3. HTTP DNS API MX record verification (if enabled)

### 2025-11-22: Major Refactoring - Modular Architecture
- **Refactored to modular architecture**:
  - ✅ Separated into validators/ package with clean module separation
  - ✅ Core validation, DNS checking, disposable checking, and I/O now independent modules
  - ✅ All components independently testable
  - ✅ Configuration externalized to config/settings.yaml
  - ✅ Loosely coupled, highly cohesive design

- **Added email deduplication**:
  - Case-insensitive duplicate detection
  - Preserves order of first occurrence
  - Reports number of duplicates removed

- **Well-known domain separation**:
  - 173 popular email providers in config/well_known_domains.txt
  - Individual files for well-known domains
  - other.txt for all other domains

- **Implemented validation features**:
  - ✅ DNS caching with LRU cache (10,000 domains)
  - ✅ Retry logic for DNS failures (3 attempts)
  - ✅ Structured logging to file and console
  - ✅ Error categorization (syntax, dns, disposable, valid)

### 2025-11-22: Project Import Completed
- Installed dependencies (requests, PyYAML)
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
- Self-hosted validation - no external validation libraries required
- HTTP DNS API with networkcalc.com for MX record verification
- Optional proxy support for API requests (HTTP/HTTPS)
- Modular architecture allows easy unit testing
- DNS caching significantly improves performance for duplicate domains
- Retry logic handles transient API failures gracefully
- Structured logging provides detailed audit trail
- Case-insensitive deduplication prevents duplicate processing
- Rate limiting prevents API abuse
