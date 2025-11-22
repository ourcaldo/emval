"""
HTTP-based DNS checker using networkcalc.com API.
Replaces local DNS resolution with external API calls.
"""

import requests
from typing import Tuple, Optional, Dict, Any, TYPE_CHECKING
from collections import OrderedDict
import time
import logging
import threading

if TYPE_CHECKING:
    from .proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


class HTTPDNSChecker:
    """
    DNS checker that uses networkcalc.com API for MX record verification.
    Includes custom caching (only caches definitive results), retry logic, and optional proxy support.
    """
    
    API_BASE_URL = "https://networkcalc.com/api/dns/lookup"
    
    def __init__(
        self,
        cache_size: int = 10000,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        proxy_manager: Optional['ProxyManager'] = None,
        rate_limit_delay: float = 0.1
    ):
        """
        Initialize HTTP DNS checker.
        
        Args:
            cache_size: Maximum number of domains to cache
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            proxy_manager: Optional ProxyManager instance for proxy rotation
            rate_limit_delay: Minimum delay between API requests to avoid rate limiting
        """
        self.cache_size = cache_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.proxy_manager = proxy_manager
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self._rate_limit_lock = threading.Lock()  # Thread-safe rate limiting
        
        # Custom cache for domain lookups (only caches definitive results)
        self._cache = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info(f"HTTPDNSChecker initialized with cache size: {cache_size}")
        if proxy_manager and proxy_manager.is_enabled():
            logger.info(f"Proxy rotation enabled with {proxy_manager.get_proxy_count()} proxies")
    
    def check_domain(self, domain: str) -> Tuple[bool, str]:
        """
        Check if domain has valid MX records (with A record fallback) using HTTP API.
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
        # Rate limiting
        self._apply_rate_limit()
        
        # Try multiple times with exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Get proxy from manager (rotates automatically)
                proxy = None
                if self.proxy_manager and self.proxy_manager.is_enabled():
                    proxy = self.proxy_manager.get_next_proxy()
                
                # Make API request
                url = f"{self.API_BASE_URL}/{domain}"
                
                logger.debug(f"Querying DNS API for domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                
                response = requests.get(
                    url,
                    timeout=self.timeout,
                    proxies=proxy,
                    headers={
                        'User-Agent': 'EmailValidator/1.0',
                        'Accept': 'application/json'
                    }
                )
                
                # Check response status
                if response.status_code == 200:
                    data = response.json()
                    result = self._parse_dns_response(domain, data)
                    if result is not None:
                        # Successful parse - return with cacheable=True
                        success, error = result
                        return success, error, True
                    # Parse error - retry
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    # After all retries, return temporary failure (not cacheable)
                    return False, "DNS lookup failed (parse error)", False
                
                elif response.status_code == 404:
                    # Definitive failure - domain doesn't exist, safe to cache
                    logger.debug(f"Domain not found: {domain}")
                    return False, "Domain not found (no DNS records)", True
                
                elif response.status_code == 429:
                    # Rate limited - temporary failure, don't cache
                    logger.warning(f"Rate limited by API for domain: {domain}")
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    # After all retries, return temporary failure (not cacheable)
                    return False, "API rate limit exceeded (temporary)", False
                
                elif response.status_code >= 500:
                    # Server error - temporary failure, don't cache
                    logger.warning(f"API server error (HTTP {response.status_code}) for domain: {domain}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    # After all retries, return temporary failure (not cacheable)
                    return False, f"API server error (HTTP {response.status_code}, temporary)", False
                
                elif response.status_code == 400:
                    # Bad request - likely invalid domain, safe to cache
                    logger.warning(f"API error (HTTP {response.status_code}) for domain: {domain}")
                    return False, "Invalid domain format", True
                
                else:
                    # Other error - unclear if temporary, don't cache
                    logger.warning(f"API error (HTTP {response.status_code}) for domain: {domain}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    # After all retries, return temporary failure (not cacheable)
                    return False, f"API error (HTTP {response.status_code}, temporary)", False
            
            except requests.exceptions.Timeout:
                # Timeout - temporary failure, don't cache
                logger.warning(f"Timeout checking domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                # After all retries, return temporary failure (not cacheable)
                return False, "DNS check timeout (temporary)", False
            
            except requests.exceptions.ProxyError as e:
                # Proxy error - temporary failure, don't cache
                logger.error(f"Proxy error for domain {domain}: {e}")
                return False, f"Proxy error (temporary): {str(e)}", False
            
            except requests.exceptions.ConnectionError as e:
                # Connection error - temporary failure, don't cache
                logger.warning(f"Connection error checking domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                # After all retries, return temporary failure (not cacheable)
                return False, f"Connection error (temporary): {str(e)}", False
            
            except requests.exceptions.RequestException as e:
                # Request error - temporary failure, don't cache
                logger.error(f"Request error for domain {domain}: {e}")
                return False, f"Request error (temporary): {str(e)}", False
            
            except ValueError as e:
                # JSON parsing error - temporary failure, don't cache
                logger.error(f"Invalid JSON response for domain {domain}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                # After all retries, return temporary failure (not cacheable)
                return False, f"Invalid API response (temporary): {str(e)}", False
            
            except Exception as e:
                # Unexpected error - temporary failure, don't cache
                logger.error(f"Unexpected error checking domain {domain}: {e}")
                return False, f"Unexpected error (temporary): {str(e)}", False
        
        # Should not reach here, but if we do, return temporary failure
        return False, "DNS lookup failed after retries (temporary)", False
    
    def _parse_dns_response(self, domain: str, data: Dict[str, Any]) -> Optional[Tuple[bool, str]]:
        """
        Parse DNS API response and check for MX records with A record fallback.
        NEVER raises exceptions - returns None on parse error.
        
        Per RFC 5321: Only fall back to A records if NO MX records exist.
        If MX records exist but are invalid, that's a domain configuration error.
        
        Note: NetworkCalc API returns A records as strings (IP addresses), not objects.
        AAAA records are NOT supported by the NetworkCalc API.
        
        Args:
            domain: Domain name
            data: JSON response from API
            
        Returns:
            Tuple of (has_mx_records, error_message) on success, None on parse error
        """
        try:
            status = data.get('status', '')
            
            if status != 'OK':
                logger.debug(f"API returned non-OK status for {domain}: {status}")
                # Parse error - return None to indicate retry needed
                return None
            
            records = data.get('records', {})
            mx_records = records.get('MX', [])
            
            # Check for MX records first
            if mx_records and len(mx_records) > 0:
                # MX records exist - check if any are valid
                for mx in mx_records:
                    if isinstance(mx, dict) and 'exchange' in mx and mx['exchange']:
                        logger.debug(f"Valid MX record found for {domain}: {mx['exchange']}")
                        return True, ""
                # MX records exist but none are valid - don't fall back to A records
                # This is a definitive failure (domain misconfiguration)
                logger.debug(f"MX records exist but are invalid for domain: {domain}")
                return False, "MX records exist but are invalid"
            
            # Only fall back to A records if NO MX records exist
            # A records are returned as strings (IP addresses), not objects
            a_records = records.get('A', [])
            if a_records and len(a_records) > 0:
                for a in a_records:
                    # A records are strings (IP addresses)
                    if isinstance(a, str) and a:
                        logger.debug(f"No MX records, but valid A record found for {domain}: {a}")
                        return True, ""
                    # Some APIs might return objects with 'address' field, handle both formats
                    elif isinstance(a, dict) and 'address' in a and a['address']:
                        logger.debug(f"No MX records, but valid A record found for {domain}: {a['address']}")
                        return True, ""
            
            # Note: AAAA records (IPv6) are NOT supported by NetworkCalc API
            # Removed AAAA checking since the API doesn't provide it
            
            logger.debug(f"No MX or A records found for domain: {domain}")
            return False, "No MX or A records found"
        
        except Exception as e:
            logger.error(f"Error parsing DNS response for {domain}: {e}")
            # Parse error - return None to indicate retry needed
            return None
    
    def _apply_rate_limit(self):
        """Apply rate limiting to avoid overwhelming the API. Thread-safe."""
        with self._rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    def get_cache_info(self):
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
