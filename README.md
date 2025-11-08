# 📬 Bulk Email Validator

A high-performance bulk email validation tool with DNS verification and disposable email detection. Built with Python and powered by [emval](https://github.com/bnkc/emval).

## ✨ Features

- ✅ **RFC 5322 Compliant** - Validates email syntax according to official standards
- 🌐 **DNS Deliverability Checks** - Verifies MX records to ensure domains can receive emails
- 🚫 **Disposable Email Blocking** - Blocks 4,765+ known disposable email domains
- ⚡ **Concurrent Processing** - Multi-threaded validation for maximum speed
- 📊 **Detailed Reporting** - Clear error messages explaining why each email is invalid

## 🚀 Quick Start

### Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

1. Add email addresses to `data/emails.txt` (one email per line)
2. Run the validator:
```bash
python validator.py
```
3. Check the results in the `output/` directory:
   - `output/valid_list.txt` - All valid email addresses
   - `output/invalid.txt` - Invalid emails with detailed error reasons

## ⚙️ Configuration

The validator uses strict validation settings configured in `validator.py`:

| Setting | Value | Description |
|---------|-------|-------------|
| `allow_smtputf8` | `False` | Only ASCII characters allowed (no Unicode) |
| `allow_empty_local` | `False` | No empty local parts |
| `allow_quoted_local` | `False` | No quoted strings in email addresses |
| `allow_domain_literal` | `False` | No IP addresses as domains |
| `deliverable_address` | `True` | DNS deliverability checks enabled |
| `allowed_special_domains` | `[]` | No special domains allowed |

### Performance Tuning

Adjust the `CONCURRENT_JOBS` variable in `validator.py` to control parallel processing:

- **Low** (5 jobs): Safer, slower - recommended for rate-limited networks
- **Medium** (10 jobs): Balanced - default setting
- **High** (20 jobs): Faster, more DNS queries - use on high-bandwidth connections

## 📁 Project Structure

```
.
├── validator.py                # Main validation script
├── requirements.txt            # Python dependencies
├── data/                       # Input files directory
│   ├── emails.txt              # Input: Email addresses to validate (one per line)
│   └── disposable_domains.txt  # Blocklist of 4,765+ disposable domains
├── output/                     # Output files directory
│   ├── valid_list.txt          # Output: Valid emails (generated)
│   └── invalid.txt             # Output: Invalid emails with reasons (generated)
└── README.md                   # Documentation
```

## 📤 Output Format

### output/valid_list.txt
```
john.doe@gmail.com
user@example.com
alice@company.co.uk
```

### output/invalid.txt
```
test@invalid-domain.xyz | Invalid Domain: The domain does not accept email...
admin@tempmail.com | Disposable email domain
invalid-email | Invalid Email Address: Missing an '@' sign.
user@123.456.789.0 | IP addresses not allowed as domains
```

## 📊 Example Output

**Input** (`data/emails.txt`):
```
john.doe@gmail.com
test@tempmail.com
invalid-email
alice@example.com
```

**Console Output**:
```
======================================================================
📬 BULK EMAIL VALIDATOR
======================================================================
Concurrent Jobs: 10

✅ Validator configured
📥 Loading disposable email domains list...
✅ Loaded 4765 disposable domains

📧 Loaded 4 emails from data/emails.txt

🔄 Validating 4 emails with 10 concurrent jobs...
🔄 Progress: 4/4 - 100% | ⚡ 1.6 emails/sec | ⏱️  2.5s

✅ Valid emails saved to: output/valid_list.txt
❌ Invalid emails saved to: output/invalid.txt

======================================================================
📊 VALIDATION SUMMARY
======================================================================
Total Emails:     4
✅ Valid:         2
❌ Invalid:       2
⏱️  Time Taken:    2.45 seconds
⚡ Speed:          1.63 emails/second
======================================================================
```

## 🛠️ Requirements

- Python 3.11+
- emval==0.1.11

## 📝 Credits

This project is powered by [**emval**](https://github.com/bnkc/emval) - a robust Python email validation library created by [@bnkc](https://github.com/bnkc). Emval provides comprehensive email validation with DNS checks, syntax validation, and deliverability verification.

## 📄 License

This project uses emval which is available under its own license. Please refer to the [emval repository](https://github.com/bnkc/emval) for more information.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
