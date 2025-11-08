from emval import EmailValidator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, Tuple, List
import time
import sys

# Configuration
CONCURRENT_JOBS = 10  # Change this to control parallelism

# File paths
DISPOSABLE_DOMAINS_FILE = "data/disposable_domains.txt"
INPUT_FILE = "data/emails.txt"
VALID_OUTPUT = "output/valid_list.txt"
INVALID_OUTPUT = "output/invalid.txt"


def load_disposable_domains() -> Set[str]:
    """Load disposable email domains from local file."""
    print("Loading disposable email domains list...")
    try:
        with open(DISPOSABLE_DOMAINS_FILE, 'r', encoding='utf-8') as f:
            domains = set(line.strip().lower() for line in f if line.strip())
        print(f"Loaded {len(domains)} disposable domains\n")
        return domains
    except FileNotFoundError:
        print(f"Warning: {DISPOSABLE_DOMAINS_FILE} not found!")
        print("Continuing without disposable domain checking...\n")
        return set()
    except Exception as e:
        print(f"Warning: Could not load disposable domains: {e}")
        print("Continuing without disposable domain checking...\n")
        return set()


def is_disposable_email(email: str, disposable_domains: Set[str]) -> bool:
    """Check if email domain is in disposable list."""
    if not disposable_domains:
        return False
    
    try:
        domain = email.split('@')[1].lower()
        return domain in disposable_domains
    except (IndexError, AttributeError):
        return False


def validate_single_email(email: str, validator: EmailValidator, disposable_domains: Set[str]) -> Tuple[str, bool, str]:
    """
    Validate a single email address.
    Returns: (email, is_valid, reason)
    """
    email = email.strip()
    
    if not email:
        return (email, False, "Empty email")
    
    # Check if disposable
    if is_disposable_email(email, disposable_domains):
        return (email, False, "Disposable email domain")
    
    # Validate with emval
    try:
        result = validator.validate_email(email)
        return (email, True, "Valid")
    except Exception as e:
        error_msg = str(e)
        # Shorten error message if too long
        if len(error_msg) > 100:
            error_msg = error_msg[:97] + "..."
        return (email, False, error_msg)


def read_emails(filename: str) -> List[str]:
    """Read emails from input file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            emails = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(emails)} emails from {filename}\n")
        return emails
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found!")
        print(f"Please create {filename} with one email per line.\n")
        return []


def write_results(valid_emails: List[Tuple[str, str]], invalid_emails: List[Tuple[str, str]]):
    """Write validation results to output files."""
    # Write valid emails
    with open(VALID_OUTPUT, 'w', encoding='utf-8') as f:
        for email, _ in valid_emails:
            f.write(f"{email}\n")
    
    # Write invalid emails with reasons
    with open(INVALID_OUTPUT, 'w', encoding='utf-8') as f:
        for email, reason in invalid_emails:
            f.write(f"{email} | {reason}\n")
    
    print(f"\nValid emails saved to: {VALID_OUTPUT}")
    print(f"Invalid emails saved to: {INVALID_OUTPUT}")


def main():
    print("="*70)
    print("BULK EMAIL VALIDATOR")
    print("="*70)
    print(f"Concurrent Jobs: {CONCURRENT_JOBS}\n")
    
    # Initialize validator
    validator = EmailValidator(
        allow_smtputf8=False,
        allow_empty_local=False,
        allow_quoted_local=False,
        allow_domain_literal=False,
        deliverable_address=True,
        allowed_special_domains=[]
    )
    print("Validator configured:")
    print("   - No Unicode characters")
    print("   - No empty local parts")
    print("   - No quoted strings")
    print("   - No IP addresses")
    print("   - DNS deliverability check enabled")
    print("   - No special domains allowed\n")
    
    # Load disposable domains
    disposable_domains = load_disposable_domains()
    
    # Read input emails
    emails = read_emails(INPUT_FILE)
    if not emails:
        return
    
    # Validate emails concurrently
    print(f"Validating {len(emails)} emails with {CONCURRENT_JOBS} concurrent jobs...")
    
    valid_emails = []
    invalid_emails = []
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_JOBS) as executor:
        # Submit all validation tasks
        future_to_email = {
            executor.submit(validate_single_email, email, validator, disposable_domains): email
            for email in emails
        }
        
        # Process results as they complete
        completed = 0
        for future in as_completed(future_to_email):
            email, is_valid, reason = future.result()
            completed += 1
            
            if is_valid:
                valid_emails.append((email, reason))
            else:
                invalid_emails.append((email, reason))
            
            # Dynamic progress indicator - updates on the same line
            percentage = (completed * 100) // len(emails)
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            
            # Use \r to return to start of line and overwrite previous output
            sys.stdout.write(f"\rProgress: {completed}/{len(emails)} - {percentage}% | {speed:.1f} emails/sec | {elapsed:.1f}s")
            sys.stdout.flush()
    
    # Print newline after progress completes
    print()
    
    elapsed_time = time.time() - start_time
    
    # Write results to files
    write_results(valid_emails, invalid_emails)
    
    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Total Emails:     {len(emails)}")
    print(f"Valid:            {len(valid_emails)}")
    print(f"Invalid:          {len(invalid_emails)}")
    print(f"Time Taken:       {elapsed_time:.2f} seconds")
    print(f"Speed:            {len(emails)/elapsed_time:.2f} emails/second")
    print("="*70)


if __name__ == "__main__":
    main()
