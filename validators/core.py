"""
Core email validation logic module.
"""

from .syntax_validator import EmailSyntaxValidator
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class EmailValidationService:
    """
    Main email validation service with retry logic and error categorization.
    Uses self-hosted email syntax validation and HTTP-based DNS checking.
    """
    
    def __init__(
        self,
        disposable_checker,
        dns_checker,
        retry_attempts: int = 3,
        retry_delay: float = 0.5,
        allow_smtputf8: bool = False,
        allow_empty_local: bool = False,
        allow_quoted_local: bool = False,
        allow_domain_literal: bool = False,
        deliverable_address: bool = True,
        allowed_special_domains: List[str] = None
    ):
        """
        Initialize email validation service.
        
        Args:
            disposable_checker: DisposableDomainChecker instance
            dns_checker: HTTPDNSChecker instance
            retry_attempts: Number of retry attempts for DNS failures
            retry_delay: Delay between retries in seconds
            allow_smtputf8: Allow Unicode characters
            allow_empty_local: Allow empty local parts
            allow_quoted_local: Allow quoted strings
            allow_domain_literal: Allow IP addresses as domains
            deliverable_address: Enable DNS deliverability checks
            allowed_special_domains: List of special-use domains to allow
        """
        self.disposable_checker = disposable_checker
        self.dns_checker = dns_checker
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.deliverable_address = deliverable_address
        
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
    
    def validate(self, email: str) -> Tuple[str, bool, str, str]:
        """
        Validate a single email address with retry logic.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (email, is_valid, reason, error_category)
            error_category: 'syntax', 'disposable', 'dns', 'valid'
        """
        email = email.strip()
        
        # Check for empty email
        if not email:
            logger.debug("Empty email encountered")
            return (email, False, "Empty email", "syntax")
        
        # Step 1: Validate syntax
        is_valid_syntax, syntax_error = self.syntax_validator.validate(email)
        if not is_valid_syntax:
            logger.debug(f"Invalid email syntax: {email} - {syntax_error}")
            return (email, False, syntax_error, "syntax")
        
        # Step 2: Check if disposable
        if self.disposable_checker.is_disposable(email):
            logger.debug(f"Disposable email rejected: {email}")
            return (email, False, "Disposable email domain", "disposable")
        
        # Step 3: Check DNS deliverability (if enabled)
        if self.deliverable_address:
            # Extract domain
            domain = self.syntax_validator.extract_domain(email)
            if not domain:
                logger.debug(f"Could not extract domain from: {email}")
                return (email, False, "Invalid email format", "syntax")
            
            # Check DNS MX records
            has_mx, dns_error = self.dns_checker.check_domain(domain)
            if not has_mx:
                logger.debug(f"DNS validation failed for {email}: {dns_error}")
                return (email, False, dns_error, "dns")
        
        # All checks passed
        logger.debug(f"Valid email: {email}")
        return (email, True, "Valid", "valid")
    
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
