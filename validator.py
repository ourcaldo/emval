"""
Bulk Email Validator - Main Entry Point (Enhanced Version)

This is a modular, testable email validation system that:
- Validates email syntax and DNS deliverability
- Blocks disposable email domains
- Separates well-known domains from others
- Generates comprehensive reports

All configuration is externalized in config/settings.yaml

ENHANCEMENTS:
- Improved dynamic progress display with cleaner output
- Better terminal/log detection
- ETA display during validation
- Right-aligned numbers for better readability
- Proper cleanup before showing summary
"""

from validators import EmailValidationService, LocalDNSChecker, DisposableDomainChecker, EmailIOHandler, ProxyManager, SMTPValidator
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml
import time
import sys
import logging
import os


class ProgressDisplay:
    """
    Enhanced dynamic progress display - uses ANSI escape codes for terminals

    Features:
    - Multi-line dashboard with progress bar
    - Automatic terminal vs log detection
    - Clean clearing before summary
    - Right-aligned numbers
    - ETA display
    - Config display on first call
    """
    def __init__(self):
        self.show_config = False
        self.config_info = {}
        self.config_printed = False
        self.is_terminal = sys.stdout.isatty()
        self.lines_printed = 0
        self.last_update_time = 0
        self.update_interval = 0.1  # Update display every 0.1 seconds minimum

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

    def clear_previous(self):
        """Clear previous progress lines using ANSI escape codes"""
        if self.lines_printed > 0 and self.is_terminal:
            # Move cursor up N lines
            sys.stdout.write(f'\033[{self.lines_printed}A')
            # Clear from cursor to end of screen
            sys.stdout.write('\033[J')

    def should_update(self):
        """
        Throttle updates to avoid flickering
        Returns True if enough time has passed since last update
        """
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self.last_update_time = current_time
            return True
        return False

    def print_progress(self, current, total, valid, risk, invalid, unknown, speed, time_taken, eta_str=""):
        """
        Print real-time progress in clean summary format

        Args:
            current: Number of emails processed
            total: Total number of emails
            valid: Count of valid emails
            risk: Count of risky emails (catch-all)
            invalid: Count of invalid emails
            unknown: Count of unknown status emails
            speed: Current processing speed (emails/sec)
            time_taken: Time elapsed in seconds
            eta_str: Estimated time remaining as string (e.g., "5s", "2m 30s")
        """
        # Config on first call
        if not self.config_printed:
            self.print_config()

        progress = (current / total) * 100

        # For non-terminal (logs), only print at 100% to avoid spam
        if not self.is_terminal:
            if current != total:
                return

        # Throttle updates for terminal to avoid flickering (except for final update)
        if self.is_terminal and current != total:
            if not self.should_update():
                return

        # Clear previous progress display (only works in terminal)
        self.clear_previous()

        # Create progress bar
        bar_length = 40
        filled = int(bar_length * current // total)
        # Using ASCII characters for better compatibility
        # Use Unicode if you want: bar = '█' * filled + '░' * (bar_length - filled)
        bar = '=' * filled + '-' * (bar_length - filled)

        # Build clean summary format with right-aligned numbers
        lines = [
            "=" * 70,
            f"PROGRESS [{bar}] {progress:.1f}%",
            "",
            f"Processed:        {current:>6} / {total}",
            f"Valid (safe):     {valid:>6}",
            f"Risk (catch-all): {risk:>6}",
            f"Invalid:          {invalid:>6}",
            f"Unknown:          {unknown:>6}",
            "",
            f"Time Taken:       {time_taken:.2f} seconds",
            f"Speed:            {speed:.2f} emails/second",
        ]

        # Add ETA only if not complete and ETA is provided
        if eta_str and current < total:
            lines.append(f"ETA:              {eta_str}")

        lines.append("=" * 70)

        # Print all lines
        output = '\n'.join(lines)
        print(output, flush=True)

        # Remember how many lines we printed for next clear
        self.lines_printed = len(lines)

    def finish(self):
        """
        Finish progress display and clear it completely before summary
        This ensures clean transition to the final summary
        """
        if self.is_terminal:
            # Clear the progress display completely
            self.clear_previous()
        self.lines_printed = 0


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
    Creates log directory if it doesn't exist.

    Args:
        config: Configuration dictionary
    """
    log_config = config.get('logging', {})
    log_file = config.get('paths', {}).get('log_file', 'validator.log')

    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Only log to file, not to console
    handlers = [logging.FileHandler(log_file)]

    logging.basicConfig(
        level=getattr(logging, log_config.get('level', 'INFO')),
        format=log_config.get('format', '%(asctime)s - %(levelname)s - %(message)s'),
        handlers=handlers
    )


def format_time(seconds):
    """
    Format seconds into human-readable time string

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "2m 30s" or "45s"
    """
    if seconds < 60:
        return f"{int(seconds)}s"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {secs}s"

    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h {mins}m"


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
    print("=" * 70)
    print("BULK EMAIL VALIDATOR")
    print("=" * 70)
    print(f"Concurrent Jobs: {concurrent_jobs}\n")

    logger.info("=" * 70)
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
    print()

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
    display.show_config = True
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

                # Calculate metrics
                current_time = time.time()
                elapsed = current_time - start_time
                speed = completed / elapsed if elapsed > 0 else 0

                # Calculate ETA
                eta_str = ""
                if speed > 0 and completed < len(emails):
                    remaining = len(emails) - completed
                    eta_seconds = remaining / speed
                    eta_str = format_time(eta_seconds)

                # Display dynamic progress dashboard
                display.print_progress(
                    current=completed,
                    total=len(emails),
                    valid=valid_count,
                    risk=risk_count,
                    invalid=invalid_count,
                    unknown=unknown_count,
                    speed=speed,
                    time_taken=elapsed,
                    eta_str=eta_str
                )

    # Finish progress display and clear it completely
    display.finish()

    elapsed_time = time.time() - start_time

    logger.info(f"Validation completed: Valid={valid_count}, Risk={risk_count}, Invalid={invalid_count}, Unknown={unknown_count}")

    # Write results
    io_handler.write_results(all_results)

    # Get output file info
    output_info = io_handler.get_output_info()

    # Print final summary (clean, after progress is cleared)
    print("=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print()
    print(f"Total Emails:     {len(emails):>6}")
    print(f"Valid (safe):     {valid_count:>6}")
    print(f"Risk (catch-all): {risk_count:>6}")
    print(f"Invalid:          {invalid_count:>6}")
    print(f"Unknown:          {unknown_count:>6}")
    print()
    print(f"Time Taken:       {format_time(elapsed_time)}")
    print(f"Speed:            {len(emails)/elapsed_time:.2f} emails/second")
    print()
    print("Output Files:")
    if valid_count > 0:
        print(f"  ✓ Valid emails: {output_info['valid_dir']}/")
    if risk_count > 0:
        print(f"  ⚠ Risk emails:  {output_info['risk_dir']}/")
    if invalid_count > 0:
        print(f"  ✗ Invalid:      {output_info['invalid_file']}")
    if unknown_count > 0:
        print(f"  ? Unknown:      {output_info['unknown_file']}")
    print("=" * 70)

    # Log DNS cache statistics
    cache_info = dns_checker.get_cache_info()
    logger.info(f"DNS cache stats: {cache_info}")

    logger.info("=" * 70)
    logger.info("Email validation process completed successfully")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()