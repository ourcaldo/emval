"""
Core email validation logic module.
"""

from .syntax_validator import EmailSyntaxValidator
from typing import Tuple, List, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import threading

logger = logging.getLogger(__name__)


class EmailValidationService:
    """
    Main email validation service with sequential validation pipeline.
    
    Validation Flow:
    Email → Step 1 (Syntax) → Step 2 (Disposable) → Step 3 (DNS) → Step 4 (SMTP RCPT TO) → Step 5 (Catch-all) → Output
    
    Output Categories:
    - valid: Passed all validation steps (safe to send)
    - risk: Passed all except catch-all validation (risky, may not be deliverable)
    - invalid: Failed at any validation step
    - unknown: Passed basic validation but error during SMTP validation
    
    Strict Syntax Rules:
    - Local part: ONLY a-z A-Z 0-9 . _ (NO plus-addressing, NO hyphens, NO special chars)
    - Dots and underscores cannot be at start or end
    - TLD validated against IANA list (downloaded fresh on each run)
    """
    
    def __init__(
        self,
        disposable_checker,
        dns_checker,
        smtp_validator=None,
        retry_attempts: int = 3,
        retry_delay: float = 0.5,
        deliverable_address: bool = True,
        smtp_validation: bool = True,
        download_tld_list: bool = True,
        global_timeout: int = 30
    ):
        """
        Initialize email validation service.
        
        Args:
            disposable_checker: DisposableDomainChecker instance
            dns_checker: DNSChecker instance
            smtp_validator: SMTPValidator instance for RCPT TO validation (optional)
            retry_attempts: Number of retry attempts for DNS failures
            retry_delay: Delay between retries in seconds
            deliverable_address: Enable DNS deliverability checks
            smtp_validation: Enable SMTP RCPT TO validation
            download_tld_list: Download fresh IANA TLD list on initialization (default: True)
            global_timeout: Global timeout for all validation steps per email (seconds)
        """
        self.disposable_checker = disposable_checker
        self.dns_checker = dns_checker
        self.smtp_validator = smtp_validator
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.deliverable_address = deliverable_address
        self.smtp_validation = smtp_validation
        self.global_timeout = global_timeout
        
        # Initialize syntax validator with strict rules
        self.syntax_validator = EmailSyntaxValidator(download_tld_list=download_tld_list)
        
        logger.info("EmailValidationService initialized")
        logger.info(f"Global timeout: {global_timeout}s")
        logger.info(f"Retry attempts: {retry_attempts}, Retry delay: {retry_delay}s")
        logger.info(f"SMTP validation: {'Enabled' if smtp_validation and smtp_validator else 'Disabled'}")
        logger.info("Strict syntax: NO plus-addressing, NO hyphens in local part, TLD validated against IANA list")
    
    def validate(self, email: str) -> Tuple[str, bool, str, str]:
        """
        Validate email through sequential validation pipeline with global timeout.
        
        Pipeline: Email → Syntax → Disposable → DNS → SMTP RCPT TO → Catch-all → Output
        
        Output categories:
        - valid: Passed all validation steps (safe)
        - risk: Passed all except catch-all (risky, domain accepts all emails)
        - invalid: Failed at any validation step
        - unknown: Passed basic validation but error during SMTP validation or timeout exceeded
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (email, is_valid, reason, category)
            category: 'valid', 'risk', 'invalid', 'unknown'
        """
        email = email.strip().lower()
        
        # Create executor explicitly (not using context manager to avoid blocking on timeout)
        # Each validation gets its own executor to support concurrent validations
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"validator_{email[:10]}")
        future = executor.submit(self._validate_internal, email)
        
        try:
            # Wait for result with global timeout
            result = future.result(timeout=self.global_timeout)
            # Success - clean up properly by waiting for the thread to complete
            executor.shutdown(wait=True)
            return result
        except FuturesTimeoutError:
            # Cancel the future to stop the validation task
            future.cancel()
            logger.warning(f"Global timeout exceeded ({self.global_timeout}s) for email: {email}")
            
            # Shutdown without waiting - don't block on timeout
            # cancel_futures=True cancels pending futures (Python 3.9+)
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Python < 3.9 doesn't support cancel_futures parameter
                executor.shutdown(wait=False)
            
            return (email, True, f"Validation timeout exceeded ({self.global_timeout}s)", "unknown")
        except Exception as e:
            logger.error(f"Unexpected error during validation of {email}: {e}")
            # Clean up on error without blocking
            executor.shutdown(wait=False)
            return (email, False, f"Validation error: {str(e)}", "unknown")
    
    def _validate_internal(self, email: str) -> Tuple[str, bool, str, str]:
        """
        Internal validation method that performs the actual validation logic.
        This method is executed within the timeout wrapper.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (email, is_valid, reason, category)
        """
        
        if not email:
            logger.debug("Empty email encountered")
            return (email, False, "Empty email", "invalid")
        
        # Step 1: Syntax validation (strict rules: NO +, NO -, dots/underscores not at start/end, IANA TLD validation)
        is_valid_syntax, syntax_error = self.syntax_validator.validate(email)
        if not is_valid_syntax:
            logger.debug(f"Step 1 FAIL - Syntax: {email} - {syntax_error}")
            return (email, False, syntax_error, "invalid")
        
        logger.debug(f"Step 1 PASS - Syntax: {email}")
        
        # Step 2: Disposable email check
        if self.disposable_checker.is_disposable(email):
            logger.debug(f"Step 2 FAIL - Disposable: {email}")
            return (email, False, "Disposable email domain", "invalid")
        
        logger.debug(f"Step 2 PASS - Disposable: {email}")
        
        # Step 3: DNS MX record check
        domain = self.syntax_validator.extract_domain(email)
        if not domain:
            logger.debug(f"Step 3 FAIL - Cannot extract domain: {email}")
            return (email, False, "Invalid email format", "invalid")
        
        # Fetch MX servers if deliverable_address OR smtp_validation is enabled
        need_mx_servers = self.deliverable_address or (self.smtp_validation and self.smtp_validator)
        
        if need_mx_servers:
            has_mx, dns_error = self.dns_checker.check_domain(domain)
            if not has_mx:
                logger.debug(f"Step 3 {'FAIL' if self.deliverable_address else 'WARN'} - DNS: {email} - {dns_error}")
                # Only fail the email if deliverable_address check is enabled
                if self.deliverable_address:
                    return (email, False, dns_error, "invalid")
                else:
                    # SMTP validation enabled but no MX servers - will skip SMTP step
                    mx_servers = []
            else:
                mx_servers = self.dns_checker.get_mx_servers(domain)
                logger.debug(f"Step 3 PASS - DNS: {email} - MX servers found")
        else:
            mx_servers = []
        
        # Step 4 & 5: SMTP RCPT TO and Catch-all validation (if enabled)
        if self.smtp_validation and self.smtp_validator and mx_servers:
            mx_server = mx_servers[0]
            
            status, code, message, is_catchall = self.smtp_validator.validate_mailbox(
                email, mx_server, check_catchall=True
            )
            
            if status == 'catch-all':
                logger.debug(f"Step 5 FAIL - Catch-all: {email} - Domain accepts all emails")
                return (email, True, "Catch-all domain (risky)", "risk")
            
            if status == 'valid':
                logger.debug(f"Step 4 PASS - SMTP: {email} - Mailbox exists")
                logger.debug(f"Step 5 PASS - Catch-all: {email} - Not a catch-all")
                return (email, True, "Valid mailbox", "valid")
            
            if status == 'invalid':
                logger.debug(f"Step 4 FAIL - SMTP: {email} - {message}")
                return (email, False, message, "invalid")
            
            if status == 'unknown':
                logger.debug(f"Step 4 UNKNOWN - SMTP: {email} - {message}")
                return (email, True, message, "unknown")
        
        # No SMTP validation or no MX servers
        logger.debug(f"SMTP validation skipped for {email}")
        return (email, True, "Valid (DNS only)", "valid")
    
    def get_validator_config(self) -> dict:
        """
        Get current validator configuration.
        
        Returns:
            Dictionary with configuration details
        """
        return {
            'retry_attempts': self.retry_attempts,
            'retry_delay': self.retry_delay,
            'disposable_domains_count': self.disposable_checker.get_domain_count(),
            'dns_cache_info': self.dns_checker.get_cache_info()
        }
