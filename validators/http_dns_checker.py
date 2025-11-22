"""
HTTP-based DNS checker using networkcalc.com API.
Replaces local DNS resolution with external API calls.
"""

import requests
from functools import lru_cache
from typing import Tuple, Optional, Dict, Any
import time
import logging

logger = logging.getLogger(__name__)


class HTTPDNSChecker:
    """
    DNS checker that uses networkcalc.com API for MX record verification.
    Includes caching, retry logic, and optional proxy support.
    """
    
    API_BASE_URL = "https://networkcalc.com/api/dns/lookup"
    
    def __init__(
        self,
        cache_size: int = 10000,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        proxy: Optional[Dict[str, str]] = None,
        rate_limit_delay: float = 0.1
    ):
        """
        Initialize HTTP DNS checker.
        
        Args:
            cache_size: Maximum number of domains to cache
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            proxy: Optional proxy configuration (e.g., {'http': 'http://proxy:8080', 'https': 'https://proxy:8080'})
            rate_limit_delay: Minimum delay between API requests to avoid rate limiting
        """
        self.cache_size = cache_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.proxy = proxy
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        
        # Create LRU cache for domain lookups
        self._check_domain_cached = lru_cache(maxsize=cache_size)(self._check_domain_impl)
        
        logger.info(f"HTTPDNSChecker initialized with cache size: {cache_size}")
        if proxy:
            logger.info(f"Using proxy: {proxy}")
    
    def check_domain(self, domain: str) -> Tuple[bool, str]:
        """
        Check if domain has valid MX records using HTTP API.
        
        Args:
            domain: Domain name to check
            
        Returns:
            Tuple of (has_mx_records, error_message)
        """
        try:
            return self._check_domain_cached(domain.lower())
        except Exception as e:
            logger.error(f"Unexpected error checking domain {domain}: {e}")
            return False, f"DNS check failed: {str(e)}"
    
    def _check_domain_impl(self, domain: str) -> Tuple[bool, str]:
        """
        Internal implementation of domain check (cached).
        
        Args:
            domain: Domain name to check
            
        Returns:
            Tuple of (has_mx_records, error_message)
        """
        # Rate limiting
        self._apply_rate_limit()
        
        # Try multiple times with exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Make API request
                url = f"{self.API_BASE_URL}/{domain}"
                
                logger.debug(f"Querying DNS API for domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                
                response = requests.get(
                    url,
                    timeout=self.timeout,
                    proxies=self.proxy,
                    headers={
                        'User-Agent': 'EmailValidator/1.0',
                        'Accept': 'application/json'
                    }
                )
                
                # Check response status
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_dns_response(domain, data)
                
                elif response.status_code == 404:
                    logger.debug(f"Domain not found: {domain}")
                    return False, "Domain not found (no DNS records)"
                
                elif response.status_code == 429:
                    # Rate limited
                    logger.warning(f"Rate limited by API for domain: {domain}")
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.debug(f"Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    return False, "API rate limit exceeded"
                
                elif response.status_code >= 500:
                    # Server error - retry
                    logger.warning(f"API server error (HTTP {response.status_code}) for domain: {domain}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return False, f"API server error (HTTP {response.status_code})"
                
                else:
                    # Other error
                    logger.warning(f"API error (HTTP {response.status_code}) for domain: {domain}")
                    return False, f"API error (HTTP {response.status_code})"
            
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout checking domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return False, "DNS lookup timeout"
            
            except requests.exceptions.ProxyError as e:
                logger.error(f"Proxy error for domain {domain}: {e}")
                return False, f"Proxy error: {str(e)}"
            
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error checking domain: {domain} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return False, "DNS lookup connection error"
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for domain {domain}: {e}")
                return False, f"DNS lookup failed: {str(e)}"
            
            except ValueError as e:
                # JSON parsing error
                logger.error(f"Invalid JSON response for domain {domain}: {e}")
                return False, "Invalid API response"
        
        # Should not reach here
        return False, "DNS lookup failed after retries"
    
    def _parse_dns_response(self, domain: str, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Parse DNS API response and check for MX records.
        
        Args:
            domain: Domain name
            data: JSON response from API
            
        Returns:
            Tuple of (has_mx_records, error_message)
        """
        try:
            status = data.get('status', '')
            
            if status != 'OK':
                logger.debug(f"API returned non-OK status for {domain}: {status}")
                return False, f"DNS lookup failed: {status}"
            
            records = data.get('records', {})
            mx_records = records.get('MX', [])
            
            if not mx_records or len(mx_records) == 0:
                logger.debug(f"No MX records found for domain: {domain}")
                return False, "No MX records found"
            
            # Check if MX records are valid
            for mx in mx_records:
                if 'exchange' in mx and mx['exchange']:
                    logger.debug(f"Valid MX record found for {domain}: {mx['exchange']}")
                    return True, ""
            
            logger.debug(f"MX records exist but are invalid for domain: {domain}")
            return False, "Invalid MX records"
        
        except Exception as e:
            logger.error(f"Error parsing DNS response for {domain}: {e}")
            return False, f"Failed to parse DNS response: {str(e)}"
    
    def _apply_rate_limit(self):
        """Apply rate limiting to avoid overwhelming the API."""
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
            Cache info object
        """
        return self._check_domain_cached.cache_info()
    
    def clear_cache(self):
        """Clear the DNS cache."""
        self._check_domain_cached.cache_clear()
        logger.info("DNS cache cleared")
