# Email Validation via SMTP - Complete Guide

## Overview
This guide documents how to validate email addresses by checking if the mailbox actually exists and can receive messages, not just checking DNS/MX records.

---

## Key Concepts

### What We're Validating
- ✅ Does the mailbox exist?
- ✅ Can it receive messages?
- ✅ Is the mailbox full?
- ✅ Is the domain catch-all enabled?

### What We're NOT Doing
- ❌ Just checking MX records (DNS lookup)
- ❌ Just validating email format
- ❌ Actually sending emails

---

## SMTP Response Codes

| Code | Meaning | Status |
|------|---------|--------|
| **250** | OK - Mailbox exists and can receive | ✅ Valid |
| **550** | Mailbox not found / doesn't exist | ❌ Invalid |
| **551** | User not local / relay denied | ❌ Invalid |
| **552** | Mailbox full | ⚠️ Exists but can't receive |
| **553** | Invalid address format | ❌ Invalid |
| **450** | Temporary failure (greylisting) | ⏳ Retry later |
| **451** | Temporary error | ⏳ Retry later |
| **530** | Must issue STARTTLS first | 🔒 TLS Required |
| **252** | Cannot verify, will try (Gmail) | ❓ Ambiguous |

---

## The SMTP Validation Flow

### Step 1: Get MX Records
```bash
dig +short MX domain.com
```

**Example:**
```
10 mx1.privateemail.com.
10 mx2.privateemail.com.
```

**What to do:**
- Use the server with lowest priority number (10 < 20)
- Try next server if first one fails

---

### Step 2: Check TLS Requirement

**Test connection and capabilities:**
```bash
telnet mx1.privateemail.com 25
EHLO test.com
```

**Look for in response:**
- `250-STARTTLS` → TLS is available

**Test if TLS is required:**
```bash
swaks --server mx1.privateemail.com \
      --port 25 \
      --to test@domain.com \
      --from test@test.com \
      --quit-after MAIL \
      --no-tls
```

**Results:**
- `250 Ok` → TLS is **optional**
- `530 Must issue STARTTLS` → TLS is **required**

**Port behavior:**
| Port | TLS Behavior |
|------|--------------|
| 25 | May require STARTTLS |
| 587 | Almost always requires STARTTLS |
| 465 | Implicit TLS (direct SSL) |

---

### Step 3: Detect Catch-All

**What is Catch-All?**
- Domain accepts ALL emails, even non-existent ones
- Makes individual mailbox validation impossible
- Common in small businesses/personal domains

**Detection method:**
```bash
# Test with obviously fake/random email
swaks --to randomimpossible999xyz@domain.com \
      --from test@test.com \
      --server mx.server.com \
      --port 25 \
      --quit-after RCPT \
      --tls
```

**Results:**

| Fake Email Response | Real Email Response | Conclusion |
|---------------------|---------------------|------------|
| 250 (accepted) | 250 (accepted) | ✅ **Catch-all ENABLED** |
| 550 (rejected) | 250 (accepted) | ❌ **Catch-all DISABLED** |

**Important Notes:**
- Use **highly random strings** like `verify8f9d7c6b5a4random@domain.com`
- Avoid common names like `test@` or `info@` (might actually exist)
- Test 2-3 random emails for higher confidence
- Even malformed emails (e.g., `ali.@domain.com`) may be accepted if catch-all is "dumb"

**Script Logic:**
```
IF (random_fake_email returns 250):
    → Catch-all enabled
    → Cannot verify individual emails
    → Mark as "valid domain, unknown mailbox"
ELSE:
    → Proceed to validate actual email
```

---

### Step 4: Validate Actual Email

**Complete SMTP conversation:**
```bash
swaks --to target@domain.com \
      --from sender@test.com \
      --server mx.server.com \
      --port 25 \
      --quit-after RCPT \
      --tls
```

