# Bulk Email Validator

## Project Overview
A high-performance Python CLI tool for bulk email validation using the emval library. The tool validates email addresses with DNS deliverability checks and blocks disposable email domains.

## Project Type
Command-line application (CLI tool)

## Key Features
- RFC 5322 compliant email syntax validation
- DNS deliverability checks (MX records)
- Disposable email domain blocking (4,765+ domains)
- Concurrent processing with configurable job count
- Detailed error reporting with reasons for invalid emails

## Architecture
- **Language**: Python 3.11
- **Main Script**: `bulk_email_validator.py`
- **Dependencies**: emval (email validation library)
- **Concurrency**: ThreadPoolExecutor for parallel validation

## File Structure
- `bulk_email_validator.py` - Main validation script
- `emails.txt` - Input file containing emails to validate (one per line)
- `disposable_domains.txt` - Blocklist of 4,765+ disposable email domains
- `valid_list.txt` - Output file for valid emails (generated)
- `invalid.txt` - Output file for invalid emails with reasons (generated)

## How to Use
1. Add email addresses to `emails.txt` (one email per line)
2. Run the workflow or execute: `python bulk_email_validator.py`
3. Check results in `valid_list.txt` (valid emails) and `invalid.txt` (invalid with reasons)

## Configuration
The validator uses strict validation settings configured in the script:
- ASCII-only characters (no Unicode)
- No empty local parts
- No quoted strings
- No IP addresses as domains
- DNS deliverability checks enabled
- No special domains allowed

Adjust `CONCURRENT_JOBS` variable (default: 10) to control parallelism based on your needs.

## Recent Changes
- **2025-11-08**: Initial project setup in Replit environment
  - Installed Python 3.11 and emval dependency
  - Created .gitignore for Python projects
  - Configured workflow for running the validator
