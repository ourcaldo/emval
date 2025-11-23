"""
Strict email syntax validator with custom rules.
NO plus-addressing, NO hyphens in local part, strict character restrictions.
"""

import re
from typing import Tuple, Optional
import logging
from validators.tld_validator import TLDValidator

logger = logging.getLogger(__name__)


class EmailSyntaxValidator:
    """
    Strict email syntax validator with custom restrictions.
    
    Rules:
    - Local part: Only a-z A-Z 0-9 . _ (NO +, NO -, NO other special chars)
    - Dots and underscores cannot be at start or end of local part
    - No consecutive dots
    - Domain: Standard format with IANA TLD validation
    - TLD: Minimum 2 characters, letters only, validated against IANA list
    """
    
    # Strict local part pattern: only letters, numbers, dots, underscores
    # Must start with alphanumeric, must end with alphanumeric
    # Middle can have any combination of a-z A-Z 0-9 . _
    LOCAL_PART_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9._]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$'
    
    # Domain label pattern: letters, numbers, hyphens (not at start/end)
    DOMAIN_LABEL_PATTERN = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$'
    
    # TLD pattern: only letters, minimum 2 characters
    TLD_PATTERN = r'^[a-zA-Z]{2,}$'
    
    def __init__(self, download_tld_list: bool = True):
        """
        Initialize email syntax validator.
        
        Args:
            download_tld_list: Download fresh IANA TLD list on initialization (default: True)
        """
        # Initialize TLD validator (downloads fresh list by default)
        self.tld_validator = TLDValidator(force_download=download_tld_list)
        
        logger.info("EmailSyntaxValidator initialized with strict rules")
        logger.info(f"TLD list loaded: {self.tld_validator.get_tld_count()} TLDs")
        if self.tld_validator.get_version_info():
            logger.info(f"TLD version: {self.tld_validator.get_version_info()}")
    
    def validate(self, email: str) -> Tuple[bool, str]:
        """
        Validate email address syntax with strict rules.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is empty string
        """
        if not email or not isinstance(email, str):
            return False, "Email must be a non-empty string"
        
        # Strip whitespace and convert to lowercase for validation
        email = email.strip()
        
        # Check overall length (RFC 5321: max 254 characters)
        if len(email) > 254:
            return False, "Email exceeds 254 characters"
        
        # Must contain exactly one @ symbol
        at_count = email.count('@')
        if at_count == 0:
            return False, "Email must contain @ symbol"
        elif at_count > 1:
            return False, "Email must contain exactly one @ symbol"
        
        # Split into local and domain parts
        local, domain = email.rsplit('@', 1)
        
        # Validate local part
        is_valid, error = self._validate_local_part(local)
        if not is_valid:
            return False, f"Invalid local part: {error}"
        
        # Validate domain part
        is_valid, error = self._validate_domain_part(domain)
        if not is_valid:
            return False, f"Invalid domain: {error}"
        
        return True, ""
    
    def _validate_local_part(self, local: str) -> Tuple[bool, str]:
        """
        Validate the local part of an email address (before @).
        
        Strict rules:
        - Allowed characters: a-z A-Z 0-9 . _
        - Cannot start with dot or underscore
        - Cannot end with dot or underscore
        - No consecutive dots
        - Length: 1-64 characters
        
        Args:
            local: Local part (before @)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for empty local part
        if not local:
            return False, "Local part is empty"
        
        # Check length (RFC 5321: max 64 characters)
        if len(local) > 64:
            return False, "Local part exceeds 64 characters"
        
        # Check if starts with dot
        if local.startswith('.'):
            return False, "Local part cannot start with dot"
        
        # Check if starts with underscore
        if local.startswith('_'):
            return False, "Local part cannot start with underscore"
        
        # Check if ends with dot
        if local.endswith('.'):
            return False, "Local part cannot end with dot"
        
        # Check if ends with underscore
        if local.endswith('_'):
            return False, "Local part cannot end with underscore"
        
        # Check for consecutive dots
        if '..' in local:
            return False, "Local part cannot contain consecutive dots"
        
        # Check for plus sign (absolutely not allowed)
        if '+' in local:
            return False, "Plus sign (+) not allowed in local part"
        
        # Check for hyphen (not allowed in local part)
        if '-' in local:
            return False, "Hyphen (-) not allowed in local part"
        
        # Validate character set using regex
        # Pattern: must start with alphanumeric, can contain dots/underscores in middle, must end with alphanumeric
        pattern = re.compile(self.LOCAL_PART_PATTERN)
        if not pattern.match(local):
            return False, "Local part contains invalid characters (only a-z A-Z 0-9 . _ allowed)"
        
        return True, ""
    
    def _validate_domain_part(self, domain: str) -> Tuple[bool, str]:
        """
        Validate the domain part of an email address (after @).
        
        Rules:
        - Must contain at least one dot (require TLD)
        - Each label: 1-63 characters
        - Allowed characters: a-z A-Z 0-9 - (hyphen only in middle)
        - Cannot start/end with dot or hyphen
        - TLD: minimum 2 characters, letters only, validated against IANA list
        - Maximum length: 255 characters
        
        Args:
            domain: Domain part (after @)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not domain:
            return False, "Domain is empty"
        
        # Check length (RFC 5321: max 255 characters)
        if len(domain) > 255:
            return False, "Domain exceeds 255 characters"
        
        # Must contain at least one dot (require TLD)
        if '.' not in domain:
            return False, "Domain must contain at least one dot (TLD required)"
        
        # Cannot start or end with dot
        if domain.startswith('.'):
            return False, "Domain cannot start with dot"
        
        if domain.endswith('.'):
            return False, "Domain cannot end with dot"
        
        # Cannot start or end with hyphen
        if domain.startswith('-'):
            return False, "Domain cannot start with hyphen"
        
        if domain.endswith('-'):
            return False, "Domain cannot end with hyphen"
        
        # Check for consecutive dots
        if '..' in domain:
            return False, "Domain cannot contain consecutive dots"
        
        # Split into labels and validate each
        labels = domain.split('.')
        
        if len(labels) < 2:
            return False, "Domain must have at least 2 labels (domain.tld)"
        
        for i, label in enumerate(labels):
            # Check for empty label
            if not label:
                return False, "Domain contains empty label (consecutive dots)"
            
            # Check label length (max 63 characters per label)
            if len(label) > 63:
                return False, f"Domain label '{label}' exceeds 63 characters"
            
            # Validate label format
            is_valid, error = self._validate_domain_label(label, is_tld=(i == len(labels) - 1))
            if not is_valid:
                return False, error
        
        # Validate TLD specifically
        tld = labels[-1]
        is_valid, error = self._validate_tld(tld)
        if not is_valid:
            return False, error
        
        return True, ""
    
    def _validate_domain_label(self, label: str, is_tld: bool = False) -> Tuple[bool, str]:
        """
        Validate a single domain label.
        
        Args:
            label: Domain label to validate
            is_tld: Whether this label is the TLD (last part)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Label must not be empty
        if not label:
            return False, "Label is empty"
        
        # Label cannot start with hyphen
        if label.startswith('-'):
            return False, f"Label '{label}' cannot start with hyphen"
        
        # Label cannot end with hyphen
        if label.endswith('-'):
            return False, f"Label '{label}' cannot end with hyphen"
        
        # For TLD, only letters allowed (no numbers, no hyphens)
        if is_tld:
            if not label.isalpha():
                return False, f"TLD '{label}' can only contain letters"
        else:
            # For non-TLD labels, validate using pattern
            pattern = re.compile(self.DOMAIN_LABEL_PATTERN)
            if not pattern.match(label):
                return False, f"Label '{label}' contains invalid characters"
        
        return True, ""
    
    def _validate_tld(self, tld: str) -> Tuple[bool, str]:
        """
        Validate TLD (Top-Level Domain).
        
        Rules:
        - Minimum 2 characters
        - Only letters (no numbers, no special characters)
        - Must be in IANA TLD list
        
        Args:
            tld: TLD to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check minimum length
        if len(tld) < 2:
            return False, f"TLD '{tld}' must be at least 2 characters"
        
        # Check if only letters
        pattern = re.compile(self.TLD_PATTERN)
        if not pattern.match(tld):
            return False, f"TLD '{tld}' can only contain letters (no numbers or special characters)"
        
        # Validate against IANA TLD list
        if not self.tld_validator.is_valid_tld(tld):
            return False, f"TLD '{tld}' is not in the IANA TLD list"
        
        return True, ""
    
    def extract_domain(self, email: str) -> Optional[str]:
        """
        Extract domain from email address.
        
        Args:
            email: Email address
            
        Returns:
            Domain part or None if invalid
        """
        if '@' not in email:
            return None
        
        try:
            domain = email.rsplit('@', 1)[1].lower()
            return domain
        except (IndexError, AttributeError):
            return None
