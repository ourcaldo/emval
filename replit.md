# Bulk Email Validator

### Overview
The Bulk Email Validator is a high-performance, self-hosted Python CLI tool designed for efficient bulk email validation. Its primary purpose is to verify email addresses for deliverability and quality, supporting various business applications requiring clean email lists. Key capabilities include RFC 5322 syntax validation, local DNS resolution for MX records, optional SMTP RCPT TO validation with catch-all domain detection, disposable email blocking, and automatic deduplication. The project aims to provide a fast, reliable, and privacy-focused alternative to API-based validation services, offering a significant performance advantage and full control over the validation process.

### Recent Changes
**November 23, 2025 (Latest)**: Log directory organization
- Moved log files from root directory to dedicated `log/` directory
- Enhanced logging setup to automatically create log directory if it doesn't exist
- Updated configuration to use `log/validator.log` path
- Added log files to .gitignore for clean version control

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
    *   **Domain Part (after @):** Standard format with labels containing letters, numbers, hyphens (not at start/end).
    *   **TLD Validation:** Minimum 2 characters, letters only, validated against official IANA TLD list (downloaded fresh on each run from https://data.iana.org/TLD/tlds-alpha-by-domain.txt).
    *   **Examples:** ✅ user@example.com, user_name@example.com, user__test@example.com, user._name@example.com | ❌ user+tag@example.com, user-name@example.com, _user@example.com, user_@example.com
*   **DNS Resolution:** Local DNS resolution using `dnspython` for MX records, significantly faster than API calls. Supports multi-provider DNS with fallback (Google, Cloudflare, OpenDNS) and smart LRU caching for definitive results (up to 10,000 domains).
*   **SMTP Validation:** Optional RCPT TO validation with SOCKS5 proxy support, including mailbox existence verification and catch-all domain detection using random address probing. Features thread-safe rate limiting (1 request/proxy/second) and multi-port support (25, 587).
*   **Disposable Email Blocking:** Utilizes a blocklist of over 4,765 disposable domains.
*   **Deduplication:** Case-insensitive automatic deduplication of input emails.
*   **Well-known Domain Separation:** Automatically categorizes emails from 173+ popular providers into separate output files.
*   **Concurrency:** Utilizes `ThreadPoolExecutor` for high-speed concurrent processing (100-500 emails/sec without SMTP, 10-50 emails/sec with SMTP validation).
*   **Configuration:** All settings are externalized in `config/settings.yaml`, allowing granular control over validation rules, DNS, SMTP, proxy, and performance parameters.
*   **Output:** Generates four distinct output categories: `valid`, `risk` (catch-all), `invalid`, and `unknown` (SMTP errors).

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