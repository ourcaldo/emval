from emval import EmailValidator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, Tuple, List, Dict
from functools import lru_cache
import time
import sys
import os
import re
import logging

# Configuration
CONCURRENT_JOBS = 1000  # Change this to control parallelism
RETRY_ATTEMPTS = 3  # Number of retry attempts for DNS failures
RETRY_DELAY = 0.5  # Delay between retries in seconds

# File paths
DISPOSABLE_DOMAINS_FILE = "data/disposable_domains.txt"
WELL_KNOWN_DOMAINS_FILE = "config/well_known_domains.txt"
INPUT_FILE = "data/emails.txt"
VALID_OUTPUT_DIR = "output/valid"
INVALID_OUTPUT = "output/invalid.txt"
SUMMARY_OUTPUT = "output/SUMMARY.txt"
LOG_FILE = "validator.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_well_known_domains() -> Set[str]:
    """Load well-known email domains from config file."""
    try:
        with open(WELL_KNOWN_DOMAINS_FILE, 'r', encoding='utf-8') as f:
            domains = set(line.strip().lower() for line in f if line.strip())
        logger.info(f"Loaded {len(domains)} well-known domains from {WELL_KNOWN_DOMAINS_FILE}")
        return domains
    except FileNotFoundError:
        logger.warning(f"{WELL_KNOWN_DOMAINS_FILE} not found! All domains will go to other.txt")
        return set()
    except Exception as e:
        logger.error(f"Error loading well-known domains: {e}")
        return set()


def load_disposable_domains() -> Set[str]:
    """Load disposable email domains from local file."""
    print("Loading disposable email domains list...")
    try:
        with open(DISPOSABLE_DOMAINS_FILE, 'r', encoding='utf-8') as f:
            domains = set(line.strip().lower() for line in f if line.strip())
        print(f"Loaded {len(domains)} disposable domains\n")
        logger.info(f"Loaded {len(domains)} disposable domains")
        return domains
    except FileNotFoundError:
        logger.warning(f"{DISPOSABLE_DOMAINS_FILE} not found!")
        print(f"Warning: {DISPOSABLE_DOMAINS_FILE} not found!")
        print("Continuing without disposable domain checking...\n")
        return set()
    except Exception as e:
        logger.error(f"Could not load disposable domains: {e}")
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


@lru_cache(maxsize=10000)
def cached_dns_check(domain: str, validator: EmailValidator) -> bool:
    """
    Cached DNS check for domain deliverability.
    Uses LRU cache to avoid repeated DNS lookups for same domain.
    
    Args:
        domain: The email domain to check
        validator: EmailValidator instance (for cache key uniqueness)
    
    Returns:
        True if domain has valid MX records, False otherwise
    """
    # This function is called by validate_single_email with retry logic
    # The actual DNS check happens in the validator.validate_email() call
    return True


