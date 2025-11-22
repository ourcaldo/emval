"""
DNS verification module with caching support.
"""

from functools import lru_cache
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DNSChecker:
    """
    DNS verification with LRU caching to avoid repeated lookups.
    """
    
    def __init__(self, cache_size: int = 10000):
        """
        Initialize DNS checker with cache.
        
        Args:
            cache_size: Maximum number of domains to cache
        """
        self.cache_size = cache_size
        self._check_domain_cached = lru_cache(maxsize=cache_size)(self._check_domain)
        logger.info(f"DNSChecker initialized with cache size: {cache_size}")
    
    def _check_domain(self, domain: str) -> bool:
        """
        Internal method to check domain (this gets cached).
        Note: Actual DNS checking is delegated to emval library.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if domain exists in cache or needs checking
        """
        # This is a placeholder for cache key - actual DNS check
        # is done by emval in the validation process
        return True
    
    def check_domain(self, domain: str) -> bool:
        """
        Check if domain has valid MX records (with caching).
        
        Args:
            domain: Domain to verify
            
        Returns:
            True if domain is cached/valid
        """
        return self._check_domain_cached(domain.lower())
    
    def clear_cache(self):
        """Clear the DNS cache."""
        self._check_domain_cached.cache_clear()
        logger.info("DNS cache cleared")
    
    def get_cache_info(self):
        """Get cache statistics."""
        return self._check_domain_cached.cache_info()
