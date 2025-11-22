"""
Proxy Manager for rotating through proxy list.
Loads proxies from file and provides rotation functionality.
"""

import logging
import random
from typing import Optional, Dict, List
from threading import Lock

logger = logging.getLogger(__name__)


class ProxyManager:
    """
    Manages a list of proxies loaded from a file.
    Supports rotation and authentication.
    """
    
    def __init__(self, proxy_file: str):
        """
        Initialize proxy manager.
        
        Args:
            proxy_file: Path to file containing proxy list
        """
        self.proxy_file = proxy_file
        self.proxies: List[Dict[str, str]] = []
        self.current_index = 0
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
    
    def _parse_proxy(self, proxy_str: str) -> Optional[Dict[str, str]]:
        """
        Parse proxy string into requests-compatible format.
        
        Supported formats:
        - host:port
        - host:port@user:password
        
        Args:
            proxy_str: Proxy string
            
        Returns:
            Proxy dictionary for requests library or None if invalid
        """
        try:
            # Check if authentication is present
            if '@' in proxy_str:
                # Format: host:port@user:password
                parts = proxy_str.split('@')
                if len(parts) != 2:
                    return None
                
                host_port = parts[0]
                user_password = parts[1]
                
                # Validate host:port
                if ':' not in host_port:
                    return None
                
                host_port_parts = host_port.split(':')
                if len(host_port_parts) != 2:
                    return None
                
                host = host_port_parts[0]
                port = host_port_parts[1]
                
                # Validate user:password
                if ':' not in user_password:
                    return None
                
                user_pass_parts = user_password.split(':', 1)
                username = user_pass_parts[0]
                password = user_pass_parts[1]
                
                # Build proxy URL with authentication
                proxy_url = f"http://{username}:{password}@{host}:{port}"
                
                return {
                    'http': proxy_url,
                    'https': proxy_url
                }
            else:
                # Format: host:port (no authentication)
                if ':' not in proxy_str:
                    return None
                
                parts = proxy_str.split(':')
                if len(parts) != 2:
                    return None
                
                host = parts[0]
                port = parts[1]
                
                # Validate port is numeric
                try:
                    int(port)
                except ValueError:
                    return None
                
                proxy_url = f"http://{host}:{port}"
                
                return {
                    'http': proxy_url,
                    'https': proxy_url
                }
        
        except Exception as e:
            logger.debug(f"Error parsing proxy '{proxy_str}': {e}")
            return None
    
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get next proxy in rotation (round-robin).
        
        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.proxies:
            return None
        
        with self.lock:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get random proxy from list.
        
        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.proxies:
            return None
        
        return random.choice(self.proxies)
    
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
