# 📬 Bulk Email Validator

A high-performance, self-hosted bulk email validation tool with local DNS resolution, disposable email detection, and automatic deduplication. Built entirely in Python with no external validation dependencies.

## ✨ Features

- ✅ **RFC 5322 Compliant** - Self-hosted email syntax validation following official standards
- ⚡ **Local DNS Resolution** - Direct DNS queries using dnspython (5-10x faster than API-based validation)
- 🌐 **Multi-Provider DNS** - Configurable DNS servers with automatic fallback (Google, Cloudflare, OpenDNS)
- 🚫 **Disposable Email Blocking** - Blocks 4,765+ known disposable email domains
- 🔥 **Concurrent Processing** - Multi-threaded validation for maximum speed (100-500 emails/sec)
- 🧩 **Modular Architecture** - Clean separation of concerns for easy testing and maintenance
- 🔁 **Automatic Deduplication** - Removes duplicate emails automatically (case-insensitive)
- 💾 **Smart DNS Caching** - LRU cache with selective caching (only definitive results, up to 10,000 domains)
- 📂 **Well-Known Domain Separation** - Organizes emails by 173+ popular email providers
- ⚙️ **External Configuration** - All settings in config/settings.yaml
- 🎛️ **Configurable Validation** - Control Unicode, quoted strings, IP addresses, and more

## 🚀 Quick Start

### Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

1. Add email addresses to `data/emails.txt` (one email per line)
   - Duplicates will be automatically removed
2. Run the validator:
```bash
python main.py
```
3. Check the results in the `output/` directory:
   - `output/valid/<domain>.txt` - Valid emails for well-known domains (gmail.com, yahoo.com, etc.)
   - `output/valid/other.txt` - Valid emails from other domains
   - `output/invalid.txt` - Invalid emails

## ⚙️ Configuration

All settings are configurable in `config/settings.yaml`:

### Validation Rules
| Setting | Default | Description |
|---------|---------|-------------|
| `allow_smtputf8` | `false` | Allow Unicode/internationalized email addresses |
| `allow_empty_local` | `false` | Allow empty local parts (@domain.com) |
| `allow_quoted_local` | `false` | Allow quoted local parts ("user name"@domain.com) |
| `allow_domain_literal` | `false` | Allow domain literals ([192.168.0.1]) |
| `deliverable_address` | `true` | Enable DNS deliverability checks (MX/A/AAAA records) |
| `allowed_special_domains` | `[]` | List of special-use domains to allow (e.g., ['test', 'localhost']) |

### DNS Settings (Local DNS Resolution)
| Setting | Default | Description |
|---------|---------|-------------|
| `dns.timeout` | `5` | DNS query timeout in seconds |
| `dns.max_retries` | `3` | Maximum retry attempts for DNS queries |
| `dns.retry_delay` | `0.5` | Delay between retries (seconds) |
| `dns.servers` | `[]` | Custom DNS servers (empty = use Google, Cloudflare, OpenDNS) |

### Performance Settings
| Setting | Default | Description |
|---------|---------|-------------|
| `max_workers` | `1000` | Number of concurrent validation jobs |
| `batch_size` | `1000` | Emails processed per batch |
| `retry.attempts` | `3` | Retry attempts for validation failures |
| `retry.delay` | `0.5` | Delay between retries (seconds) |
| `dns_cache.max_size` | `10000` | Maximum domains to cache |

## 📁 Project Structure

```
.
├── main.py                        # Main entry point
├── validators/                    # Modular validation package
│   ├── __init__.py                # Package exports
│   ├── core.py                    # Email validation service
│   ├── syntax_validator.py        # Self-hosted RFC 5322 syntax validation
│   ├── local_dns_checker.py       # Local DNS resolution with caching (dnspython)
│   ├── http_dns_checker.py        # Legacy HTTP DNS API (deprecated)
│   ├── disposable.py              # Disposable domain checker
│   └── io_handler.py              # File I/O operations
├── config/                        # Configuration files
│   ├── settings.yaml              # Main configuration
│   └── well_known_domains.txt     # 173 well-known email providers
├── data/                         # Input files directory
│   ├── emails.txt                # Input: Email addresses (one per line)
│   └── disposable_domains.txt    # Blocklist of 4,765+ disposable domains
├── output/                       # Output files (generated)
│   ├── valid/                    # Valid emails by domain
│   │   ├── gmail.com.txt         # Well-known domain
│   │   ├── yahoo.com.txt         # Well-known domain
│   │   └── other.txt             # All other domains
│   └── invalid.txt               # Invalid emails
└── requirements.txt              # Python dependencies
```

## 📤 Output Format

All output files contain **email addresses only** (one per line), with no additional information or reasons.

### Valid Emails - Well-Known Domains

Emails from 173 popular providers are separated into individual files:

**output/valid/gmail.com.txt:**
```
john.doe@gmail.com
jane.smith@gmail.com
```

**output/valid/yahoo.com.txt:**
```
alice@yahoo.com
bob@yahoo.com
```

