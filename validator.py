from emval import EmailValidator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, Tuple, List
import time
import sys
import os

# Configuration
CONCURRENT_JOBS = 1000  # Change this to control parallelism

# File paths
DISPOSABLE_DOMAINS_FILE = "data/disposable_domains.txt"
INPUT_FILE = "data/emails.txt"
VALID_OUTPUT_DIR = "output/valid"
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
    # Create valid output directory if it doesn't exist
    if not os.path.exists(VALID_OUTPUT_DIR):
        os.makedirs(VALID_OUTPUT_DIR, exist_ok=True)
        print(f"Created valid output directory: {VALID_OUTPUT_DIR}")
    
    # Create invalid output directory if it doesn't exist
    invalid_output_dir = os.path.dirname(INVALID_OUTPUT)
    if invalid_output_dir and not os.path.exists(invalid_output_dir):
        os.makedirs(invalid_output_dir, exist_ok=True)
    
    # Group valid emails by domain
    domain_emails = {}
    for email, _ in valid_emails:
        try:
            domain = email.split('@')[1].lower()
            if domain not in domain_emails:
                domain_emails[domain] = []
            domain_emails[domain].append(email)
        except (IndexError, AttributeError):
            # Skip malformed emails (shouldn't happen for valid emails)
            continue
    
    # Write valid emails organized by domain
    total_files_created = 0
    for domain, emails in domain_emails.items():
        # Create a safe filename from domain (replace special chars)
        safe_domain = domain.replace('/', '_').replace('\\', '_')
        domain_file = os.path.join(VALID_OUTPUT_DIR, f"{safe_domain}.txt")
        
        with open(domain_file, 'w', encoding='utf-8') as f:
            for email in sorted(emails):
                f.write(f"{email}\n")
        total_files_created += 1
    
    # Write invalid emails with reasons
    with open(INVALID_OUTPUT, 'w', encoding='utf-8') as f:
        for email, reason in invalid_emails:
            f.write(f"{email} | {reason}\n")
    
    print(f"\nValid emails saved to: {VALID_OUTPUT_DIR}/")
    print(f"  - Created {total_files_created} domain-specific files")
    print(f"  - Total valid emails: {len(valid_emails)}")
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
    print("Starting validation process...")
    print()
    
    valid_emails = []
    invalid_emails = []
    
    start_time = time.time()
    
    # Process in batches to avoid memory issues with large email lists
    completed = 0
    batch_size = 1000  # Submit 1000 emails at a time
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_JOBS) as executor:
        # Process emails in batches
        for batch_start in range(0, len(emails), batch_size):
            batch_end = min(batch_start + batch_size, len(emails))
            batch = emails[batch_start:batch_end]
            
            # Submit current batch
            futures = {
                executor.submit(validate_single_email, email, validator, disposable_domains): email
                for email in batch
            }
            
            # Process this batch's results
            for future in as_completed(futures):
                email, is_valid, reason = future.result()
                completed += 1
                
                if is_valid:
                    valid_emails.append((email, reason))
                else:
                    invalid_emails.append((email, reason))
                
                # Calculate and show real-time progress on same line
                current_time = time.time()
                percentage = (completed * 100.0) / len(emails)
                elapsed = current_time - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                
                # Calculate ETA
                if speed > 0:
                    remaining = len(emails) - completed
                    eta_seconds = remaining / speed
                    eta_minutes = int(eta_seconds // 60)
                    eta_secs = int(eta_seconds % 60)
                    eta_str = f"{eta_minutes}m {eta_secs}s" if eta_minutes > 0 else f"{eta_secs}s"
                else:
                    eta_str = "calculating..."
                
                # Print progress on same line with carriage return
                print(f"{completed}/{len(emails)} - {percentage:.1f}% | Valid: {len(valid_emails)} | Invalid: {len(invalid_emails)} | Speed: {speed:.1f}/sec | ETA: {eta_str}", end='\r', flush=True)
    
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
