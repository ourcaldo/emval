"""
TLD (Top-Level Domain) validator using IANA official list.
Downloads fresh TLD list on each validation run.
"""

import logging
import os
import time
from typing import Set, Optional
import requests

logger = logging.getLogger(__name__)


class TLDValidator:
    """
    Validates TLDs against the official IANA TLD list.
    Downloads fresh list from https://data.iana.org/TLD/tlds-alpha-by-domain.txt
    """
    
    IANA_TLD_URL = "https://data.iana.org/TLD/tlds-alpha-by-domain.txt"
    TLD_CACHE_FILE = "data/tlds-alpha-by-domain.txt"
    
    def __init__(self, force_download: bool = True):
        """
        Initialize TLD validator.
        
        Args:
            force_download: If True, download fresh TLD list on each init (default: True)
        """
        self.tlds: Set[str] = set()
        self.last_updated: Optional[str] = None
        
        if force_download:
            self.download_tld_list()
        else:
            self.load_tld_list()
    
    def download_tld_list(self) -> bool:
        """
        Download fresh TLD list from IANA.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading fresh TLD list from {self.IANA_TLD_URL}")
            
            response = requests.get(self.IANA_TLD_URL, timeout=10)
            response.raise_for_status()
            
            # Save to cache file
            os.makedirs(os.path.dirname(self.TLD_CACHE_FILE), exist_ok=True)
            with open(self.TLD_CACHE_FILE, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Parse the list
            self._parse_tld_list(response.text)
            
            logger.info(f"TLD list downloaded successfully. Total TLDs: {len(self.tlds)}")
            if self.last_updated:
                logger.info(f"TLD list version: {self.last_updated}")
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to download TLD list from {self.IANA_TLD_URL}: {e}")
            logger.info("Falling back to cached TLD list if available")
            return self.load_tld_list()
        
        except Exception as e:
            logger.error(f"Error downloading TLD list: {e}")
            return False
    
    def load_tld_list(self) -> bool:
        """
        Load TLD list from cached file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(self.TLD_CACHE_FILE):
                logger.warning(f"TLD cache file not found: {self.TLD_CACHE_FILE}")
                return False
            
            logger.info(f"Loading TLD list from cache: {self.TLD_CACHE_FILE}")
            
            with open(self.TLD_CACHE_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self._parse_tld_list(content)
            
            logger.info(f"TLD list loaded from cache. Total TLDs: {len(self.tlds)}")
            if self.last_updated:
                logger.info(f"TLD list version: {self.last_updated}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading TLD list from cache: {e}")
            return False
    
    def _parse_tld_list(self, content: str) -> None:
        """
        Parse TLD list content from IANA format.
        
        Format:
        # Version 2025112300, Last Updated Sun Nov 23 07:07:02 2025 UTC
        AAA
        AARP
        ABB
        ...
        
        Args:
            content: TLD list content
        """
        self.tlds.clear()
        self.last_updated = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Extract version info from comment
            if line.startswith('#'):
                if 'Version' in line:
                    self.last_updated = line
                continue
            
            # Add TLD in lowercase (IANA list is uppercase)
            tld = line.lower()
            self.tlds.add(tld)
    
    def is_valid_tld(self, tld: str) -> bool:
        """
        Check if TLD is valid according to IANA list.
        
        Args:
            tld: TLD to validate (e.g., 'com', 'org', 'co.uk')
            
        Returns:
            True if valid, False otherwise
        """
        if not self.tlds:
            logger.warning("TLD list is empty. Validation may be inaccurate.")
            return False
        
        # Normalize to lowercase
        tld_lower = tld.lower()
        
        # Check if TLD is in the list
        return tld_lower in self.tlds
    
    def get_tld_count(self) -> int:
        """
        Get the number of TLDs in the list.
        
        Returns:
            Number of TLDs
        """
        return len(self.tlds)
    
    def get_version_info(self) -> Optional[str]:
        """
        Get TLD list version information.
        
        Returns:
            Version string or None
        """
        return self.last_updated