**Or manual via telnet/openssl:**
```
EHLO test.com
MAIL FROM:<sender@test.com>
RCPT TO:<target@domain.com>
QUIT
```

**Parse RCPT TO response:**
- Starts with `250` → ✅ Valid mailbox
- Starts with `550/551/553` → ❌ Invalid mailbox
- Starts with `552` → ⚠️ Mailbox exists but full
- Starts with `450/451` → ⏳ Temporary error, retry later

---

## Complete Validation Algorithm

```
1. Extract domain from email
   Example: user@domain.com → domain.com

2. DNS MX Lookup
   dig +short MX domain.com
   → Get mail server address

3. Check TLS Requirement
   Connect and try MAIL FROM without TLS
   → If 530 error: TLS required
   → If 250: TLS optional

4. Detect Catch-All (CRITICAL STEP)
   RCPT TO: randomimpossible{timestamp}@domain.com
   → If 250: Catch-all enabled, stop here
   → If 550: Continue to step 5

5. Validate Target Email
   RCPT TO: target@domain.com
   → 250: Valid ✅
   → 550: Invalid ❌
   → 552: Full ⚠️
   → 450/451: Temporary ⏳

6. Return Result
   {
     "email": "target@domain.com",
     "valid": true/false,
     "catch_all": true/false,
     "smtp_code": 250,
     "message": "Mailbox exists",
     "can_receive": true
   }
```

---

## Why VRFY Doesn't Work

### Old Method (VRFY Command)
```bash
VRFY user@domain.com
```

**Problem:**
- Most modern servers **disable VRFY** (anti-spam measure)
- Gmail returns `252` (ambiguous) for ALL emails
- Cannot distinguish valid from invalid

**Gmail Example:**
```
VRFY aldodkris@gmail.com
252 2.1.5 Send some mail, I'll try my best

VRFY fakeinvalid@gmail.com  
252 2.1.5 Send some mail, I'll try my best
```
→ Same response for both! **Useless!**

---

## Real-World Examples

### Example 1: Gmail (No Catch-All)

```bash
# MX Lookup
dig +short MX gmail.com
→ 5 gmail-smtp-in.l.google.com.

# Test valid email
swaks --to aldodkris@gmail.com --from test@test.com \
      --server gmail-smtp-in.l.google.com --port 25 \
      --quit-after RCPT

Result: 250 2.1.5 OK ✅

# Test invalid email
swaks --to fakeinvaliduser12345@gmail.com --from test@test.com \
      --server gmail-smtp-in.l.google.com --port 25 \
      --quit-after RCPT

Result: 550-5.1.1 The email account that you tried to reach does not exist ❌

Conclusion: Gmail does NOT have catch-all, individual validation works ✅
```

---

### Example 2: PrivateEmail.com (Catch-All Enabled)

```bash
# MX Lookup
dig +short MX elevau.id
→ 10 mx1.privateemail.com.

# Test valid email
swaks --to ali@elevau.id --from test@test.com \
      --server mx1.privateemail.com --port 25 \
      --quit-after RCPT --tls

Result: 250 2.1.5 Ok ✅

# Test fake email
swaks --to fakeinvalid999@elevau.id --from test@test.com \
      --server mx1.privateemail.com --port 25 \
      --quit-after RCPT --tls

Result: 250 2.1.5 Ok ✅ (ALSO accepted!)

# Test malformed email
swaks --to ali.@elevau.id --from test@test.com \
      --server mx1.privateemail.com --port 25 \
      --quit-after RCPT --tls

Result: 250 2.1.5 Ok ✅ (Even invalid format accepted!)

Conclusion: Catch-all is ENABLED, cannot verify individual mailboxes ⚠️
```

---

## Integration with SOCKS5 Proxy

### Why Use Proxy?
- Avoid IP blocking/rate limiting
- Rotate IPs for bulk validation
- Bypass geographical restrictions

### Tools that Support SOCKS5

