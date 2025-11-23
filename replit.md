# Bulk Email Validator

## Project Overview
A high-performance, self-hosted Python CLI tool for bulk email validation. Features self-hosted RFC 5322 syntax validation, local DNS resolution (5-10x faster than API), disposable email blocking, automatic deduplication, and well-known domain separation. Built with a clean, testable architecture with no external validation dependencies.

## Project Type
Command-line application (CLI tool) with modular self-hosted architecture

## Key Features
- **Self-hosted RFC 5322 compliant** email syntax validation
- **Local DNS resolution** using dnspython library (5-10x faster than API-based validation)
- **Multi-provider DNS** with configurable DNS servers and automatic fallback (Google, Cloudflare, OpenDNS)
- **Disposable email blocking** (4,765+ domains)
- **Automatic deduplication** (case-insensitive)
- **Well-known domain separation** (173+ popular email providers)
- **Smart DNS caching** with selective LRU cache (only caches definitive results, up to 10,000 domains)
- **High-speed concurrent processing** (100-500 emails/sec with configurable job count)
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
  - `proxy_manager.py` - Proxy rotation manager with authentication support
  - `core.py` - Email validation service orchestrating all checks
  - `disposable.py` - Disposable domain checker
  - `io_handler.py` - File I/O operations with deduplication
- **config/settings.yaml** - External configuration file (includes network/proxy settings)
- **config/well_known_domains.txt** - 173 well-known email providers
- **data/proxy.txt** - Proxy list file (when proxy rotation is enabled)

### Technology Stack
- **Language**: Python 3.11
- **Dependencies**: dnspython (DNS resolution), PyYAML (configuration), requests (legacy HTTP API support)
- **Validation**: Self-hosted RFC 5322 compliant (no external validation libraries)
- **DNS**: Local DNS resolution using dnspython with multi-provider fallback (Google DNS, Cloudflare, OpenDNS)
- **Concurrency**: ThreadPoolExecutor for parallel validation
- **Caching**: Smart LRU cache for DNS lookups (selective caching of definitive results only)
- **Performance**: 100-500 emails/sec (5-10x faster than API-based validation)

## File Structure
```
.
├── validator.py                   # Main entry point
├── validators/                    # Modular validation package
│   ├── syntax_validator.py        # Self-hosted RFC 5322 syntax validation
│   ├── local_dns_checker.py       # Local DNS resolution with caching (dnspython)
│   ├── http_dns_checker.py        # Legacy HTTP DNS API (deprecated)
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
- `deliverable_address`: Enable DNS deliverability checks (default: true)
- `allowed_special_domains`: List of special-use domains to allow (default: [])

### DNS Settings (Local DNS Resolution)
- `dns.timeout`: DNS query timeout (default: 5s)
- `dns.max_retries`: Maximum retry attempts (default: 3)
- `dns.retry_delay`: Delay between retries (default: 0.5s)
- `dns.servers`: Custom DNS servers (default: [] = Google, Cloudflare, OpenDNS)

### Performance Settings
- `max_workers`: 1000 (concurrent validation jobs)
- `batch_size`: 1000 (emails per batch)
- `retry.attempts`: 3 (validation failure retries)
- `retry.delay`: 0.5 (delay between retries)
- `dns_cache.max_size`: 10000 (cached domains)

**⚠️ Note:** With local DNS resolution, 1000 concurrent jobs works well. For API-based validation, consider 50-100 to avoid rate limiting.

## Recent Changes

### 2025-11-23: Migration from HTTP API to Local DNS Resolution
- **Replaced HTTP DNS API with local DNS resolution**:
  - ✅ Created `validators/local_dns_checker.py` using dnspython library
  - ✅ 5-10x performance improvement (from ~20 emails/sec to 100-500 emails/sec)
  - ✅ Eliminated external API dependency (no rate limits, no downtime)
  - ✅ Multi-provider DNS support with automatic fallback (Google, Cloudflare, OpenDNS)
  - ✅ Configurable DNS servers in config/settings.yaml
  - ✅ Preserved all features: selective caching, thread-safety, retry logic, RFC 5321 compliance
  
- **Performance improvements**:
  - Direct DNS queries via dnspython (10-100ms vs 200-1000ms for HTTP API)
  - No network overhead from HTTP requests
  - No rate limiting from external API
  - Validated 19 emails in 0.10 seconds (184.77 emails/sec average, 443.8 emails/sec peak)

- **Configuration updates**:
  - Added `dns` section in config/settings.yaml
  - Configurable DNS servers (default: Google, Cloudflare, OpenDNS)
  - Faster default timeout (5s vs 10s)
  - Kept `http_dns_checker.py` for backward compatibility (deprecated)

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

### 2025-11-22: Enhanced Proxy Functionality
- **Simplified proxy configuration**:
  - ✅ Changed from complex dict to simple true/false toggle in settings.yaml
  - ✅ Created ProxyManager class for automatic proxy rotation
  - ✅ Added support for proxy authentication (host:port@user:password)
  - ✅ Implemented thread-safe round-robin proxy selection
  - ✅ Proxy list loaded from data/proxy.txt with format validation

- **New components**:
  - `validators/proxy_manager.py` - Manages proxy loading and rotation
  - `data/proxy.txt` - Proxy list configuration file with examples

- **Integration**:
  - HTTPDNSChecker automatically rotates through proxies per request
  - Graceful fallback when proxy list is empty
  - Detailed logging for proxy operations

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
- All configuration in `config/settings.yaml` - no hardcoded settings (DNS servers configurable)
- Self-hosted validation - no external validation libraries required
- Local DNS resolution using dnspython (5-10x faster than API-based validation)
- Multi-provider DNS with automatic fallback (Google DNS, Cloudflare, OpenDNS)
- Modular architecture allows easy unit testing
- Smart DNS caching (only caches definitive results) significantly improves performance
- Retry logic with exponential backoff handles transient DNS failures gracefully
- Structured logging provides detailed audit trail
- Thread-safe operations for concurrent requests
- Case-insensitive deduplication prevents duplicate processing
- High performance: 100-500 emails/sec (vs 12-20 emails/sec with HTTP API)
