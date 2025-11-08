# 📬 Bulk Email Validator

A high-performance bulk email validator using emval with disposable email detection.

## Features

✅ Validates email syntax (RFC 5322 compliant)
✅ DNS deliverability checks (MX records)
✅ Disposable email domain blocking (4,765+ domains)
✅ Concurrent processing for speed
✅ Detailed error reporting

## Configuration

The validator uses strict settings:
- `allow_smtputf8=False` - Only ASCII characters allowed
- `allow_empty_local=False` - No empty local parts
- `allow_quoted_local=False` - No quoted strings
- `allow_domain_literal=False` - No IP addresses
- `deliverable_address=True` - DNS checks enabled
- `allowed_special_domains=[]` - No special domains

## Files

- `bulk_email_validator.py` - Main script
- `emails.txt` - Input file (one email per line)
- `disposable_domains.txt` - Blocklist of disposable domains
- `valid_list.txt` - Output: valid emails
- `invalid.txt` - Output: invalid emails with reasons

## Usage

1. Add your emails to `emails.txt` (one per line)
2. Adjust `CONCURRENT_JOBS` in the script (default: 10)
3. Run: `python bulk_email_validator.py`

## Performance

The script uses ThreadPoolExecutor for concurrent validation.
Adjust `CONCURRENT_JOBS` based on your needs:
- Low: 5 jobs (safer, slower)
- Medium: 10 jobs (balanced)
- High: 20 jobs (faster, more DNS queries)

## Output Format

**valid_list.txt:**
```
john.doe@gmail.com
user@yahoo.com
```

**invalid.txt:**
```
test@example.com | Invalid Domain: The domain does not accept email...
admin@tempmail.com | Disposable email domain
invalid-email | Invalid Email Address: Missing an '@' sign.
```

## Example

Input (emails.txt):
```
john.doe@gmail.com
test@tempmail.com
invalid-email
```

Output:
```
Total Emails:     3
✅ Valid:         1
❌ Invalid:       2
```
