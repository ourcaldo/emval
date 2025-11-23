"""
Proxy Manager for rotating through proxy list.
Loads proxies from file and provides rotation functionality.
Supports SOCKS5 proxies with rate limiting (1 request/proxy/second).
"""

import logging
import random
import time
from typing import Optional, Dict, List, Tuple, Any
from threading import Lock

logger = logging.getLogger(__name__)


class ProxyManager:
    """
    Manages a list of SOCKS5 proxies loaded from a file.
    Supports rotation, authentication, and rate limiting (1 request/proxy/second).
    """
    
    def __init__(self, proxy_file: str, rate_limit_seconds: float = 1.0):
        """
        Initialize proxy manager.
        
        Args:
            proxy_file: Path to file containing proxy list
            rate_limit_seconds: Minimum seconds between requests per proxy (default: 1.0)
        """
        self.proxy_file = proxy_file
        self.proxies: List[Dict[str, Any]] = []
        self.current_index = 0
        self.rate_limit_seconds = rate_limit_seconds
        self.lock = Lock()
        
        self._load_proxies()
    
    def _load_proxies(self):
        """Load proxies from file."""
        try:
            with open(self.proxy_file, 'r') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                proxy_dict = self._parse_proxy(line)
                if proxy_dict:
                    self.proxies.append(proxy_dict)
                else:
                    logger.warning(f"Invalid proxy format at line {line_num}: {line}")
            
            if self.proxies:
                logger.info(f"Loaded {len(self.proxies)} proxies from {self.proxy_file}")
            else:
                logger.warning(f"No valid proxies found in {self.proxy_file}")
        
        except FileNotFoundError:
            logger.warning(f"Proxy file not found: {self.proxy_file}")
        except Exception as e:
            logger.error(f"Error loading proxies from {self.proxy_file}: {e}")
    
    def _parse_proxy(self, proxy_str: str) -> Optional[Dict[str, Any]]:
        """
        Parse SOCKS5 proxy string.
        
        Supported formats:
        - host:port
        - host:port:user:password
        
        Args:
            proxy_str: Proxy string
            
        Returns:
            Proxy dictionary with host, port, username, password, and last_used timestamp
        """
        try:
            parts = proxy_str.split(':')
            
            if len(parts) == 2:
                host, port = parts
                username = None
                password = None
            elif len(parts) == 4:
                host, port, username, password = parts
            else:
                return None
            
            try:
                port = int(port)
            except ValueError:
                return None
            
            return {
                'host': host,
                'port': port,
                'username': username,
                'password': password,
                'last_used': 0.0
            }
        
        except Exception as e:
            logger.debug(f"Error parsing SOCKS5 proxy '{proxy_str}': {e}")
            return None
    
    def get_next_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get next proxy in rotation (round-robin) with rate limiting.
        Waits if the proxy was used too recently.
        
        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.proxies:
            return None
        
        while True:
            wait_time = 0
            
            with self.lock:
                # Try to find an available proxy (not rate-limited)
                for _ in range(len(self.proxies)):
                    proxy = self.proxies[self.current_index]
                    self.current_index = (self.current_index + 1) % len(self.proxies)
                    
                    current_time = time.time()
                    time_since_last_use = current_time - proxy['last_used']
                    
                    if time_since_last_use >= self.rate_limit_seconds:
                        proxy['last_used'] = current_time
                        return proxy
                
                # All proxies are rate-limited, find the one available soonest
                oldest_proxy = min(self.proxies, key=lambda p: p['last_used'])
                current_time = time.time()
                wait_time = self.rate_limit_seconds - (current_time - oldest_proxy['last_used'])
            
            # Release lock before sleeping to allow other threads to proceed
            if wait_time > 0:
                logger.debug(f"All proxies rate limited, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
            
            # Loop back to try again (will re-acquire lock)
    
    def get_random_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get random proxy from list with rate limiting.
        Waits if the proxy was used too recently.
        
        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.proxies:
            return None
        
        while True:
            wait_time = 0
            
            with self.lock:
                available_proxies = []
                current_time = time.time()
                
                for proxy in self.proxies:
                    time_since_last_use = current_time - proxy['last_used']
                    if time_since_last_use >= self.rate_limit_seconds:
                        available_proxies.append(proxy)
                
                if available_proxies:
                    proxy = random.choice(available_proxies)
                    proxy['last_used'] = current_time
                    return proxy
                
                # All proxies are rate-limited, find the one available soonest
                oldest_proxy = min(self.proxies, key=lambda p: p['last_used'])
                wait_time = self.rate_limit_seconds - (current_time - oldest_proxy['last_used'])
            
            # Release lock before sleeping to allow other threads to proceed
            if wait_time > 0:
                logger.debug(f"All proxies rate limited, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
            
            # Loop back to try again (will re-acquire lock)
    
    def get_proxy_count(self) -> int:
        """
        Get number of loaded proxies.
        
        Returns:
            Number of proxies
        """
        return len(self.proxies)
    
    def is_enabled(self) -> bool:
        """
        Check if proxy manager has valid proxies.
        
        Returns:
            True if proxies are available, False otherwise
        """
        return len(self.proxies) > 0
