"""
Bulk Email Validator - Main Entry Point

This is a modular, testable email validation system that:
- Validates email syntax and DNS deliverability
- Blocks disposable email domains
- Separates well-known domains from others
- Generates comprehensive reports

All configuration is externalized in config/settings.yaml
"""

from validators import EmailValidationService, LocalDNSChecker, DisposableDomainChecker, EmailIOHandler, ProxyManager, SMTPValidator
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import time
import sys
import logging


class ProgressDisplay:
    """
    Dynamic progress display - uses \r for terminals, regular output for pipes
    Based on sys.stdout.isatty() detection from dynamic-progress-guide.md
    """
    def __init__(self):
        self.show_config = False
        self.config_info = {}
        self.config_printed = False
        self.is_terminal = sys.stdout.isatty()
    
    def print_config(self):
        """Print configuration once before progress starts"""
        if self.show_config and self.config_info and not self.config_printed:
            print("=" * 70)
            print("VALIDATOR CONFIGURATION")
            print()
            print(f"DNS deliverability:  {'Enabled' if self.config_info.get('dns_deliverable') else 'Disabled'}")
            print(f"SMTP validation:     {'Enabled' if self.config_info.get('smtp_enabled') else 'Disabled'}")
            print(f"Retry attempts:      {self.config_info.get('retry_attempts', 3)}")
            print(f"DNS cache size:      {self.config_info.get('dns_cache_size', 10000)} domains")
            print(f"SOCKS5 proxy:        {'Enabled (' + str(self.config_info.get('proxy_count', 0)) + ' proxies)' if self.config_info.get('proxy_enabled') else 'Disabled'}")
            print(f"Well-known domains:  {self.config_info.get('well_known_domains', 0)}")
            print(f"Disposable domains:  {self.config_info.get('disposable_domains', 0)}")
            print("=" * 70)
            print()
            self.config_printed = True
    
    def print_progress(self, current, total, valid, risk, invalid, unknown, speed, eta_str=""):
        """Progress updates disabled - final summary provides all information"""
        # Config only shown once if needed
        if not self.config_printed and self.show_config and self.config_info:
            self.print_config()
    
    def finish(self):
        """Move to next line after progress completes"""
        if self.is_terminal:
            print()  # Move to next line
        print("=" * 70)

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
    Only logs to file, not to console for cleaner output.
    
    Args:
        config: Configuration dictionary
    """
    log_config = config.get('logging', {})
    log_file = config.get('paths', {}).get('log_file', 'validator.log')
    
    # Only log to file, not to console
    handlers = [logging.FileHandler(log_file)]
    
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
    dns_config = config.get('dns', {})
    validation_config = config.get('validation', {})
    smtp_config = config.get('smtp', {})
    paths_config = config.get('paths', {})
    network_config = config.get('network', {})
    
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
    
    # 2. Proxy manager (SOCKS5 with rate limiting)
    proxy_manager = None
    smtp_use_proxy = smtp_config.get('use_proxy', True) and smtp_config.get('enabled', True)
    if smtp_use_proxy:
        proxy_list_file = paths_config.get('proxy_list', 'data/proxy.txt')
        proxy_rate_limit = smtp_config.get('proxy_rate_limit', 1.0)
        proxy_manager = ProxyManager(proxy_list_file, rate_limit_seconds=proxy_rate_limit)
        if not proxy_manager.is_enabled():
            logger.warning("SMTP proxy enabled but no valid SOCKS5 proxies loaded. Continuing without proxy.")
            print("Warning: SMTP proxy enabled but no valid SOCKS5 proxies found in proxy list file.")
            proxy_manager = None
    
    # 3. Local DNS checker with caching (5-10x faster than HTTP API!)
    dns_servers = dns_config.get('servers', [])
    dns_checker = LocalDNSChecker(
        cache_size=dns_cache_config.get('max_size', 10000),
        timeout=dns_config.get('timeout', 5),
        max_retries=dns_config.get('max_retries', 3),
        retry_delay=dns_config.get('retry_delay', 0.5),
        dns_servers=dns_servers if dns_servers else None
    )
    
    # 4. SMTP validator (for RCPT TO and catch-all detection)
    smtp_validator = None
    smtp_enabled = smtp_config.get('enabled', True) and validation_config.get('smtp_validation', True)
    if smtp_enabled:
        smtp_validator = SMTPValidator(
            proxy_manager=proxy_manager,
            timeout=smtp_config.get('timeout', 10),
            from_email=smtp_config.get('from_email', 'verify@example.com'),
            max_retries=smtp_config.get('max_retries', 2)
        )
        logger.info("SMTP validator initialized for RCPT TO and catch-all detection")
    
    # 5. Email validation service (with strict syntax validation)
    validation_service = EmailValidationService(
        disposable_checker=disposable_checker,
        dns_checker=dns_checker,
        smtp_validator=smtp_validator,
        retry_attempts=retry_config.get('attempts', 3),
        retry_delay=retry_config.get('delay', 0.5),
        deliverable_address=validation_config.get('deliverable_address', True),
        smtp_validation=smtp_enabled,
        download_tld_list=True  # Download fresh IANA TLD list on each run
    )
    
    # 6. I/O handler
    io_handler = EmailIOHandler(
        input_file=paths_config.get('input_file', 'data/emails.txt'),
        valid_output_dir=paths_config.get('valid_output_dir', 'output/valid'),
        risk_output_dir=paths_config.get('risk_output_dir', 'output/risk'),
        invalid_output=paths_config.get('invalid_output', 'output/invalid.txt'),
        unknown_output=paths_config.get('unknown_output', 'output/unknown.txt'),
        well_known_domains_file=paths_config.get('well_known_domains', 'config/well_known_domains.txt')
    )
    
    # Store configuration for display in progress
    config_info = {
        'dns_deliverable': validation_config.get('deliverable_address'),
        'smtp_enabled': smtp_enabled,
        'retry_attempts': retry_config.get('attempts', 3),
        'dns_cache_size': dns_cache_config.get('max_size', 10000),
        'proxy_enabled': proxy_manager and proxy_manager.is_enabled(),
        'proxy_count': proxy_manager.get_proxy_count() if proxy_manager and proxy_manager.is_enabled() else 0,
        'well_known_domains': len(io_handler.well_known_domains),
        'disposable_domains': disposable_checker.get_domain_count()
    }
    
    # Read emails with deduplication
    emails, duplicates_removed = io_handler.read_emails()
    if not emails:
        logger.error("No emails to process")
        print("Error: No emails found to validate!")
        return
    
    # Print minimal header
    print(f"\nLoaded {len(emails)} unique emails from {paths_config.get('input_file')}")
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate emails")
    
    all_results = []
    start_time = time.time()
    completed = 0
    
    # Counters for each category
    valid_count = 0
    risk_count = 0
    invalid_count = 0
    unknown_count = 0
    
    # Initialize progress display with configuration
    display = ProgressDisplay()
    display.show_config = True  # Show config on first display
    display.config_info = config_info
    
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
                
                all_results.append((email, reason, category))
                
                # Update category counters
                if category == 'valid':
                    valid_count += 1
                elif category == 'risk':
                    risk_count += 1
                elif category == 'invalid':
                    invalid_count += 1
                elif category == 'unknown':
                    unknown_count += 1
                
                # Calculate and display progress
                current_time = time.time()
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
                
                # Display dynamic progress dashboard
                display.print_progress(
                    current=completed,
                    total=len(emails),
                    valid=valid_count,
                    risk=risk_count,
                    invalid=invalid_count,
                    unknown=unknown_count,
                    speed=speed,
                    eta_str=eta_str
                )
    
    # Finish progress display and move to next line
    display.finish()
    elapsed_time = time.time() - start_time
    
    logger.info(f"Validation completed: Valid={valid_count}, Risk={risk_count}, Invalid={invalid_count}, Unknown={unknown_count}")
    
    # Write results
    io_handler.write_results(all_results)
    
    # Get output file info
    output_info = io_handler.get_output_info()
    
    # Print final summary (merged with output summary)
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print()
    print(f"Total Emails:     {len(emails)}")
    print(f"Valid (safe):     {valid_count}")
    print(f"Risk (catch-all): {risk_count}")
    print(f"Invalid:          {invalid_count}")
    print(f"Unknown:          {unknown_count}")
    print(f"Time Taken:       {elapsed_time:.2f} seconds")
    print(f"Speed:            {len(emails)/elapsed_time:.2f} emails/second")
    print()
    print(f"Output Files:")
    if valid_count > 0:
        print(f"  Valid emails: {output_info['valid_dir']}/")
    if risk_count > 0:
        print(f"  Risk emails:  {output_info['risk_dir']}/")
    if invalid_count > 0:
        print(f"  Invalid:      {output_info['invalid_file']}")
    if unknown_count > 0:
        print(f"  Unknown:      {output_info['unknown_file']}")
    print("="*70)
    
    # Log DNS cache statistics
    cache_info = dns_checker.get_cache_info()
    logger.info(f"DNS cache stats: {cache_info}")
    
    logger.info("="*70)
    logger.info("Email validation process completed successfully")
    logger.info("="*70)


if __name__ == "__main__":
    main()
