# Bulk Email Validator

### Overview
The Bulk Email Validator is a high-performance, self-hosted Python CLI tool designed for efficient bulk email validation. Its primary purpose is to verify email addresses for deliverability and quality, supporting various business applications requiring clean email lists. Key capabilities include RFC 5322 syntax validation, local DNS resolution for MX records, optional SMTP RCPT TO validation with catch-all domain detection, disposable email blocking, and automatic deduplication. The project aims to provide a fast, reliable, and privacy-focused alternative to API-based validation services, offering a significant performance advantage and full control over the validation process.

### Recent Changes
**November 26, 2025 (Latest)**: Enhanced syntax validation for number-heavy emails
- Added validation to reject emails with all-numeric local parts (e.g., `123456@gmail.com`)
- Added validation to reject emails where numbers exceed letters in local part (e.g., `a123456@gmail.com` has 1 letter and 6 numbers)
- Emails with equal numbers and letters are allowed (e.g., `abc123@gmail.com` with 3 letters and 3 numbers)
- Emails with more letters than numbers pass validation (e.g., `abcdef1@gmail.com` with 6 letters and 1 number)
- Clear error messages explain why emails are rejected (e.g., "Local part has too many numbers (6) compared to letters (1)")
- Updated docstrings in `EmailSyntaxValidator` class to document new rules

**November 24, 2025**: All-valid output file enhancement
- Added new `all-valid.txt` output file that contains ALL valid emails in a single file
- Valid emails are now available in three formats: (1) domain-separated files, (2) other.txt for less common domains, (3) all-valid.txt for all valid emails combined
- Thread-safe implementation ensures no duplicates under concurrent processing
- Updated configuration with `all_valid_output` path in `config/settings.yaml`
- Summary output now displays both "Valid emails (by domain)" and "Valid emails (all)" for clarity
- Provides users with convenient access to all valid emails without needing to merge domain files

**November 24, 2025**: Incremental data persistence for fault tolerance
- Implemented incremental saving: each email result is written to disk immediately after validation
- **Key improvement:** Validated data is now preserved even if the process is stopped mid-way
- Added thread-safe `write_single_result()` method with O(n) performance using in-memory caching
- Results are no longer buffered in memory - they're written directly to output files as they complete
- Duplicate detection prevents re-writing emails across multiple runs
- Enables safe interruption: you can stop the validator at any time and resume later without losing progress
- Fixed clean exit: Program now exits cleanly without hanging threads (daemon threads used for timeout)
- Added graceful CTRL+C handling: Shows progress saved when interrupted by user

**November 24, 2025**: Global timeout feature and output folder management
- Implemented global timeout system (default 30s) to prevent emails from taking too long overall
- Added `timeout.global_timeout` setting to `config/settings.yaml` for easy configuration
- Removed individual DNS and SMTP timeout parameters in favor of unified global timeout
- Updated validation pipeline to enforce timeout across all steps (syntax, disposable, DNS, SMTP, catch-all)
- Emails exceeding the global timeout are marked as "unknown" with timeout reason
- Added `output/` folder to .gitignore to prevent validation results from being committed to git
- Each validation runs independently with its own executor, maintaining concurrent processing performance

**November 23, 2025**: Project cleanup and file reorganization
- Renamed main entry point from `validator.py` to `main.py` for clarity
- Removed deprecated HTTP DNS API configuration (rate_limit_delay, etc.)
- The old networkcalc.com API was replaced with local DNS resolution (5-10x faster!)
- Moved log files from root directory to dedicated `log/` directory
- Enhanced logging setup to automatically create log directory if it doesn't exist
- Updated configuration to use `log/validator.log` path
- Added log files to .gitignore for clean version control
- Updated all documentation to reflect new file names

**November 23, 2025**: Enhanced terminal progress display
- Implemented dynamic multi-line dashboard-style progress display using ANSI escape codes
- Replaced simple single-line progress with a clean, compact visual dashboard
- Features: progress bar with filled/unfilled blocks (█/░), categorized statistics with icons (✓ ⚠ ✗ ?), real-time speed and ETA
- Updates in place instead of appending lines, making output easier to read
- Automatically detects terminal support and gracefully handles non-interactive output

### User Preferences
- Prefers clean, compact terminal output with visual progress bars over verbose line-by-line updates

### System Architecture
The project employs a modular, self-hosted architecture built with Python 3.11.

**UI/UX Decisions:**
The tool is a Command-Line Interface (CLI) application, focusing on functional efficiency over graphical user interface. Output is structured into four categories (valid, risk, invalid, unknown) with well-known domains separated for clear results.

