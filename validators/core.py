"""
Core email validation logic module.
"""

from .syntax_validator import EmailSyntaxValidator
from typing import Tuple, List, Optional
import logging

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
    
    Plus-addressing is provider-aware:
    - Rejected for Gmail/Google domains (gmail.com, googlemail.com, google.com)
    - Allowed for all other domains
    """
    
    # Gmail/Google domains where plus-addressing is not allowed
    GMAIL_DOMAINS = {'gmail.com', 'googlemail.com', 'google.com'}
    
    def __init__(
        self,
        disposable_checker,
        dns_checker,
        smtp_validator=None,
        retry_attempts: int = 3,
        retry_delay: float = 0.5,
        allow_smtputf8: bool = False,
        allow_empty_local: bool = False,
        allow_quoted_local: bool = False,
        allow_domain_literal: bool = False,
        deliverable_address: bool = True,
        smtp_validation: bool = True,
        allowed_special_domains: Optional[List[str]] = None
    ):
        """
        Initialize email validation service.
        
        Args:
            disposable_checker: DisposableDomainChecker instance
            dns_checker: DNSChecker instance
            smtp_validator: SMTPValidator instance for RCPT TO validation (optional)
            retry_attempts: Number of retry attempts for DNS failures
            retry_delay: Delay between retries in seconds
            allow_smtputf8: Allow Unicode characters
            allow_empty_local: Allow empty local parts
            allow_quoted_local: Allow quoted strings
            allow_domain_literal: Allow IP addresses as domains
            deliverable_address: Enable DNS deliverability checks
            smtp_validation: Enable SMTP RCPT TO validation
            allowed_special_domains: List of special-use domains to allow
        
        Note: Plus-addressing is handled with provider-aware logic (rejected only for Gmail/Google).
        """
        self.disposable_checker = disposable_checker
        self.dns_checker = dns_checker
        self.smtp_validator = smtp_validator
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.deliverable_address = deliverable_address
        self.smtp_validation = smtp_validation
        
        # Initialize syntax validator
        self.syntax_validator = EmailSyntaxValidator(
            allow_smtputf8=allow_smtputf8,
            allow_empty_local=allow_empty_local,
            allow_quoted_local=allow_quoted_local,
            allow_domain_literal=allow_domain_literal,
            allowed_special_domains=allowed_special_domains or []
        )
        
        logger.info("EmailValidationService initialized")
        logger.info(f"Retry attempts: {retry_attempts}, Retry delay: {retry_delay}s")
        logger.info(f"SMTP validation: {'Enabled' if smtp_validation and smtp_validator else 'Disabled'}")
        logger.info(f"Plus-addressing: Rejected for {self.GMAIL_DOMAINS}, allowed for other domains")
    
    def validate(self, email: str) -> Tuple[str, bool, str, str]:
        """
        Validate email through sequential validation pipeline.
        
        Pipeline: Email → Syntax → Disposable → DNS → SMTP RCPT TO → Catch-all → Output
        
        Output categories:
        - valid: Passed all validation steps (safe)
        - risk: Passed all except catch-all (risky, domain accepts all emails)
        - invalid: Failed at any validation step
        - unknown: Passed basic validation but error during SMTP validation
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (email, is_valid, reason, category)
            category: 'valid', 'risk', 'invalid', 'unknown'
        """
        email = email.strip().lower()
        
        if not email:
            logger.debug("Empty email encountered")
            return (email, False, "Empty email", "invalid")
        
        # Step 1: Syntax validation
        is_valid_syntax, syntax_error = self.syntax_validator.validate(email)
        if not is_valid_syntax:
            logger.debug(f"Step 1 FAIL - Syntax: {email} - {syntax_error}")
            return (email, False, syntax_error, "invalid")
        
        # Step 1.5: Provider-aware plus-addressing check
        if '+' in email:
            domain = self.syntax_validator.extract_domain(email)
            if domain and domain in self.GMAIL_DOMAINS:
                logger.debug(f"Step 1 FAIL - Plus-addressing rejected: {email}")
                return (email, False, "Plus-addressing not allowed for Gmail/Google", "invalid")
        
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
