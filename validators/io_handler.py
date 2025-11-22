"""
File I/O operations module for email validation.
"""

from typing import List, Tuple, Dict, Set
import os
import re
import logging

logger = logging.getLogger(__name__)


class EmailIOHandler:
    """
    Handles all file I/O operations for email validation.
    """
    
    def __init__(
        self,
        input_file: str,
        valid_output_dir: str,
        invalid_output: str,
        well_known_domains_file: str
    ):
        """
        Initialize I/O handler.
        
        Args:
            input_file: Path to input emails file
            valid_output_dir: Directory for valid emails output
            invalid_output: Path to invalid emails output file
            well_known_domains_file: Path to well-known domains config file
        """
        self.input_file = input_file
        self.valid_output_dir = valid_output_dir
        self.invalid_output = invalid_output
        self.well_known_domains_file = well_known_domains_file
        self.well_known_domains = self._load_well_known_domains()
    
    def _load_well_known_domains(self) -> Set[str]:
        """
        Load well-known email domains from config file.
        
        Returns:
            Set of well-known domain strings
        """
        try:
            with open(self.well_known_domains_file, 'r', encoding='utf-8') as f:
                domains = set(line.strip().lower() for line in f if line.strip())
            logger.info(f"Loaded {len(domains)} well-known domains from {self.well_known_domains_file}")
            return domains
        except FileNotFoundError:
            logger.warning(f"Well-known domains file not found: {self.well_known_domains_file}")
            return set()
        except Exception as e:
            logger.error(f"Error loading well-known domains: {e}")
            return set()
    
    def read_emails(self) -> Tuple[List[str], int]:
        """
        Read and deduplicate emails from input file.
        
        Returns:
            Tuple of (unique_emails_list, duplicates_removed_count)
        """
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                all_emails = [line.strip() for line in f if line.strip()]
            
            original_count = len(all_emails)
            
            # Deduplicate while preserving order
            seen = set()
            unique_emails = []
            for email in all_emails:
                email_lower = email.lower()  # Case-insensitive deduplication
                if email_lower not in seen:
                    seen.add(email_lower)
                    unique_emails.append(email)
            
            duplicates_removed = original_count - len(unique_emails)
            
            if duplicates_removed > 0:
                logger.info(f"Removed {duplicates_removed} duplicate emails from {self.input_file}")
            
            logger.info(f"Loaded {len(unique_emails)} unique emails from {self.input_file}")
            return unique_emails, duplicates_removed
        except FileNotFoundError:
            logger.error(f"Input file not found: {self.input_file}")
            return [], 0
        except Exception as e:
            logger.error(f"Error reading input file: {e}")
            return [], 0
    
    @staticmethod
    def sanitize_domain_filename(domain: str) -> str:
        """
        Sanitize domain name for use as filename.
        
        Args:
            domain: Domain name to sanitize
            
        Returns:
            Safe filename string
        """
        # Replace any character that's not a-z, A-Z, 0-9, dot, or hyphen with underscore
        safe_domain = re.sub(r'[^a-zA-Z0-9.-]', '_', domain)
        # Remove any leading/trailing dots or hyphens
        safe_domain = safe_domain.strip('.-')
        # Ensure it's not empty
        if not safe_domain:
            safe_domain = "unknown"
        return safe_domain
    
    def write_results(
        self,
        valid_emails: List[Tuple[str, str, str]],
        invalid_emails: List[Tuple[str, str, str]]
    ):
        """
        Write validation results to output files.
        
        Args:
            valid_emails: List of (email, reason, category) tuples for valid emails
            invalid_emails: List of (email, reason, category) tuples for invalid emails
        """
        # Create output directories
        self._create_output_directories()
        
        # Group and write valid emails
        well_known_count, other_count = self._write_valid_emails(valid_emails)
        
        # Write invalid emails
        self._write_invalid_emails(invalid_emails)
        
        # Print summary
        self._print_summary(len(valid_emails), len(invalid_emails), well_known_count, other_count)
    
    def _create_output_directories(self):
        """Create necessary output directories."""
        for directory in [self.valid_output_dir, os.path.dirname(self.invalid_output)]:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created output directory: {directory}")
    
    def _write_valid_emails(
        self,
        valid_emails: List[Tuple[str, str, str]]
    ) -> Tuple[int, int]:
        """
        Write valid emails to domain-specific files.
        
        Args:
            valid_emails: List of valid email tuples
            
        Returns:
            Tuple of (well_known_files_count, other_emails_count)
        """
        # Group emails by domain
        well_known_emails = {}
        other_emails = []
        
        for email, _, _ in valid_emails:
            try:
                domain = email.split('@')[1].lower()
                
                if domain in self.well_known_domains:
                    if domain not in well_known_emails:
                        well_known_emails[domain] = []
                    well_known_emails[domain].append(email)
                else:
                    other_emails.append(email)
            except (IndexError, AttributeError):
                logger.warning(f"Malformed valid email: {email}")
                continue
        
        # Write well-known domain files
        for domain, emails in well_known_emails.items():
            safe_domain = self.sanitize_domain_filename(domain)
            domain_file = os.path.join(self.valid_output_dir, f"{safe_domain}.txt")
            
            try:
                with open(domain_file, 'w', encoding='utf-8') as f:
                    for email in sorted(emails):
                        f.write(f"{email}\n")
                logger.info(f"Wrote {len(emails)} emails to {domain_file}")
            except Exception as e:
                logger.error(f"Error writing to {domain_file}: {e}")
        
        # Write other emails
        other_count = 0
        if other_emails:
            other_file = os.path.join(self.valid_output_dir, "other.txt")
            try:
                with open(other_file, 'w', encoding='utf-8') as f:
                    for email in sorted(other_emails):
                        f.write(f"{email}\n")
                other_count = len(other_emails)
                logger.info(f"Wrote {len(other_emails)} emails to {other_file}")
            except Exception as e:
                logger.error(f"Error writing to {other_file}: {e}")
        
        return len(well_known_emails), other_count
    
    def _write_invalid_emails(self, invalid_emails: List[Tuple[str, str, str]]):
        """Write invalid emails to file."""
        try:
            with open(self.invalid_output, 'w', encoding='utf-8') as f:
                for email, reason, category in invalid_emails:
                    f.write(f"{email} | {reason} | {category}\n")
            logger.info(f"Wrote {len(invalid_emails)} invalid emails to {self.invalid_output}")
        except Exception as e:
            logger.error(f"Error writing to {self.invalid_output}: {e}")
    
    def _print_summary(
        self,
        valid_count: int,
        invalid_count: int,
        well_known_files_count: int,
        other_count: int
    ):
        """Print summary to console."""
        print(f"\nValid emails saved to: {self.valid_output_dir}/")
        print(f"  - Created {well_known_files_count} well-known domain files")
        if other_count > 0:
            print(f"  - Created other.txt with {other_count} emails from unknown domains")
        print(f"  - Total valid emails: {valid_count}")
        print(f"Invalid emails saved to: {self.invalid_output}")