**Technical Implementations & Feature Specifications:**
*   **Validation Pipeline:** Emails pass through a sequential validation pipeline: Syntax -> Disposable Domain Check -> DNS Resolution -> (Optional) SMTP RCPT TO -> (Optional) Catch-all Detection.
*   **Syntax Validation:** Strict custom rules (stricter than RFC 5322):
    *   **Local Part (before @):** ONLY allows letters (a-z A-Z), numbers (0-9), dots (.), and underscores (_). NO plus-addressing (+), NO hyphens (-), NO other special characters.
    *   **Position Rules:** Dots and underscores cannot be at start or end of local part. No consecutive dots allowed. Consecutive underscores ARE allowed.
    *   **Number/Letter Ratio:** Local part must contain at least one letter (no all-numeric usernames). Numbers cannot exceed letters in count (number-heavy emails are marked invalid).
    *   **Domain Part (after @):** Standard format with labels containing letters, numbers, hyphens (not at start/end).
    *   **TLD Validation:** Minimum 2 characters, letters only, validated against official IANA TLD list (downloaded fresh on each run from https://data.iana.org/TLD/tlds-alpha-by-domain.txt).
    *   **Examples:** ✅ user@example.com, user_name@example.com, abc123@example.com, john.doe@example.com | ❌ user+tag@example.com, user-name@example.com, 123456@example.com, a123456@example.com
*   **DNS Resolution:** Local DNS resolution using `dnspython` for MX records, significantly faster than API calls. Supports multi-provider DNS with fallback (Google, Cloudflare, OpenDNS) and smart LRU caching for definitive results (up to 10,000 domains).
*   **SMTP Validation:** Optional RCPT TO validation with SOCKS5 proxy support, including mailbox existence verification and catch-all domain detection using random address probing. Features thread-safe rate limiting (1 request/proxy/second) and multi-port support (25, 587).
*   **Disposable Email Blocking:** Utilizes a blocklist of over 4,765 disposable domains.
*   **Deduplication:** Case-insensitive automatic deduplication of input emails.
*   **Well-known Domain Separation:** Automatically categorizes emails from 173+ popular providers into separate output files.
*   **Global Timeout:** Configurable timeout (default 30s) applied to all validation steps combined. If validation exceeds this time, the email is marked as "unknown" to prevent indefinite blocking.
*   **Concurrency:** Utilizes `ThreadPoolExecutor` for high-speed concurrent processing (100-500 emails/sec without SMTP, 10-50 emails/sec with SMTP validation).
*   **Configuration:** All settings are externalized in `config/settings.yaml`, allowing granular control over validation rules, DNS, SMTP, proxy, timeout, and performance parameters.
*   **Output:** Generates four distinct output categories: `valid`, `risk` (catch-all), `invalid`, and `unknown` (SMTP errors or timeout). Valid emails are provided in three formats: (1) domain-separated files in `output/valid/` directory for well-known domains (gmail.com.txt, yahoo.com.txt, etc.), (2) `other.txt` for less common domains, and (3) `all-valid.txt` containing all valid emails in a single file for convenience. Output files are excluded from git via .gitignore.
*   **Incremental Persistence:** Results are written to disk immediately after each email validation (not buffered in memory). This ensures data is preserved if the process is stopped or crashes. Thread-safe with O(n) performance using in-memory caching for duplicate detection.

**System Design Choices:**
*   **Modular Design:** The codebase is organized into a `validators/` package with clear separation of concerns (e.g., `syntax_validator.py`, `local_dns_checker.py`, `smtp_validator.py`, `proxy_manager.py`, `io_handler.py`, `core.py`). This promotes testability and maintainability.
*   **Externalized Configuration:** All operational parameters are managed via a YAML file, avoiding hardcoded values and facilitating deployment and customization.
*   **Robustness:** Includes retry logic for transient network failures and structured logging for detailed operational insights.
*   **Performance Optimization:** Emphasizes local processing (DNS, syntax) and efficient concurrency to achieve high throughput.

### External Dependencies
*   **Python Libraries:**
    *   `dnspython`: For local DNS resolution.
    *   `PySocks`: For SOCKS5 proxy support.
    *   `PyYAML`: For configuration file parsing.
    *   `requests`: Used for legacy HTTP DNS API support (now largely deprecated in favor of local DNS).
*   **Configuration/Data Files:**
    *   `config/settings.yaml`: Main configuration file.
    *   `config/well_known_domains.txt`: List of popular email providers for categorization.
    *   `data/proxy.txt`: SOCKS5 proxy list (format: host:port or host:port@username:password, optional for SMTP validation).
    *   `data/disposable_domains.txt`: Blocklist for disposable email addresses.
    *   `data/tlds-alpha-by-domain.txt`: IANA TLD list (auto-downloaded on each run, cached locally).