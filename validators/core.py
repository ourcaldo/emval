"""
Core email validation logic module.
"""

from emval import EmailValidator
from typing import Tuple
import time
import logging

logger = logging.getLogger(__name__)


class EmailValidationService:
    """
    Main email validation service with retry logic and error categorization.
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
        deliverable_address: bool = True
    ):
        """
        Initialize email validation service.
        
        Args:
            disposable_checker: DisposableDomainChecker instance
            dns_checker: DNSChecker instance
            retry_attempts: Number of retry attempts for DNS failures
            retry_delay: Delay between retries in seconds
            allow_smtputf8: Allow Unicode characters
            allow_empty_local: Allow empty local parts
            allow_quoted_local: Allow quoted strings
            allow_domain_literal: Allow IP addresses as domains
            deliverable_address: Enable DNS deliverability checks
        """
        self.disposable_checker = disposable_checker
        self.dns_checker = dns_checker
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        # Initialize emval validator
        self.validator = EmailValidator(
            allow_smtputf8=allow_smtputf8,
            allow_empty_local=allow_empty_local,
            allow_quoted_local=allow_quoted_local,
            allow_domain_literal=allow_domain_literal,
            deliverable_address=deliverable_address,
            allowed_special_domains=[]
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
        
        # Check if disposable
        if self.disposable_checker.is_disposable(email):
            logger.debug(f"Disposable email rejected: {email}")
            return (email, False, "Disposable email domain", "disposable")
        
        # Extract domain for caching
        try:
            domain = email.split('@')[1].lower()
        except (IndexError, AttributeError):
            logger.debug(f"Invalid email format: {email}")
            return (email, False, "Invalid email format", "syntax")
        
        # Check domain cache
        self.dns_checker.check_domain(domain)
        
        # Validate with emval with retry logic for DNS failures
        for attempt in range(self.retry_attempts):
            try:
                result = self.validator.validate_email(email)
                logger.debug(f"Valid email: {email}")
                return (email, True, "Valid", "valid")
            
            except Exception as e:
                error_msg = str(e)
                
                # Categorize error
                if any(keyword in error_msg.lower() for keyword in ['dns', 'resolve', 'timeout', 'mx']):
                    error_category = "dns"
                    # Retry on DNS errors
                    if attempt < self.retry_attempts - 1:
                        logger.debug(f"DNS error for {email}, attempt {attempt + 1}/{self.retry_attempts}: {error_msg[:50]}")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logger.warning(f"DNS validation failed after {self.retry_attempts} attempts: {email}")
                else:
                    error_category = "syntax"
                
                # Shorten error message if too long
                if len(error_msg) > 100:
                    error_msg = error_msg[:97] + "..."
                
                logger.debug(f"Invalid email: {email} - {error_msg}")
                return (email, False, error_msg, error_category)
        
        # Should not reach here, but just in case
        return (email, False, "Validation failed", "unknown")
    
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