### Valid Emails - Other Domains

Emails from all other domains go into a single file:

**output/valid/other.txt:**
```
contact@company.com
info@startup.io
team@business.co.uk
```

### Invalid Emails

**output/invalid.txt:**
```
test@invalid-domain.xyz
admin@tempmail.com
invalid-email
@missing.com
```

This organization makes it easy to:
- Process emails by provider
- Send bulk emails to specific domains
- Analyze email distribution across providers
- Import clean email lists into your application

## 🔄 Deduplication

The validator automatically removes duplicate emails:
- **Case-insensitive** - `User@Gmail.com` and `user@gmail.com` are treated as duplicates
- **First occurrence kept** - Original order preserved
- **Reported** - Number of duplicates removed is logged

Example:
```
# Input (data/emails.txt):
user@gmail.com
test@yahoo.com
User@Gmail.com    # Duplicate (different case)
test@yahoo.com    # Duplicate (exact)

# Result:
Loaded 2 unique emails
Removed 2 duplicate emails
```

## 📊 Example Run

```bash
$ python main.py

======================================================================
BULK EMAIL VALIDATOR
======================================================================
Concurrent Jobs: 1000

Initializing validation components...
Validator configured:
   - Unicode characters: Not allowed
   - Empty local parts: Not allowed
   - Quoted strings: Not allowed
   - IP addresses: Not allowed
   - DNS deliverability: Enabled
   - Retry attempts: 3
   - DNS caching: Enabled (max 10000 domains)

Well-known domains: 173 loaded
Disposable domains: 4765 loaded

Loaded 19 unique emails from data/emails.txt

Validating 19 emails with 1000 concurrent jobs...
Starting validation process...

19/19 - 100.0% | Valid: 12 | Invalid: 7 | Speed: 0.6/sec | ETA: 0s

Valid emails saved to: output/valid/
  - Created 5 well-known domain files
  - Created other.txt with 7 emails from unknown domains
  - Total valid emails: 12
Invalid emails saved to: output/invalid.txt

======================================================================
VALIDATION SUMMARY
======================================================================
Total Emails:     19
Valid:            12
Invalid:          7
Time Taken:       32.13 seconds
Speed:            0.59 emails/second
======================================================================
```

## 🎯 Well-Known Domains

The validator recognizes 173 popular email providers and creates separate files for each:

**Major Providers:**
- Gmail, Yahoo, Outlook, Hotmail, Live, MSN
- iCloud, Me, Mac
- ProtonMail, Tutanota, Zoho, Yandex
- AOL, GMX, Fastmail, Hey, Hushmail

**Regional Providers:**
- Asian: QQ, 163, 126, Sina, Naver, Daum
- European: Web.de, T-Online, Orange.fr, Free.fr, Libero.it
- Others: See `config/well_known_domains.txt` for complete list

## 🛠️ Architecture

The validator uses a self-hosted modular architecture with clear separation of concerns:

- **main.py** - Main orchestrator, loads config and coordinates components
- **EmailSyntaxValidator** - Self-hosted RFC 5322 compliant syntax validation
- **LocalDNSChecker** - Local DNS resolution using dnspython (5-10x faster than API-based)
- **EmailValidationService** - Core validation logic orchestrating syntax, disposable, and DNS checks
- **DisposableDomainChecker** - Disposable domain detection
- **EmailIOHandler** - File I/O and well-known domain separation

All components are independently testable and loosely coupled. No external validation libraries required.

## 🔧 Advanced Configuration

Edit `config/settings.yaml` to customize behavior:

```yaml
# Increase performance (API rate limits may apply)
concurrency:
  max_workers: 2000

# More aggressive retries
retry:
  attempts: 5
  delay: 1.0

# Larger DNS cache
dns_cache:
  max_size: 50000

# Add proxy for API requests
network:
  proxy:
    http: "http://proxy-server:8080"
    https: "https://proxy-server:8080"
  timeout: 15
  max_retries: 5

# Allow special domains
validation:
  allowed_special_domains: ['localhost', 'test']
```

## 📝 Logging

Detailed logs are written to `validator.log`:
- All validation operations
- Retry attempts for DNS failures
- Disposable domain detections
- File I/O operations
- DNS cache statistics

Configure logging in `config/settings.yaml`:
```yaml
logging:
  level: "DEBUG"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## 🤝 Credits

- Self-hosted email validation following RFC 5322 standards
- DNS verification via [networkcalc.com API](https://networkcalc.com)
- Disposable domain list from various open-source blocklists

## 🔌 DNS API

This validator uses the networkcalc.com DNS lookup API:
- **Endpoint**: `https://networkcalc.com/api/dns/lookup/{hostname}`
- **Features**: Returns A, CNAME, MX, NS, SOA, and TXT records
- **Rate Limiting**: Configurable delay between requests
- **Proxy Support**: Optional HTTP/HTTPS proxy configuration

## 📄 License

This project is provided as-is for email validation purposes.
