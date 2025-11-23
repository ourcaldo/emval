# Dynamic Terminal Progress Display Guide

## Overview
This guide shows how to create a **dynamic, in-place updating progress display** in terminal instead of appending new lines. This creates a cleaner, more compact output that's easier to read.

---

## The Problem

**Current behavior (appending lines):**
```
1/19 - 5.3% | Valid: 1 | Invalid: 0
2/19 - 10.5% | Valid: 2 | Invalid: 0
3/19 - 15.8% | Valid: 3 | Invalid: 0
4/19 - 21.1% | Valid: 4 | Invalid: 0
... (fills up terminal)
```

**Desired behavior (dynamic update):**
```
12/19 (63.2%) | Valid: 7 | Risk: 0 | Invalid: 5 | Speed: 328/s
(This line updates in place, not appending new lines)
```

---

## The Solution: Use Carriage Return (`\r`)

Instead of printing new lines, **overwrite the same line** using:
- `\r` (carriage return) - moves cursor back to start of line
- `end=''` - prevents automatic newline
- `flush=True` - forces immediate output to terminal

---

## Method 1: Simple Single-Line Progress (Recommended)

### Basic Example

```python
import time

total = 100
for i in range(1, total + 1):
    # Calculate progress
    progress = (i / total) * 100
    
    # Print with \r to overwrite same line
    print(f"\rProgress: {progress:.1f}% - {i}/{total}", end='', flush=True)
    
    time.sleep(0.1)  # Simulate work

print("\nDone!")  # Print newline at the end
```

### For Email Validator (Single Line)

```python
def print_progress_compact(current, total, valid, risk, invalid, unknown, speed):
    """
    Single line dynamic progress - overwrites same line
    """
    progress = (current / total) * 100
    
    # Build compact progress string
    status = (
        f"\r{current}/{total} ({progress:.1f}%) | "
        f"Valid: {valid} | Risk: {risk} | Invalid: {invalid} | Unknown: {unknown} | "
        f"Speed: {speed:.1f}/s"
    )
    
    # Print and pad with spaces to clear any leftover characters from previous line
    print(status.ljust(120), end='', flush=True)


# Usage in validation loop
for i, email in enumerate(emails, 1):
    # ... your validation logic ...
    
    print_progress_compact(
        current=i,
        total=len(emails),
        valid=valid_count,
        risk=risk_count,
        invalid=invalid_count,
        unknown=unknown_count,
        speed=current_speed
    )

# IMPORTANT: Print newline at the end to move to next line
print()
```

**Output (single line that updates):**
```
12/19 (63.2%) | Valid: 7 | Risk: 0 | Invalid: 5 | Unknown: 0 | Speed: 328.0/s
```

---

## Method 2: Multi-Line Progress with ANSI Escape Codes

For a dashboard-style display with multiple lines that update in place:

### Using ANSI Escape Codes

```python
import sys

class ProgressDisplay:
    """
    Multi-line dynamic progress display using ANSI escape codes
    """
    def __init__(self):
        self.lines_printed = 0
    
    def clear_previous(self):
        """Move cursor up and clear previous lines"""
        if self.lines_printed > 0:
            # Move cursor up N lines
            sys.stdout.write(f'\033[{self.lines_printed}A')
            # Clear from cursor to end of screen
            sys.stdout.write('\033[J')
    
    def print_progress(self, current, total, valid, risk, invalid, unknown, speed):
        """Print multi-line progress display"""
        # Clear previous output
        self.clear_previous()
        
        progress = (current / total) * 100
        
        # Create progress bar
        bar_length = 40
        filled = int(bar_length * current // total)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Build output lines
        lines = [
            "=" * 60,
            f"Progress: [{bar}] {progress:.1f}%",
            f"Status: {current}/{total} emails processed",
            "",
            f"✓ Valid:   {valid:>5}",
            f"⚠ Risk:    {risk:>5}",
            f"✗ Invalid: {invalid:>5}",
            f"? Unknown: {unknown:>5}",
            "",
            f"Speed: {speed:.1f} emails/sec",
            "=" * 60,
        ]
        
        # Print all lines
        output = '\n'.join(lines)
        print(output, flush=True)
        
        # Remember how many lines we printed for next clear
        self.lines_printed = len(lines)


# Usage
display = ProgressDisplay()

for i, email in enumerate(emails, 1):
    # ... validation logic ...
    
    display.print_progress(
        current=i,
        total=len(emails),
        valid=valid_count,
        risk=risk_count,
        invalid=invalid_count,
        unknown=unknown_count,
        speed=current_speed
    )

# Final newline
print("\nValidation completed!")
```