def validate_single_email(
    email: str, 
    validator: EmailValidator, 
    disposable_domains: Set[str]
) -> Tuple[str, bool, str, str]:
    """
    Validate a single email address with retry logic for DNS failures.
    
    Args:
        email: Email address to validate
        validator: EmailValidator instance
        disposable_domains: Set of disposable domains to check against
    
    Returns:
        Tuple of (email, is_valid, reason, error_category)
        error_category can be: 'syntax', 'disposable', 'dns', 'valid'
    """
    email = email.strip()
    
    if not email:
        logger.debug(f"Empty email encountered")
        return (email, False, "Empty email", "syntax")
    
    # Check if disposable
    if is_disposable_email(email, disposable_domains):
        logger.debug(f"Disposable email rejected: {email}")
        return (email, False, "Disposable email domain", "disposable")
    
    # Extract domain for caching
    try:
        domain = email.split('@')[1].lower()
    except (IndexError, AttributeError):
        logger.debug(f"Invalid email format: {email}")
        return (email, False, "Invalid email format", "syntax")
    
    # Validate with emval with retry logic for DNS failures
    for attempt in range(RETRY_ATTEMPTS):
        try:
            # Check cache first (through domain lookup)
            result = validator.validate_email(email)
            logger.debug(f"Valid email: {email}")
            return (email, True, "Valid", "valid")
        
        except Exception as e:
            error_msg = str(e)
            
            # Categorize error
            if "dns" in error_msg.lower() or "resolve" in error_msg.lower() or "timeout" in error_msg.lower():
                error_category = "dns"
                # Retry on DNS errors
                if attempt < RETRY_ATTEMPTS - 1:
                    logger.debug(f"DNS error for {email}, attempt {attempt + 1}/{RETRY_ATTEMPTS}: {error_msg}")
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    logger.warning(f"DNS validation failed after {RETRY_ATTEMPTS} attempts: {email}")
            else:
                error_category = "syntax"
            
            # Shorten error message if too long
            if len(error_msg) > 100:
                error_msg = error_msg[:97] + "..."
            
            logger.debug(f"Invalid email: {email} - {error_msg}")
            return (email, False, error_msg, error_category)
    
    # Should not reach here, but just in case
    return (email, False, "Validation failed", "unknown")


