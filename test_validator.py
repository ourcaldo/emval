from emval import EmailValidator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, Tuple, List
import time
import sys
import os

# Configuration
CONCURRENT_JOBS = 10

# File paths
DISPOSABLE_DOMAINS_FILE = "data/disposable_domains.txt"
INPUT_FILE = "data/emails_quick_test.txt"
VALID_OUTPUT_DIR = "output/test_valid"
INVALID_OUTPUT = "output/test_invalid.txt"


def load_disposable_domains() -> Set[str]:
    """Load disposable email domains from local file."""
    try:
        with open(DISPOSABLE_DOMAINS_FILE, 'r', encoding='utf-8') as f:
            domains = set(line.strip().lower() for line in f if line.strip())
        return domains
    except:
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
    """Validate a single email address."""
    email = email.strip()
    
    if not email:
        return (email, False, "Empty email")
    
    if is_disposable_email(email, disposable_domains):
        return (email, False, "Disposable email domain")
    
    try:
        result = validator.validate_email(email)
        return (email, True, "Valid")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:97] + "..."
        return (email, False, error_msg)


def read_emails(filename: str) -> List[str]:
    """Read emails from input file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            emails = [line.strip() for line in f if line.strip()]
        return emails
    except FileNotFoundError:
        return []


def write_results(valid_emails: List[Tuple[str, str]], invalid_emails: List[Tuple[str, str]]):
    """Write validation results to output files."""
    # Create valid output directory if it doesn't exist
    if not os.path.exists(VALID_OUTPUT_DIR):
        os.makedirs(VALID_OUTPUT_DIR, exist_ok=True)
        print(f"✓ Created valid output directory: {VALID_OUTPUT_DIR}")
    
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
            continue
    
    # Write valid emails organized by domain
    total_files_created = 0
    for domain, emails in domain_emails.items():
        safe_domain = domain.replace('/', '_').replace('\\', '_')
        domain_file = os.path.join(VALID_OUTPUT_DIR, f"{safe_domain}.txt")
        
        with open(domain_file, 'w', encoding='utf-8') as f:
            for email in sorted(emails):
                f.write(f"{email}\n")
        total_files_created += 1
        print(f"  ✓ Created: {safe_domain}.txt ({len(emails)} emails)")
    
    # Write invalid emails with reasons
    with open(INVALID_OUTPUT, 'w', encoding='utf-8') as f:
        for email, reason in invalid_emails:
            f.write(f"{email} | {reason}\n")
    
    print(f"\n✓ Valid emails saved to: {VALID_OUTPUT_DIR}/")
    print(f"  - Created {total_files_created} domain-specific files")
    print(f"  - Total valid emails: {len(valid_emails)}")
    print(f"✓ Invalid emails saved to: {INVALID_OUTPUT}")


def main():
    print("="*70)
    print("TESTING NEW DIRECTORY OUTPUT STRUCTURE")
    print("="*70)
    
    validator = EmailValidator(
        allow_smtputf8=False,
        allow_empty_local=False,
        allow_quoted_local=False,
        allow_domain_literal=False,
        deliverable_address=True,
        allowed_special_domains=[]
    )
    
    disposable_domains = load_disposable_domains()
    emails = read_emails(INPUT_FILE)
    
    if not emails:
        print("No emails to test")
        return
    
    print(f"Testing with {len(emails)} emails...\n")
    
    valid_emails = []
    invalid_emails = []
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_JOBS) as executor:
        futures = {
            executor.submit(validate_single_email, email, validator, disposable_domains): email
            for email in emails
        }
        
        for future in as_completed(futures):
            email, is_valid, reason = future.result()
            if is_valid:
                valid_emails.append((email, reason))
            else:
                invalid_emails.append((email, reason))
    
    write_results(valid_emails, invalid_emails)
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total:   {len(emails)}")
    print(f"Valid:   {len(valid_emails)}")
    print(f"Invalid: {len(invalid_emails)}")
    print("="*70)


if __name__ == "__main__":
    main()