**Output (updates entire block in place):**
```
============================================================
Progress: [████████████████████░░░░░░░░░░░░░░░░░░░░] 52.6%
Status: 10/19 emails processed

✓ Valid:       6
⚠ Risk:        0
✗ Invalid:     4
? Unknown:     0

Speed: 278.0 emails/sec
============================================================
```

---

## Method 3: Compact Multi-Line (No ANSI)

If you want multiple lines but simpler implementation:

```python
def print_progress_multiline(current, total, valid, risk, invalid, unknown, speed):
    """
    Multi-line compact progress (simpler version)
    """
    progress = (current / total) * 100
    
    # Build multi-line output
    output = (
        f"\rProgress: {progress:.1f}% ({current}/{total}) | "
        f"Valid: {valid} | Risk: {risk} | Invalid: {invalid} | Unknown: {unknown} | "
        f"Speed: {speed:.1f}/s\n"
        f"{'=' * 80}\n"
    )
    
    print(output, end='', flush=True)

# Usage
for i, email in enumerate(emails, 1):
    print_progress_multiline(i, len(emails), valid, risk, invalid, unknown, speed)

print("\nDone!")
```

---

## Quick Fix for Existing Code

### Find This Pattern (Appending):
```python
# Current code that appends lines
print(f"{i}/{total} - {progress}% | Valid: {valid} | Invalid: {invalid}")
```

### Replace With (Dynamic):
```python
# Dynamic update - overwrites same line
print(f"\r{i}/{total} - {progress:.1f}% | Valid: {valid} | Invalid: {invalid}", 
      end='', flush=True)
```

### Add at End of Loop:
```python
# After validation loop completes
print()  # Print newline to move to next line for summary
```

---

## Complete Example for Email Validator

```python
import time
import sys

def validate_emails_with_progress(emails):
    """
    Email validation with dynamic progress display
    """
    total = len(emails)
    valid_count = 0
    risk_count = 0
    invalid_count = 0
    unknown_count = 0
    
    start_time = time.time()
    
    print("Starting email validation...\n")
    
    for i, email in enumerate(emails, 1):
        # Your validation logic here
        # result = validate_email(email)
        # Update counters based on result
        
        # Simulate validation
        time.sleep(0.05)
        valid_count += 1  # Example
        
        # Calculate speed
        elapsed = time.time() - start_time
        speed = i / elapsed if elapsed > 0 else 0
        
        # Calculate progress
        progress = (i / total) * 100
        
        # Dynamic progress display (single line)
        status = (
            f"\r{i}/{total} ({progress:.1f}%) | "
            f"Valid: {valid_count} | Risk: {risk_count} | "
            f"Invalid: {invalid_count} | Unknown: {unknown_count} | "
            f"Speed: {speed:.1f}/s"
        )
        print(status.ljust(120), end='', flush=True)
    
    # Move to next line after progress completes
    print("\n")
    
    # Print final summary
    total_time = time.time() - start_time
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Emails:     {total}")
    print(f"Valid (safe):     {valid_count}")
    print(f"Risk (catch-all): {risk_count}")
    print(f"Invalid:          {invalid_count}")
    print(f"Unknown:          {unknown_count}")
    print(f"Time Taken:       {total_time:.2f} seconds")
    print(f"Speed:            {total/total_time:.2f} emails/second")
    print("=" * 70)


# Example usage
emails = ["user1@example.com", "user2@example.com", "user3@example.com"]
validate_emails_with_progress(emails)
```

