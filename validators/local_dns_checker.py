"""
Local DNS checker using dnspython library.
Replaces HTTP API calls with direct DNS resolution for 5-10x performance improvement.
"""

import dns.resolver
import dns.exception
from typing import Tuple, Optional, List
from collections import OrderedDict
import time
import logging
import threading

logger = logging.getLogger(__name__)


class LocalDNSChecker:
    """
    DNS checker that uses dnspython for direct DNS resolution.
    Includes custom caching (only caches definitive results), retry logic, and multi-provider support.
    
    Key features preserved from HTTPDNSChecker:
    - Selective caching (only definitive results)
    - Thread-safe operations
    - LRU cache eviction
    - Retry logic with exponential backoff
    - Never crashes (returns tuples)
    - RFC 5321 compliant (MX first, A fallback)
    - Cache statistics
    """
    
    def __init__(
        self,
        cache_size: int = 10000,
        timeout: int = 5,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        dns_servers: Optional[List[str]] = None
    ):
        """
        Initialize Local DNS checker.
        
        Args:
            cache_size: Maximum number of domains to cache
            timeout: DNS query timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            dns_servers: List of DNS server IPs (default: Google, Cloudflare, OpenDNS)
        """
        self.cache_size = cache_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Configure DNS resolver with multiple providers for redundancy
        self.resolver = dns.resolver.Resolver()
        
        # Use provided DNS servers or fallback to reliable public DNS providers
        if dns_servers and len(dns_servers) > 0:
            self.resolver.nameservers = dns_servers
            logger.info(f"Using custom DNS servers: {dns_servers}")
        else:
            # Default to multiple reliable public DNS providers
            self.resolver.nameservers = [
                '8.8.8.8',      # Google Primary
                '8.8.4.4',      # Google Secondary
                '1.1.1.1',      # Cloudflare Primary
                '1.0.0.1',      # Cloudflare Secondary
            ]
            logger.info(f"Using default DNS servers: {self.resolver.nameservers}")
        
        # Set resolver timeouts
        self.resolver.timeout = timeout
        self.resolver.lifetime = timeout * 2  # Total timeout (allows retries)
        
        # Custom cache for domain lookups (only caches definitive results)
        self._cache = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info(f"LocalDNSChecker initialized with cache size: {cache_size}, "
                   f"timeout: {timeout}s, nameservers: {len(self.resolver.nameservers)}")
    
    def check_domain(self, domain: str) -> Tuple[bool, str]:
        """
        Check if domain has valid MX records (with A record fallback) using direct DNS resolution.
        Only definitive results are cached; temporary failures are not cached.
        
        Args:
            domain: Domain name to check
            
        Returns:
            Tuple of (has_mx_records, error_message)
        """
        domain = domain.lower()
        
        # Check cache first
        with self._cache_lock:
            if domain in self._cache:
                self._cache_hits += 1
                # Move to end (LRU)
                self._cache.move_to_end(domain)
                logger.debug(f"Cache hit for domain: {domain}")
                return self._cache[domain]
            self._cache_misses += 1
        
        # Not in cache, check domain
        success, error, cacheable = self._check_domain_impl(domain)
        
        # Only cache definitive results
        if cacheable:
            with self._cache_lock:
                self._cache[domain] = (success, error)
                # Maintain cache size limit (LRU eviction)
                if len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
                logger.debug(f"Cached result for domain: {domain} (success={success})")
        else:
            logger.debug(f"Not caching temporary failure for domain: {domain}")
        
        return success, error
    
    def _check_domain_impl(self, domain: str) -> Tuple[bool, str, bool]:
        """
        Internal implementation of domain check.
        NEVER raises exceptions - always returns a tuple.
        
        Args:
            domain: Domain name to check
            
        Returns:
            Tuple of (has_mx_records, error_message, cacheable)
            - has_mx_records: True if domain has valid MX/A/AAAA records
            - error_message: Empty string if valid, error description otherwise
            - cacheable: True if result should be cached (definitive), False for temporary failures
        """
        # Try multiple times with exponential backoff
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Checking DNS for domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                
                # First, check for MX records (preferred for email)
                try:
                    mx_records = self.resolver.resolve(domain, 'MX')
                    if mx_records and len(mx_records) > 0:
                        # MX records exist - check if any are valid
                        for mx in mx_records:
                            if mx.exchange and str(mx.exchange) != '.':
                                logger.debug(f"Valid MX record found for {domain}: {mx.exchange} (priority: {mx.preference})")
                                return True, "", True
                        # MX records exist but none are valid (all null MX)
                        # This is definitive - domain explicitly rejects email
                        logger.debug(f"Domain {domain} has only null MX records (rejects email)")
                        return False, "Domain rejects email (null MX records)", True
                
                except dns.resolver.NoAnswer:
                    # No MX records - will try A/AAAA records below (RFC 5321 compliant)
                    logger.debug(f"No MX records for {domain}, will try A/AAAA records")
                    pass
                
                except dns.resolver.NXDOMAIN:
                    # Domain doesn't exist - definitive failure, safe to cache
                    logger.debug(f"Domain not found: {domain}")
                    return False, "Domain not found (no DNS records)", True
                
                # Per RFC 5321: If no MX records, fall back to A/AAAA records
                # Try A records (IPv4)
                try:
                    a_records = self.resolver.resolve(domain, 'A')
                    if a_records and len(a_records) > 0:
                        logger.debug(f"No MX records, but valid A record found for {domain}: {a_records[0].address}")
                        return True, "", True
                except dns.resolver.NoAnswer:
                    # No A records, try AAAA
                    pass
                except dns.resolver.NXDOMAIN:
                    # Domain doesn't exist
                    return False, "Domain not found (no DNS records)", True
                
                # Try AAAA records (IPv6)
                try:
                    aaaa_records = self.resolver.resolve(domain, 'AAAA')
                    if aaaa_records and len(aaaa_records) > 0:
                        logger.debug(f"No MX/A records, but valid AAAA record found for {domain}: {aaaa_records[0].address}")
                        return True, "", True
                except dns.resolver.NoAnswer:
                    # No AAAA records either
                    pass
                except dns.resolver.NXDOMAIN:
                    # Domain doesn't exist
                    return False, "Domain not found (no DNS records)", True
                
                # No MX, A, or AAAA records found - definitive failure
                logger.debug(f"No MX, A, or AAAA records found for domain: {domain}")
                return False, "No MX, A, or AAAA records found", True
            
            except dns.resolver.NXDOMAIN:
                # Domain doesn't exist - definitive failure, safe to cache
                logger.debug(f"Domain not found: {domain}")
                return False, "Domain not found (no DNS records)", True
            
            except dns.exception.Timeout:
                # Timeout - temporary failure, don't cache
                logger.warning(f"DNS timeout for domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                # After all retries, return temporary failure (not cacheable)
                return False, "DNS check timeout (temporary)", False
            
            except dns.resolver.LifetimeTimeout:
                # Lifetime timeout (total timeout exceeded) - temporary failure
                logger.warning(f"DNS lifetime timeout for domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                return False, "DNS lifetime timeout (temporary)", False
            
            except dns.resolver.NoNameservers:
                # All nameservers failed - temporary failure, don't cache
                logger.warning(f"All nameservers failed for domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                return False, "All DNS servers failed (temporary)", False
            
            except dns.resolver.NoResolverConfiguration:
                # No resolver configuration - configuration error, treat as temporary
                logger.error(f"No resolver configuration for domain: {domain}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                return False, "DNS resolver not configured (temporary)", False
            
            except dns.resolver.NoAnswer:
                # Should not reach here (handled above), but if we do, it's definitive
                logger.debug(f"No DNS records for domain: {domain}")
                return False, "No DNS records found", True
            
            except dns.exception.DNSException as e:
                # Generic DNS error - could be temporary or permanent, treat as temporary to be safe
                logger.warning(f"DNS exception for domain {domain}: {type(e).__name__}: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                # After all retries, treat as temporary failure
                return False, f"DNS error (temporary): {str(e)}", False
            
            except Exception as e:
                # Unexpected error - temporary failure, don't cache
                logger.error(f"Unexpected error checking domain {domain}: {e}")
                return False, f"Unexpected error (temporary): {str(e)}", False
        
        # Should not reach here, but if we do, return temporary failure
        return False, "DNS lookup failed after retries (temporary)", False
    
    def get_cache_info(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics (hits, misses, size, maxsize)
        """
        with self._cache_lock:
            return {
                'hits': self._cache_hits,
                'misses': self._cache_misses,
                'currsize': len(self._cache),
                'maxsize': self.cache_size
            }
    
    def clear_cache(self):
        """Clear the DNS cache."""
        with self._cache_lock:
            self._cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
        logger.info("DNS cache cleared")
