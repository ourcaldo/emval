"""
Bulk Email Validator - Main Entry Point

This is a modular, testable email validation system that:
- Validates email syntax and DNS deliverability
- Blocks disposable email domains
- Separates well-known domains from others
- Generates comprehensive reports

All configuration is externalized in config/settings.yaml
"""

from validators import EmailValidationService, DNSChecker, DisposableDomainChecker, EmailIOHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import time
import sys
import logging

# Load configuration from YAML file
def load_config(config_file: str = "config/settings.yaml") -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found!")
        print("Please ensure config/settings.yaml exists.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)


def setup_logging(config: dict):
    """
    Setup logging based on configuration.
    
    Args:
        config: Configuration dictionary
    """
    log_config = config.get('logging', {})
    log_file = config.get('paths', {}).get('log_file', 'validator.log')
    
    handlers = []
    handlers.append(logging.FileHandler(log_file))
    
    if log_config.get('console_output', True):
        handlers.append(logging.StreamHandler(sys.stdout))
    
    logging.basicConfig(
        level=getattr(logging, log_config.get('level', 'INFO')),
        format=log_config.get('format', '%(asctime)s - %(levelname)s - %(message)s'),
        handlers=handlers
    )


def main():
    """Main function - orchestrates the email validation process."""
    
    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config)
    logger = logging.getLogger(__name__)
    
    # Extract configuration
    concurrency_config = config.get('concurrency', {})
    retry_config = config.get('retry', {})
    dns_cache_config = config.get('dns_cache', {})
    validation_config = config.get('validation', {})
    paths_config = config.get('paths', {})
    
    concurrent_jobs = concurrency_config.get('max_workers', 1000)
    batch_size = concurrency_config.get('batch_size', 1000)
    
    # Print header
    print("="*70)
    print("BULK EMAIL VALIDATOR")
    print("="*70)
    print(f"Concurrent Jobs: {concurrent_jobs}\n")
    
    logger.info("="*70)
    logger.info("Email validation process started")
    logger.info(f"Concurrent jobs: {concurrent_jobs}")
    logger.info(f"Retry attempts: {retry_config.get('attempts', 3)}")
    
    # Initialize components
    print("Initializing validation components...")
    
    # 1. Disposable domain checker
    disposable_checker = DisposableDomainChecker(
        disposable_domains_file=paths_config.get('disposable_domains', 'data/disposable_domains.txt')
    )
    
    # 2. DNS checker with caching
    dns_checker = DNSChecker(
        cache_size=dns_cache_config.get('max_size', 10000)
    )
    
    # 3. Email validation service
    validation_service = EmailValidationService(
        disposable_checker=disposable_checker,
        dns_checker=dns_checker,
        retry_attempts=retry_config.get('attempts', 3),
        retry_delay=retry_config.get('delay', 0.5),
        allow_smtputf8=validation_config.get('allow_smtputf8', False),
        allow_empty_local=validation_config.get('allow_empty_local', False),
        allow_quoted_local=validation_config.get('allow_quoted_local', False),
        allow_domain_literal=validation_config.get('allow_domain_literal', False),
        deliverable_address=validation_config.get('deliverable_address', True)
    )
    
    # 4. I/O handler
    io_handler = EmailIOHandler(
        input_file=paths_config.get('input_file', 'data/emails.txt'),
        valid_output_dir=paths_config.get('valid_output_dir', 'output/valid'),
        invalid_output=paths_config.get('invalid_output', 'output/invalid.txt'),
        well_known_domains_file=paths_config.get('well_known_domains', 'config/well_known_domains.txt')
    )
    
    # Print configuration
    print("\nValidator configured:")
    print(f"   - Unicode characters: {'Allowed' if validation_config.get('allow_smtputf8') else 'Not allowed'}")
    print(f"   - Empty local parts: {'Allowed' if validation_config.get('allow_empty_local') else 'Not allowed'}")
    print(f"   - Quoted strings: {'Allowed' if validation_config.get('allow_quoted_local') else 'Not allowed'}")
    print(f"   - IP addresses: {'Allowed' if validation_config.get('allow_domain_literal') else 'Not allowed'}")
    print(f"   - DNS deliverability: {'Enabled' if validation_config.get('deliverable_address') else 'Disabled'}")
    print(f"   - Retry attempts: {retry_config.get('attempts', 3)}")
    print(f"   - DNS caching: Enabled (max {dns_cache_config.get('max_size', 10000)} domains)")
    print(f"\nWell-known domains: {len(io_handler.well_known_domains)} loaded")
    print(f"Disposable domains: {disposable_checker.get_domain_count()} loaded\n")
    
    # Read emails with deduplication
    emails, duplicates_removed = io_handler.read_emails()
    if not emails:
        logger.error("No emails to process")
        print("Error: No emails found to validate!")
        return
    
    print(f"Loaded {len(emails)} unique emails from {paths_config.get('input_file')}")
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate emails")
    
    # Validate emails
    print(f"\nValidating {len(emails)} emails with {concurrent_jobs} concurrent jobs...")
    print("Starting validation process...\n")
    
    valid_emails = []
    invalid_emails = []
    start_time = time.time()
    completed = 0
    
    # Process emails concurrently in batches
    with ThreadPoolExecutor(max_workers=concurrent_jobs) as executor:
        for batch_start in range(0, len(emails), batch_size):
            batch_end = min(batch_start + batch_size, len(emails))
            batch = emails[batch_start:batch_end]
            
            # Submit current batch
            futures = {
                executor.submit(validation_service.validate, email): email
                for email in batch
            }
            
            # Process batch results
            for future in as_completed(futures):
                email, is_valid, reason, category = future.result()
                completed += 1
                
                if is_valid:
                    valid_emails.append((email, reason, category))
                else:
                    invalid_emails.append((email, reason, category))
                
                # Calculate and display progress
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
                
                # Print progress (same line with carriage return)
                print(
                    f"{completed}/{len(emails)} - {percentage:.1f}% | "
                    f"Valid: {len(valid_emails)} | Invalid: {len(invalid_emails)} | "
                    f"Speed: {speed:.1f}/sec | ETA: {eta_str}",
                    end='\r',
                    flush=True
                )
    
    print()  # New line after progress
    elapsed_time = time.time() - start_time
    
    logger.info(f"Validation completed: {len(valid_emails)} valid, {len(invalid_emails)} invalid")
    
    # Write results
    io_handler.write_results(valid_emails, invalid_emails)
    
    # Print final summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Total Emails:     {len(emails)}")
    print(f"Valid:            {len(valid_emails)}")
    print(f"Invalid:          {len(invalid_emails)}")
    print(f"Time Taken:       {elapsed_time:.2f} seconds")
    print(f"Speed:            {len(emails)/elapsed_time:.2f} emails/second")
    print("="*70)
    
    # Log DNS cache statistics
    cache_info = dns_checker.get_cache_info()
    logger.info(f"DNS cache stats: {cache_info}")
    
    logger.info("="*70)
    logger.info("Email validation process completed successfully")
    logger.info("="*70)


if __name__ == "__main__":
    main()