---

## ANSI Escape Codes Reference

| Code | Purpose |
|------|---------|
| `\r` | Move cursor to start of current line (carriage return) |
| `\n` | Move cursor to next line (newline) |
| `\033[A` | Move cursor up one line |
| `\033[B` | Move cursor down one line |
| `\033[C` | Move cursor right one column |
| `\033[D` | Move cursor left one column |
| `\033[K` | Clear line from cursor to end |
| `\033[J` | Clear screen from cursor to end |
| `\033[{n}A` | Move cursor up n lines |
| `\033[H` | Move cursor to home position (0,0) |
| `\033[2J` | Clear entire screen |

---

## Key Techniques Summary

| Technique | Purpose | Usage |
|-----------|---------|-------|
| `\r` | Move cursor to line start | `print("\rProgress...", end='')` |
| `end=''` | Don't add newline | `print("text", end='')` |
| `flush=True` | Force immediate output | `print("text", flush=True)` |
| `.ljust(n)` | Pad with spaces to clear old text | `status.ljust(120)` |
| `\033[A` | Move cursor up (ANSI) | `sys.stdout.write('\033[5A')` |
| `\033[K` | Clear line (ANSI) | `sys.stdout.write('\033[K')` |
| `\033[J` | Clear to end of screen | `sys.stdout.write('\033[J')` |

---

## Recommended Implementation

For your email validator, I recommend **Method 1 (Single Line)** because:

1. ✅ Simple to implement
2. ✅ Works on all terminals
3. ✅ Clean and easy to read
4. ✅ No complex ANSI codes needed
5. ✅ Fast and efficient

### Implementation Steps:

1. **Find your current progress print statement**
2. **Add `\r` at the start, `end=''`, and `flush=True`**
3. **Add `.ljust(120)` to clear leftover characters**
4. **Add `print()` after the loop to move to next line**

---

## Example: Before & After

### Before (Appending Lines):
```python
for i, email in enumerate(emails, 1):
    progress = (i / len(emails)) * 100
    print(f"{i}/{len(emails)} - {progress:.1f}% | Valid: {valid}")
```

**Terminal Output:**
```
1/19 - 5.3% | Valid: 1
2/19 - 10.5% | Valid: 2
3/19 - 15.8% | Valid: 3
(keeps appending...)
```

### After (Dynamic Update):
```python
for i, email in enumerate(emails, 1):
    progress = (i / len(emails)) * 100
    status = f"\r{i}/{len(emails)} - {progress:.1f}% | Valid: {valid}"
    print(status.ljust(100), end='', flush=True)

print()  # Move to next line when done
```

**Terminal Output:**
```
12/19 - 63.2% | Valid: 7
(This line updates in place)
```

---

## Progress Bar Example

```python
def print_progress_bar(current, total, prefix='', length=50):
    """
    Print a progress bar with percentage
    """
    percent = 100 * (current / float(total))
    filled = int(length * current // total)
    bar = '█' * filled + '-' * (length - filled)
    
    print(f'\r{prefix} |{bar}| {percent:.1f}% ({current}/{total})', end='', flush=True)
    
    # Print newline when complete
    if current == total:
        print()


# Usage
for i in range(1, 101):
    print_progress_bar(i, 100, prefix='Progress')
    time.sleep(0.05)
```

**Output:**
```
Progress |██████████████████████████------------------------| 52.0% (52/100)
```

---

## Troubleshooting

### Issue: Old text remains visible
**Solution:** Use `.ljust(n)` to pad with spaces
```python
print(status.ljust(120), end='', flush=True)
```

### Issue: Progress not updating immediately
**Solution:** Add `flush=True`
```python
print(status, end='', flush=True)
```

### Issue: Cursor jumps around
**Solution:** Make sure to use `end=''` and only `print()` at the very end
```python
# During loop
print("\rProgress", end='', flush=True)

# After loop
print()  # Single newline
```

