"""
Disposable email domain detection module.
"""

from typing import Set
import logging

logger = logging.getLogger(__name__)


class DisposableDomainChecker:
    """
    Checker for disposable/temporary email domains.
    """
    
    def __init__(self, disposable_domains_file: str):
        """
        Initialize disposable domain checker.
        
        Args:
            disposable_domains_file: Path to file containing disposable domains
        """
        self.disposable_domains_file = disposable_domains_file
        self.disposable_domains = self._load_disposable_domains()
    
    def _load_disposable_domains(self) -> Set[str]:
        """
        Load disposable email domains from file.
        
        Returns:
            Set of disposable domain strings
        """
        try:
            with open(self.disposable_domains_file, 'r', encoding='utf-8') as f:
                domains = set(line.strip().lower() for line in f if line.strip())
            logger.info(f"Loaded {len(domains)} disposable domains from {self.disposable_domains_file}")
            return domains
        except FileNotFoundError:
            logger.warning(f"Disposable domains file not found: {self.disposable_domains_file}")
            return set()
        except Exception as e:
            logger.error(f"Error loading disposable domains: {e}")
            return set()
    
    def is_disposable(self, email: str) -> bool:
        """
        Check if email domain is disposable.
        
        Args:
            email: Email address to check
            
        Returns:
            True if domain is disposable, False otherwise
        """
        if not self.disposable_domains:
            return False
        
        try:
            domain = email.split('@')[1].lower()
            is_disp = domain in self.disposable_domains
            if is_disp:
                logger.debug(f"Disposable domain detected: {domain}")
            return is_disp
        except (IndexError, AttributeError):
            logger.debug(f"Invalid email format for disposable check: {email}")
            return False
    
    def reload_domains(self):
        """Reload disposable domains from file."""
        self.disposable_domains = self._load_disposable_domains()
        logger.info("Disposable domains reloaded")
    
    def get_domain_count(self) -> int:
        """Get count of loaded disposable domains."""
        return len(self.disposable_domains)
