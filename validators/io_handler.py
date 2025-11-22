"""
File I/O operations module for email validation.
"""

from typing import List, Tuple, Dict, Set
import os
import re
import time
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
        summary_output: str,
        well_known_domains_file: str
    ):
        """
        Initialize I/O handler.
        
        Args:
            input_file: Path to input emails file
            valid_output_dir: Directory for valid emails output
            invalid_output: Path to invalid emails output file
            summary_output: Path to summary statistics file
            well_known_domains_file: Path to well-known domains config file
        """
        self.input_file = input_file
        self.valid_output_dir = valid_output_dir
        self.invalid_output = invalid_output
        self.summary_output = summary_output
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
    
    def read_emails(self) -> List[str]:
        """
        Read emails from input file.
        
        Returns:
            List of email addresses
        """
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                emails = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(emails)} emails from {self.input_file}")
            return emails
        except FileNotFoundError:
            logger.error(f"Input file not found: {self.input_file}")
            return []
        except Exception as e:
            logger.error(f"Error reading input file: {e}")
            return []
    
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
        invalid_emails: List[Tuple[str, str, str]],
        start_time: float,
        total_emails: int
    ):
        """
        Write validation results to output files.
        
        Args:
            valid_emails: List of (email, reason, category) tuples for valid emails
            invalid_emails: List of (email, reason, category) tuples for invalid emails
            start_time: Validation start time
            total_emails: Total number of emails processed
        """
        # Create output directories
        self._create_output_directories()
        
        # Group and write valid emails
        well_known_files, other_count = self._write_valid_emails(valid_emails)
        
        # Write invalid emails
        self._write_invalid_emails(invalid_emails)
        
        # Calculate statistics
        elapsed_time = time.time() - start_time
        invalid_by_category = self._categorize_invalid(invalid_emails)
        
        # Write summary
        self._write_summary(
            total_emails,
            len(valid_emails),
            len(invalid_emails),
            well_known_files,
            other_count,
            invalid_by_category,
            elapsed_time
        )
        
        # Print summary
        self._print_summary(len(valid_emails), len(invalid_emails), well_known_files, other_count)
    
    def _create_output_directories(self):
        """Create necessary output directories."""
        for directory in [self.valid_output_dir, os.path.dirname(self.invalid_output)]:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created output directory: {directory}")
    
    def _write_valid_emails(
        self,
        valid_emails: List[Tuple[str, str, str]]
    ) -> Tuple[Dict[str, int], int]:
        """
        Write valid emails to domain-specific files.
        
        Args:
            valid_emails: List of valid email tuples
            
        Returns:
            Tuple of (well_known_files_dict, other_count)
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
        well_known_files = {}
        for domain, emails in well_known_emails.items():
            safe_domain = self.sanitize_domain_filename(domain)
            domain_file = os.path.join(self.valid_output_dir, f"{safe_domain}.txt")
            
            try:
                with open(domain_file, 'w', encoding='utf-8') as f:
                    for email in sorted(emails):
                        f.write(f"{email}\n")
                well_known_files[domain] = len(emails)
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
        
        return well_known_files, other_count
    
    def _write_invalid_emails(self, invalid_emails: List[Tuple[str, str, str]]):
        """Write invalid emails to file."""
        try:
            with open(self.invalid_output, 'w', encoding='utf-8') as f:
                for email, reason, category in invalid_emails:
                    f.write(f"{email} | {reason} | {category}\n")
            logger.info(f"Wrote {len(invalid_emails)} invalid emails to {self.invalid_output}")
        except Exception as e:
            logger.error(f"Error writing to {self.invalid_output}: {e}")
    
    @staticmethod
    def _categorize_invalid(invalid_emails: List[Tuple[str, str, str]]) -> Dict[str, int]:
        """Categorize invalid emails by error type."""
        invalid_by_category = {}
        for _, _, category in invalid_emails:
            invalid_by_category[category] = invalid_by_category.get(category, 0) + 1
        return invalid_by_category
    
    def _write_summary(
        self,
        total: int,
        valid: int,
        invalid: int,
        well_known_files: Dict[str, int],
        other_count: int,
        invalid_by_category: Dict[str, int],
        elapsed_time: float
    ):
        """Write summary statistics file."""
        try:
            summary_dir = os.path.dirname(self.summary_output)
            if summary_dir and not os.path.exists(summary_dir):
                os.makedirs(summary_dir, exist_ok=True)
            
            with open(self.summary_output, 'w', encoding='utf-8') as f:
                f.write("="*70 + "\n")
                f.write("EMAIL VALIDATION SUMMARY REPORT\n")
                f.write("="*70 + "\n")
                f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Overall statistics
                f.write("OVERALL STATISTICS\n")
                f.write("-"*70 + "\n")
                f.write(f"Total Emails Processed:     {total:,}\n")
                f.write(f"Valid Emails:               {valid:,} ({valid*100/total:.1f}%)\n")
                f.write(f"Invalid Emails:             {invalid:,} ({invalid*100/total:.1f}%)\n")
                f.write(f"Processing Time:            {elapsed_time:.2f} seconds\n")
                f.write(f"Processing Speed:           {total/elapsed_time:.2f} emails/second\n\n")
                
                # Valid emails breakdown
                f.write("VALID EMAILS BY DOMAIN\n")
                f.write("-"*70 + "\n")
                
                for domain, count in sorted(well_known_files.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {domain:<40} {count:>8,} emails\n")
                
                if other_count > 0:
                    f.write(f"  {'Other domains (other.txt)':<40} {other_count:>8,} emails\n")
                
                f.write(f"\n  {'TOTAL VALID':<40} {valid:>8,} emails\n\n")
                
                # Invalid emails breakdown
                f.write("INVALID EMAILS BY CATEGORY\n")
                f.write("-"*70 + "\n")
                for category, count in sorted(invalid_by_category.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {category.capitalize():<40} {count:>8,} emails\n")
                f.write(f"\n  {'TOTAL INVALID':<40} {invalid:>8,} emails\n\n")
                
                # File locations
                f.write("OUTPUT FILES\n")
                f.write("-"*70 + "\n")
                f.write(f"Valid emails (well-known):  {self.valid_output_dir}/<domain>.txt\n")
                if other_count > 0:
                    f.write(f"Valid emails (other):       {self.valid_output_dir}/other.txt\n")
                f.write(f"Invalid emails:             {self.invalid_output}\n")
                f.write("="*70 + "\n")
            
            logger.info(f"Summary statistics written to {self.summary_output}")
        except Exception as e:
            logger.error(f"Error writing summary file: {e}")
    
    def _print_summary(
        self,
        valid_count: int,
        invalid_count: int,
        well_known_files: Dict[str, int],
        other_count: int
    ):
        """Print summary to console."""
        print(f"\nValid emails saved to: {self.valid_output_dir}/")
        print(f"  - Created {len(well_known_files)} well-known domain files")
        if other_count > 0:
            print(f"  - Created other.txt with {other_count} emails from unknown domains")
        print(f"  - Total valid emails: {valid_count}")
        print(f"Invalid emails saved to: {self.invalid_output}")
        print(f"\nSummary statistics saved to: {self.summary_output}")