**Option 1: proxychains**
```bash
# Configure /etc/proxychains4.conf
socks5  149.81.34.182 1080

# Use with any command
proxychains4 telnet mx.server.com 25
proxychains4 swaks --to email@domain.com ...
```

**Option 2: Python with PySocks**
```python
import socks
import socket

socks.set_default_proxy(socks.SOCKS5, "149.81.34.182", 1080)
socket.socket = socks.socksocket

# Now all connections use SOCKS5
```

---

## Tools Summary

| Tool | Purpose | Pros | Cons |
|------|---------|------|------|
| **dig** | DNS/MX lookup | Fast, simple | DNS only |
| **telnet** | Manual SMTP testing | Good for learning | No TLS support |
| **openssl s_client** | SMTP with TLS | Supports STARTTLS | Complex, can have errors |
| **swaks** | SMTP testing tool | Best for testing | Needs installation |
| **Python smtplib** | Script automation | Full control | Need to code |

---

## Important Considerations

### Security & Ethics
- Don't abuse/spam mail servers
- Rate limit your requests
- Respect server resources
- Use for legitimate verification only

### Limitations
- **Catch-all domains**: Cannot verify individual emails
- **Greylisting**: May need retry logic
- **Rate limiting**: Servers may block excessive checks
- **Privacy**: Some consider this intrusive
- **False positives**: Temporary errors may look like invalid emails

### Best Practices
1. Always check catch-all BEFORE validating individual emails
2. Implement retry logic for 450/451 errors
3. Cache results to avoid repeated checks
4. Use random strings for catch-all detection
5. Handle TLS gracefully (try with/without)
6. Add delays between bulk validations
7. Rotate proxies for large-scale validation

---

## Script Architecture Recommendation

```
Input: Email address + SOCKS5 proxy

↓

1. Format Validation (regex)
   - Invalid format → Return error

↓

2. DNS MX Lookup
   - No MX records → Return error
   - Get mail server address

↓

3. SOCKS5 Connection
   - Connect to mail server via proxy

↓

4. TLS Detection
   - Try without TLS first
   - If 530 → Enable TLS

↓

5. Catch-All Detection (CRITICAL)
   - Test with random email
   - If 250 → Catch-all enabled
   - If 550 → No catch-all

↓

6. Email Validation (if not catch-all)
   - RCPT TO: target email
   - Parse response code

↓

Output: Validation result
{
  valid: true/false,
  catch_all: true/false,
  smtp_code: 250,
  can_receive: true/false,
  reason: "Mailbox exists" / "User not found" / "Mailbox full"
}
```

---

## Testing Data Used

### Test Email 1 (Gmail - Valid)
- Email: `aldodkris@gmail.com`
- MX Server: `gmail-smtp-in.l.google.com`
- Result: Valid, No catch-all

### Test Email 2 (Custom Domain - Catch-All)
- Email: `ali@elevau.id`
- MX Server: `mx1.privateemail.com`
- Result: Valid, Catch-all enabled

### Test SOCKS5 Proxy
- Address: `149.81.34.182:1080`
- Type: SOCKS5

---

## Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Connection refused (port 25) | Port blocked/wrong | Try port 587 or 465 |
| 530 Must issue STARTTLS | TLS required | Enable STARTTLS/TLS |
| SSL renegotiation error | OpenSSL issue | Use swaks or Python instead |
| 421 Too many connections | Rate limited | Add delays, rotate IPs |
| Timeout | Firewall/slow server | Increase timeout, try different MX |
| 252 response | Server won't verify | Use RCPT TO method instead |

---

## Next Steps

1. ✅ Understand the flow (completed)
2. ⏳ Build the script with SOCKS5 support
3. ⏳ Implement catch-all detection
4. ⏳ Add error handling & retries
5. ⏳ Test with various email providers
6. ⏳ Add result caching
7. ⏳ Implement rate limiting