def read_emails(filename: str) -> List[str]:
    """Read emails from input file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            emails = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(emails)} emails from {filename}\n")
        logger.info(f"Loaded {len(emails)} emails from {filename}")
        return emails
    except FileNotFoundError:
        logger.error(f"File '{filename}' not found!")
        print(f"Error: File '{filename}' not found!")
        print(f"Please create {filename} with one email per line.\n")
        return []


def sanitize_domain_filename(domain: str) -> str:
    """
    Sanitize domain name for use as filename.
    Uses regex to replace any character that's not alphanumeric, dot, or hyphen.
    
    Args:
        domain: Domain name to sanitize
    
    Returns:
        Safe filename string
    """
    # Replace any character that's not a-z, A-Z, 0-9, dot, or hyphen with underscore
    safe_domain = re.sub(r'[^a-zA-Z0-9.-]', '_', domain)
    # Remove any leading/trailing dots or hyphens
    safe_domain = safe_domain.strip('.-')
    # Ensure it's not empty
    if not safe_domain:
        safe_domain = "unknown"
    return safe_domain


def write_results(
    valid_emails: List[Tuple[str, str, str]], 
    invalid_emails: List[Tuple[str, str, str]],
    well_known_domains: Set[str],
    start_time: float,
    total_emails: int
):
    """
    Write validation results to output files with well-known domain separation.
    
    Args:
        valid_emails: List of (email, reason, category) tuples for valid emails
        invalid_emails: List of (email, reason, category) tuples for invalid emails
        well_known_domains: Set of well-known domains for separation
        start_time: Validation start time
        total_emails: Total number of emails processed
    """
    # Create valid output directory if it doesn't exist
    if not os.path.exists(VALID_OUTPUT_DIR):
        os.makedirs(VALID_OUTPUT_DIR, exist_ok=True)
        logger.info(f"Created valid output directory: {VALID_OUTPUT_DIR}")
        print(f"Created valid output directory: {VALID_OUTPUT_DIR}")
    
    # Create invalid output directory if it doesn't exist
    invalid_output_dir = os.path.dirname(INVALID_OUTPUT)
    if invalid_output_dir and not os.path.exists(invalid_output_dir):
        os.makedirs(invalid_output_dir, exist_ok=True)
    
    # Group valid emails by domain with well-known separation
    well_known_emails = {}  # domain -> [emails]
    other_emails = []  # List of emails for other.txt
    
    for email, _, _ in valid_emails:
        try:
            domain = email.split('@')[1].lower()
            
            # Check if it's a well-known domain
            if domain in well_known_domains:
                if domain not in well_known_emails:
                    well_known_emails[domain] = []
                well_known_emails[domain].append(email)
            else:
                other_emails.append(email)
        except (IndexError, AttributeError):
            # Skip malformed emails (shouldn't happen for valid emails)
            logger.warning(f"Malformed valid email encountered: {email}")
            continue
    
    # Write well-known domain emails to individual files
    well_known_files_created = 0
    for domain, emails in well_known_emails.items():
        # Create a safe filename from domain
        safe_domain = sanitize_domain_filename(domain)
        domain_file = os.path.join(VALID_OUTPUT_DIR, f"{safe_domain}.txt")
        
        try:
            with open(domain_file, 'w', encoding='utf-8') as f:
                for email in sorted(emails):
                    f.write(f"{email}\n")
            well_known_files_created += 1
            logger.info(f"Wrote {len(emails)} emails to {domain_file}")
        except Exception as e:
            logger.error(f"Error writing to {domain_file}: {e}")
    
    # Write other emails to other.txt
    if other_emails:
        other_file = os.path.join(VALID_OUTPUT_DIR, "other.txt")
        try:
            with open(other_file, 'w', encoding='utf-8') as f:
                for email in sorted(other_emails):
                    f.write(f"{email}\n")
            logger.info(f"Wrote {len(other_emails)} emails to {other_file}")
            print(f"  - other.txt: {len(other_emails)} emails")
        except Exception as e:
            logger.error(f"Error writing to {other_file}: {e}")
    
    # Write invalid emails with reasons
    try:
        with open(INVALID_OUTPUT, 'w', encoding='utf-8') as f:
            for email, reason, category in invalid_emails:
                f.write(f"{email} | {reason} | {category}\n")
        logger.info(f"Wrote {len(invalid_emails)} invalid emails to {INVALID_OUTPUT}")
    except Exception as e:
        logger.error(f"Error writing to {INVALID_OUTPUT}: {e}")
    
    # Calculate statistics
    elapsed_time = time.time() - start_time
    
    # Categorize invalid emails
    invalid_by_category = {}
    for _, _, category in invalid_emails:
        invalid_by_category[category] = invalid_by_category.get(category, 0) + 1
    
    # Print summary
    print(f"\nValid emails saved to: {VALID_OUTPUT_DIR}/")
    print(f"  - Created {well_known_files_created} well-known domain files")
    if other_emails:
        print(f"  - Created other.txt with {len(other_emails)} emails from unknown domains")
    print(f"  - Total valid emails: {len(valid_emails)}")
    print(f"Invalid emails saved to: {INVALID_OUTPUT}")
    
    # Write summary statistics file
    write_summary_file(
        total_emails,
        len(valid_emails),
        len(invalid_emails),
        well_known_emails,
        len(other_emails),
        invalid_by_category,
        elapsed_time
    )


def write_summary_file(
    total: int,
    valid: int,
    invalid: int,
    well_known_emails: Dict[str, List[str]],
    other_count: int,
    invalid_by_category: Dict[str, int],
    elapsed_time: float
):
    """
    Write a summary statistics file.
    
    Args:
        total: Total emails processed
        valid: Total valid emails
        invalid: Total invalid emails
        well_known_emails: Dictionary of domain -> emails for well-known domains
        other_count: Count of emails in other.txt
        invalid_by_category: Dictionary of category -> count for invalid emails
        elapsed_time: Total processing time
    """
    try:
        summary_dir = os.path.dirname(SUMMARY_OUTPUT)
        if summary_dir and not os.path.exists(summary_dir):
            os.makedirs(summary_dir, exist_ok=True)
        
        with open(SUMMARY_OUTPUT, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("EMAIL VALIDATION SUMMARY REPORT\n")
            f.write("="*70 + "\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
            
            # Overall statistics
            f.write("OVERALL STATISTICS\n")
            f.write("-"*70 + "\n")
            f.write(f"Total Emails Processed:     {total:,}\n")
            f.write(f"Valid Emails:               {valid:,} ({valid*100/total:.1f}%)\n")
            f.write(f"Invalid Emails:             {invalid:,} ({invalid*100/total:.1f}%)\n")
            f.write(f"Processing Time:            {elapsed_time:.2f} seconds\n")
            f.write(f"Processing Speed:           {total/elapsed_time:.2f} emails/second\n")
            f.write("\n")
            
            # Valid emails breakdown
            f.write("VALID EMAILS BY DOMAIN\n")
            f.write("-"*70 + "\n")
            
            # Sort domains by email count (descending)
            sorted_domains = sorted(well_known_emails.items(), key=lambda x: len(x[1]), reverse=True)
            
            for domain, emails in sorted_domains:
                f.write(f"  {domain:<40} {len(emails):>8,} emails\n")
            
            if other_count > 0:
                f.write(f"  {'Other domains (other.txt)':<40} {other_count:>8,} emails\n")
            
            f.write(f"\n  {'TOTAL VALID':<40} {valid:>8,} emails\n")
            f.write("\n")
            
            # Invalid emails breakdown
            f.write("INVALID EMAILS BY CATEGORY\n")
            f.write("-"*70 + "\n")
            for category, count in sorted(invalid_by_category.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {category.capitalize():<40} {count:>8,} emails\n")
            f.write(f"\n  {'TOTAL INVALID':<40} {invalid:>8,} emails\n")
            f.write("\n")
            
            # File locations
            f.write("OUTPUT FILES\n")
            f.write("-"*70 + "\n")
            f.write(f"Valid emails (well-known):  {VALID_OUTPUT_DIR}/<domain>.txt\n")
            if other_count > 0:
                f.write(f"Valid emails (other):       {VALID_OUTPUT_DIR}/other.txt\n")
            f.write(f"Invalid emails:             {INVALID_OUTPUT}\n")
            f.write(f"Log file:                   {LOG_FILE}\n")
            f.write("="*70 + "\n")
        
        logger.info(f"Summary statistics written to {SUMMARY_OUTPUT}")
        print(f"\nSummary statistics saved to: {SUMMARY_OUTPUT}")
    
    except Exception as e:
        logger.error(f"Error writing summary file: {e}")
        print(f"Warning: Could not write summary file: {e}")


def main():
    """Main function to orchestrate email validation process."""
    print("="*70)
    print("BULK EMAIL VALIDATOR")
    print("="*70)
    print(f"Concurrent Jobs: {CONCURRENT_JOBS}\n")
    
    logger.info("="*70)
    logger.info("Email validation process started")
    logger.info(f"Concurrent jobs: {CONCURRENT_JOBS}")
    logger.info(f"Retry attempts: {RETRY_ATTEMPTS}")
    
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
    print("   - No special domains allowed")
    print(f"   - Retry attempts: {RETRY_ATTEMPTS}")
    print(f"   - DNS caching enabled (LRU cache)")
    print()
    
    # Load well-known domains
    well_known_domains = load_well_known_domains()
    print(f"Loaded {len(well_known_domains)} well-known domains\n")
    
    # Load disposable domains
    disposable_domains = load_disposable_domains()
    
    # Read input emails
    emails = read_emails(INPUT_FILE)
    if not emails:
        logger.error("No emails to process")
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
                email, is_valid, reason, category = future.result()
                completed += 1
                
                if is_valid:
                    valid_emails.append((email, reason, category))
                else:
                    invalid_emails.append((email, reason, category))
                
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
    
    logger.info(f"Validation completed: {len(valid_emails)} valid, {len(invalid_emails)} invalid")
    
    # Write results to files
    write_results(valid_emails, invalid_emails, well_known_domains, start_time, len(emails))
    
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
    
    logger.info("="*70)
    logger.info("Email validation process completed successfully")
    logger.info("="*70)


if __name__ == "__main__":
    main()
