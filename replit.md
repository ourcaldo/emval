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
- `validator.py` - Main validation script
- `data/emails.txt` - Input file containing emails to validate (one per line)
- `data/disposable_domains.txt` - Blocklist of 4,765+ disposable email domains
- `output/valid_list.txt` - Output file for valid emails (generated)
- `output/invalid.txt` - Output file for invalid emails with reasons (generated)
- `requirements.txt` - Python dependencies (emval)

## How to Use
1. Add email addresses to `data/emails.txt` (one email per line)
2. Run the workflow or execute: `python validator.py`
3. Check results in the `output/` directory:
   - `output/valid_list.txt` - Valid emails
   - `output/invalid.txt` - Invalid emails with reasons

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
- **2025-11-08**: Project enhancements
  - Restructured project with `data/` and `output/` directories for better organization
  - Enhanced progress display to show dynamic real-time updates on the same line
  - Added live statistics: progress percentage, speed (emails/sec), and elapsed time
  - Created requirements.txt for easy dependency installation
  - Renamed main script from `bulk_email_validator.py` to `validator.py`
  - Updated README with proper credits to emval library
- **2025-11-08**: Initial project setup in Replit environment
  - Installed Python 3.11 and emval dependency
  - Created .gitignore for Python projects
  - Configured workflow for running the validator