### Issue: Doesn't work in file output
**Note:** Dynamic progress only works in **interactive terminals**, not when redirecting to files
```bash
python script.py          # Works (terminal)
python script.py > log    # Won't work (file redirect)
```

**Solution:** Detect if output is a terminal
```python
import sys

if sys.stdout.isatty():
    # Use dynamic progress
    print(f"\rProgress: {i}", end='', flush=True)
else:
    # Use regular logging for file output
    print(f"Progress: {i}")
```

---

## Best Practices

1. **Always add `print()` at the end** to move to next line
2. **Use `.ljust()` to clear leftover text** from longer previous lines
3. **Add `flush=True`** for immediate display
4. **Keep status line under 120 characters** to avoid wrapping on most terminals
5. **Test on your target terminal** (some terminals handle ANSI differently)
6. **Use `sys.stdout.isatty()`** to detect if output is to terminal or file

---

## Integration with Your Email Validator

Based on your log output, here's what to change:

### Current Code (somewhere in your validation loop):
```python
# Find something like this
print(f"{i}/{total} - {progress}% | Valid: {valid} | Risk: {risk} | Invalid: {invalid} | Unknown: {unknown} | Speed: {speed}")
```

### Replace With:
```python
# Dynamic single-line progress
status = (
    f"\r{i}/{total} ({progress:.1f}%) | "
    f"Valid: {valid} | Risk: {risk} | Invalid: {invalid} | Unknown: {unknown} | "
    f"Speed: {speed:.1f}/s"
)
print(status.ljust(120), end='', flush=True)
```

### After Validation Loop:
```python
# Move to next line
print("\n")

# Then print your summary
print("=" * 70)
print("VALIDATION SUMMARY")
# ... rest of summary
```

---

## Complete Working Example

```python
#!/usr/bin/env python3
import time
import random

def validate_email_batch(emails):
    """
    Email validator with dynamic progress display
    """
    total = len(emails)
    valid = 0
    risk = 0
    invalid = 0
    unknown = 0
    
    start_time = time.time()
    
    print("Email Validation Started\n")
    
    for i, email in enumerate(emails, 1):
        # Simulate validation
        time.sleep(0.1)
        result = random.choice(['valid', 'valid', 'invalid'])
        
        if result == 'valid':
            valid += 1
        elif result == 'invalid':
            invalid += 1
        
        # Calculate metrics
        elapsed = time.time() - start_time
        speed = i / elapsed if elapsed > 0 else 0
        progress = (i / total) * 100
        eta = (total - i) / speed if speed > 0 else 0
        
        # Dynamic progress (single line)
        status = (
            f"\r{i}/{total} ({progress:.1f}%) | "
            f"Valid: {valid} | Risk: {risk} | Invalid: {invalid} | Unknown: {unknown} | "
            f"Speed: {speed:.1f}/s | ETA: {eta:.0f}s"
        )
        print(status.ljust(120), end='', flush=True)
    
    # Validation complete - move to next line
    print("\n")
    
    # Print summary
    total_time = time.time() - start_time
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Emails:     {total}")
    print(f"Valid (safe):     {valid}")
    print(f"Risk (catch-all): {risk}")
    print(f"Invalid:          {invalid}")
    print(f"Unknown:          {unknown}")
    print(f"Time Taken:       {total_time:.2f} seconds")
    print(f"Speed:            {total/total_time:.2f} emails/second")
    print("=" * 70)


if __name__ == "__main__":
    # Test with sample emails
    test_emails = [f"user{i}@example.com" for i in range(1, 51)]
    validate_email_batch(test_emails)
```

---

## Summary

**Quick Fix (3 steps):**
1. Add `\r` at start: `print(f"\r{progress}...")`
2. Add `end=''` and `flush=True`: `print(..., end='', flush=True)`
3. Add `print()` after loop to move to next line

**Result:** Clean, compact, easy-to-read progress that updates in place instead of filling up your terminal!
