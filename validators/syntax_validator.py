"""
Custom email syntax validator following RFC 5322 standards.
Replaces the emval module with self-hosted validation logic.
"""

import re
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


class EmailSyntaxValidator:
    """
    RFC 5322 compliant email syntax validator with configurable options.
    
    Supports:
    - allow_smtputf8: Internationalized email addresses (Unicode)
    - allow_empty_local: Empty local parts (@domain.com)
    - allow_quoted_local: Quoted local parts ("user name"@domain.com)
    - allow_domain_literal: Domain literals ([192.168.0.1])
    - allowed_special_domains: Special-use domains to allow
    """
    
    # RFC 5322 character sets
    ATEXT = r'[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]'
    DOT_ATOM = r'[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*'
    
    # Quoted string pattern
    QTEXT = r'[^\x00-\x1F\x7F"\\]'
    QCONTENT = rf'(?:{QTEXT}|\\[\x00-\x7F])'
    QUOTED_STRING = rf'"(?:{QCONTENT})*"'
    
    # Domain patterns
    DOMAIN_LABEL = r'[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?'
    DOMAIN = rf'{DOMAIN_LABEL}(?:\.{DOMAIN_LABEL})*'
    
    # IP address pattern (domain literal)
    IPV4 = r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}'
    DOMAIN_LITERAL = rf'\[(?:{IPV4}|[^\]]+)\]'
    
    # Unicode pattern for SMTPUTF8
    UNICODE_ATEXT = r'[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~\u0080-\uFFFF-]'
    UNICODE_DOT_ATOM = r'[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~\u0080-\uFFFF-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~\u0080-\uFFFF-]+)*'
    
    # Reserved/special domains (RFC 2606, RFC 6761)
    RESERVED_DOMAINS = {
        'test', 'example', 'invalid', 'localhost',
        'example.com', 'example.net', 'example.org',
        'test.com', 'invalid.com'
    }
    
    def __init__(
        self,
        allow_smtputf8: bool = False,
        allow_empty_local: bool = False,
        allow_quoted_local: bool = False,
        allow_domain_literal: bool = False,
        allowed_special_domains: Optional[List[str]] = None
    ):
        """
        Initialize email syntax validator.
        
        Args:
            allow_smtputf8: Allow Unicode characters in email addresses
            allow_empty_local: Allow empty local part (e.g., @domain.com)
            allow_quoted_local: Allow quoted local parts (e.g., "user name"@domain.com)
            allow_domain_literal: Allow domain literals (e.g., [192.168.0.1])
            allowed_special_domains: List of special-use domains to allow
        
        Note: Plus-addressing validation is now handled at the service layer with provider-aware logic.
        """
        self.allow_smtputf8 = allow_smtputf8
        self.allow_empty_local = allow_empty_local
        self.allow_quoted_local = allow_quoted_local
        self.allow_domain_literal = allow_domain_literal
        self.allowed_special_domains = set(allowed_special_domains or [])
        
        logger.info("EmailSyntaxValidator initialized")
        logger.debug(f"Options: smtputf8={allow_smtputf8}, empty_local={allow_empty_local}, "
                    f"quoted_local={allow_quoted_local}, domain_literal={allow_domain_literal}")
    
    def validate(self, email: str) -> Tuple[bool, str]:
        """
        Validate email address syntax.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is empty string
        """
        if not email or not isinstance(email, str):
            return False, "Email must be a non-empty string"
        
        email = email.strip()
        
        # Check overall length (RFC 5321)
        if len(email) > 254:
            return False, "Email exceeds 254 characters"
        
        # Must contain exactly one @ (unless empty local is allowed)
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
        Validate the local part of an email address.
        
        Args:
            local: Local part (before @)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for empty local part
        if not local:
            if self.allow_empty_local:
                return True, ""
            return False, "Local part is empty"
        
        # Check length (RFC 5321)
        if len(local) > 64:
            return False, "Local part exceeds 64 characters"
        
        # Check if it's a quoted string
        if local.startswith('"') and local.endswith('"'):
            if self.allow_quoted_local:
                return self._validate_quoted_local(local)
            return False, "Quoted local parts not allowed"
        
        # Validate as dot-atom
        return self._validate_dot_atom_local(local)
    
    def _validate_quoted_local(self, local: str) -> Tuple[bool, str]:
        """
        Validate quoted local part.
        
        Args:
            local: Quoted local part
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if properly quoted
        if len(local) < 2:
            return False, "Invalid quoted string"
        
        # Remove quotes and validate content
        content = local[1:-1]
        
        # Quoted strings can contain almost anything, but need to escape special chars
        # For simplicity, we'll allow most characters
        pattern = re.compile(self.QCONTENT + r'*')
        if not pattern.fullmatch(content):
            return False, "Invalid characters in quoted local part"
        
        return True, ""
    
    def _validate_dot_atom_local(self, local: str) -> Tuple[bool, str]:
        """
        Validate local part as dot-atom format.
        
        Note: Plus-addressing validation is now handled at the service layer
        with provider-aware logic (rejected only for Gmail/Google domains).
        
        Args:
            local: Local part
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Cannot start or end with dot
        if local.startswith('.') or local.endswith('.'):
            return False, "Local part cannot start or end with dot"
        
        # Cannot have consecutive dots
        if '..' in local:
            return False, "Local part cannot contain consecutive dots"
        
        # Check character set
        if self.allow_smtputf8:
            pattern = re.compile(f'^{self.UNICODE_DOT_ATOM}$')
        else:
            pattern = re.compile(f'^{self.DOT_ATOM}$')
        
        if not pattern.match(local):
            if self.allow_smtputf8:
                return False, "Invalid characters in local part"
            return False, "Invalid characters in local part (Unicode not allowed)"
        
        return True, ""
    
    def _validate_domain_part(self, domain: str) -> Tuple[bool, str]:
        """
        Validate the domain part of an email address.
        
        Args:
            domain: Domain part (after @)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not domain:
            return False, "Domain is empty"
        
        # Check length (RFC 5321)
        if len(domain) > 253:
            return False, "Domain exceeds 253 characters"
        
        # Check if it's a domain literal
        if domain.startswith('[') and domain.endswith(']'):
            if self.allow_domain_literal:
                return self._validate_domain_literal(domain)
            return False, "Domain literals not allowed"
        
        # Validate as regular domain
        return self._validate_regular_domain(domain)
    
    def _validate_domain_literal(self, domain: str) -> Tuple[bool, str]:
        """
        Validate domain literal (IP address in brackets).
        
        Args:
            domain: Domain literal [IP]
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pattern = re.compile(f'^{self.DOMAIN_LITERAL}$')
        if not pattern.match(domain):
            return False, "Invalid domain literal format"
        
        # Extract and validate IP
        ip = domain[1:-1]
        
        # Try IPv4 validation
        ipv4_pattern = re.compile(f'^{self.IPV4}$')
        if ipv4_pattern.match(ip):
            return True, ""
        
        # For IPv6 or other formats, just accept if syntax is correct
        return True, ""
    
    def _validate_regular_domain(self, domain: str) -> Tuple[bool, str]:
        """
        Validate regular domain name.
        
        Args:
            domain: Domain name
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Convert to lowercase for checking
        domain_lower = domain.lower()
        
        # Must contain at least one dot for TLD
        if '.' not in domain:
            # Check if it's a special allowed domain
            if domain_lower in self.allowed_special_domains:
                return True, ""
            return False, "Domain must contain at least one dot (TLD required)"
        
        # Check for reserved domains
        if domain_lower in self.RESERVED_DOMAINS:
            if domain_lower not in self.allowed_special_domains:
                return False, f"Reserved domain '{domain}' not allowed"
        
        # Cannot start or end with dot
        if domain.startswith('.') or domain.endswith('.'):
            return False, "Domain cannot start or end with dot"
        
        # Cannot start or end with hyphen
        if domain.startswith('-') or domain.endswith('-'):
            return False, "Domain cannot start or end with hyphen"
        
        # Validate each label
        labels = domain.split('.')
        for label in labels:
            if not label:
                return False, "Domain contains empty label (consecutive dots)"
            
            if len(label) > 63:
                return False, f"Domain label '{label}' exceeds 63 characters"
            
            # Label cannot start or end with hyphen
            if label.startswith('-') or label.endswith('-'):
                return False, f"Domain label '{label}' cannot start or end with hyphen"
            
            # Check characters (allow Unicode if SMTPUTF8 is enabled)
            if self.allow_smtputf8:
                # Allow Unicode characters
                if not re.match(r'^[a-zA-Z0-9\u0080-\uFFFF-]+$', label):
                    return False, f"Invalid characters in domain label '{label}'"
            else:
                # ASCII only
                if not re.match(r'^[a-zA-Z0-9-]+$', label):
                    return False, f"Invalid characters in domain label '{label}' (Unicode not allowed)"
        
        # TLD must be at least 2 characters (except for allowed special domains)
        tld = labels[-1]
        if len(tld) < 2 and domain_lower not in self.allowed_special_domains:
            return False, f"TLD '{tld}' must be at least 2 characters"
        
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
