"""
File I/O operations module for email validation.
"""

from typing import List, Tuple, Dict, Set, Sequence
import os
import re
import logging
import threading

logger = logging.getLogger(__name__)


class EmailIOHandler:
    """
    Handles all file I/O operations for email validation.
    """
    
    def __init__(
        self,
        input_file: str,
        valid_output_dir: str,
        risk_output_dir: str,
        invalid_output: str,
        unknown_output: str,
        well_known_domains_file: str
    ):
        """
        Initialize I/O handler.
        
        Args:
            input_file: Path to input emails file
            valid_output_dir: Directory for valid emails output (passed all validations)
            risk_output_dir: Directory for risky emails output (catch-all domains)
            invalid_output: Path to invalid emails output file
            unknown_output: Path to unknown emails output file (SMTP errors)
            well_known_domains_file: Path to well-known domains config file
        """
        self.input_file = input_file
        self.valid_output_dir = valid_output_dir
        self.risk_output_dir = risk_output_dir
        self.invalid_output = invalid_output
        self.unknown_output = unknown_output
        self.well_known_domains_file = well_known_domains_file
        self.well_known_domains = self._load_well_known_domains()
        self._write_lock = threading.Lock()
        self._directories_created = False
        self._seen_emails_cache = {}
    
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
        all_emails: List[Tuple[str, str, str]]
    ):
        """
        Write validation results to output files based on categories.
        
        Args:
            all_emails: List of (email, reason, category) tuples
                category can be: 'valid', 'risk', 'invalid', 'unknown'
        """
        # Create output directories
        self._create_output_directories()
        
        # Separate emails by category
        valid_emails = [(e, r, c) for e, r, c in all_emails if c == 'valid']
        risk_emails = [(e, r, c) for e, r, c in all_emails if c == 'risk']
        invalid_emails = [(e, r, c) for e, r, c in all_emails if c == 'invalid']
        unknown_emails = [(e, r, c) for e, r, c in all_emails if c == 'unknown']
        
        # Write each category
        valid_wk_count, valid_other_count = self._write_category_emails(valid_emails, self.valid_output_dir, "valid")
        risk_wk_count, risk_other_count = self._write_category_emails(risk_emails, self.risk_output_dir, "risk")
        
        self._write_single_file_category(invalid_emails, self.invalid_output, "invalid")
        self._write_single_file_category(unknown_emails, self.unknown_output, "unknown")
        
        # Print summary
        self._print_summary(
            len(valid_emails), len(risk_emails), len(invalid_emails), len(unknown_emails),
            valid_wk_count, valid_other_count, risk_wk_count, risk_other_count
        )
    
    def _create_output_directories(self):
        """Create necessary output directories."""
        directories = [
            self.valid_output_dir,
            self.risk_output_dir,
            os.path.dirname(self.invalid_output),
            os.path.dirname(self.unknown_output)
        ]
        for directory in directories:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Created output directory: {directory}")
    
    def _write_category_emails(
        self,
        emails: Sequence[Tuple[str, str, str]],
        output_dir: str,
        category_name: str
    ) -> Tuple[int, int]:
        """
        Write emails to domain-specific files in a category directory.
        Uses append mode to preserve existing results.
        
        Args:
            emails: List of email tuples
            output_dir: Output directory for this category
            category_name: Category name for logging
            
        Returns:
            Tuple of (well_known_files_count, other_emails_count)
        """
        # Group emails by domain
        well_known_emails = {}
        other_emails = []
        
        for email, _, _ in emails:
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
        
        # Write well-known domain files (email only) in append mode
        for domain, domain_emails in well_known_emails.items():
            safe_domain = self.sanitize_domain_filename(domain)
            domain_file = os.path.join(output_dir, f"{safe_domain}.txt")
            
            try:
                # Read existing emails to avoid duplicates
                existing_emails = set()
                if os.path.exists(domain_file):
                    with open(domain_file, 'r', encoding='utf-8') as f:
                        existing_emails = set(line.strip().lower() for line in f if line.strip())
                
                # Only write new emails
                new_emails = [e for e in sorted(domain_emails) if e.lower() not in existing_emails]
                
                if new_emails:
                    with open(domain_file, 'a', encoding='utf-8') as f:
                        for email in new_emails:
                            f.write(f"{email}\n")
                    logger.info(f"Appended {len(new_emails)} new emails to {domain_file}")
                else:
                    logger.info(f"No new emails to append to {domain_file}")
            except Exception as e:
                logger.error(f"Error writing to {domain_file}: {e}")
        
        # Write other emails (email only) in append mode
        other_count = 0
        if other_emails:
            other_file = os.path.join(output_dir, "other.txt")
            try:
                # Read existing emails to avoid duplicates
                existing_emails = set()
                if os.path.exists(other_file):
                    with open(other_file, 'r', encoding='utf-8') as f:
                        existing_emails = set(line.strip().lower() for line in f if line.strip())
                
                # Only write new emails
                new_emails = [e for e in sorted(other_emails) if e.lower() not in existing_emails]
                
                if new_emails:
                    with open(other_file, 'a', encoding='utf-8') as f:
                        for email in new_emails:
                            f.write(f"{email}\n")
                    other_count = len(new_emails)
                    logger.info(f"Appended {len(new_emails)} new emails to {other_file}")
                else:
                    logger.info(f"No new emails to append to {other_file}")
            except Exception as e:
                logger.error(f"Error writing to {other_file}: {e}")
        
        return len(well_known_emails), other_count
    
    def _write_single_file_category(
        self,
        emails: Sequence[Tuple[str, str, str]],
        output_file: str,
        category_name: str
    ):
        """
        Write emails to a single file (email only, no reason) in append mode.
        
        Args:
            emails: List of email tuples
            output_file: Output file path
            category_name: Category name for logging
        """
        try:
            # Read existing emails to avoid duplicates
            existing_emails = set()
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_emails = set(line.strip().lower() for line in f if line.strip())
            
            # Only write new emails
            new_emails = [email for email, _, _ in emails if email.lower() not in existing_emails]
            
            if new_emails:
                with open(output_file, 'a', encoding='utf-8') as f:
                    for email in new_emails:
                        f.write(f"{email}\n")
                logger.info(f"Appended {len(new_emails)} new {category_name} emails to {output_file}")
            else:
                logger.info(f"No new {category_name} emails to append to {output_file}")
        except Exception as e:
            logger.error(f"Error writing {category_name} emails to {output_file}: {e}")
    
    def _print_summary(
        self,
        valid_count: int,
        risk_count: int,
        invalid_count: int,
        unknown_count: int,
        valid_wk_count: int,
        valid_other_count: int,
        risk_wk_count: int,
        risk_other_count: int
    ):
        """Print summary to console - Disabled for cleaner output."""
        # Summary is now merged into VALIDATION SUMMARY in main()
        pass
    
    def write_single_result(self, email: str, reason: str, category: str):
        """
        Write a single email result immediately (thread-safe).
        This allows incremental saving so data is preserved even if process is stopped.
        
        Args:
            email: Email address
            reason: Validation reason/message
            category: Category ('valid', 'risk', 'invalid', 'unknown')
        """
        with self._write_lock:
            # Create output directories on first write
            if not self._directories_created:
                self._create_output_directories()
                self._directories_created = True
            
            try:
                # Extract domain for categorization
                domain = email.split('@')[1].lower() if '@' in email else None
                
                if category == 'valid' or category == 'risk':
                    # Determine output directory
                    output_dir = self.valid_output_dir if category == 'valid' else self.risk_output_dir
                    
                    # Check if well-known domain
                    if domain and domain in self.well_known_domains:
                        # Write to domain-specific file
                        safe_domain = self.sanitize_domain_filename(domain)
                        output_file = os.path.join(output_dir, f"{safe_domain}.txt")
                    else:
                        # Write to other.txt
                        output_file = os.path.join(output_dir, "other.txt")
                    
                    # Check for duplicates before writing
                    if self._is_email_already_saved(output_file, email):
                        logger.debug(f"Email already saved, skipping: {email}")
                        return
                    
                    # Append email to file
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"{email}\n")
                    
                    # Update cache AFTER successful write
                    self._mark_email_as_saved(output_file, email)
                    logger.debug(f"Saved {category} email to {output_file}: {email}")
                
                elif category == 'invalid':
                    # Write to invalid file
                    if self._is_email_already_saved(self.invalid_output, email):
                        logger.debug(f"Email already saved, skipping: {email}")
                        return
                    
                    with open(self.invalid_output, 'a', encoding='utf-8') as f:
                        f.write(f"{email}\n")
                    
                    # Update cache AFTER successful write
                    self._mark_email_as_saved(self.invalid_output, email)
                    logger.debug(f"Saved invalid email: {email}")
                
                elif category == 'unknown':
                    # Write to unknown file
                    if self._is_email_already_saved(self.unknown_output, email):
                        logger.debug(f"Email already saved, skipping: {email}")
                        return
                    
                    with open(self.unknown_output, 'a', encoding='utf-8') as f:
                        f.write(f"{email}\n")
                    
                    # Update cache AFTER successful write
                    self._mark_email_as_saved(self.unknown_output, email)
                    logger.debug(f"Saved unknown email: {email}")
                
            except Exception as e:
                logger.error(f"Error writing single result for {email}: {e}")
    
    def _is_email_already_saved(self, file_path: str, email: str) -> bool:
        """
        Check if email is already saved in the file to avoid duplicates.
        Uses in-memory cache to avoid O(n^2) file I/O.
        This is a pure check - does NOT mutate the cache.
        
        Args:
            file_path: Path to the output file
            email: Email to check
            
        Returns:
            True if email already exists in file or cache, False otherwise
        """
        # Lazy load cache for this file on first access
        if file_path not in self._seen_emails_cache:
            self._seen_emails_cache[file_path] = set()
            
            # If file exists, load existing emails into cache
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_emails = set(line.strip().lower() for line in f if line.strip())
                    self._seen_emails_cache[file_path] = existing_emails
                    logger.debug(f"Loaded {len(existing_emails)} existing emails into cache for {file_path}")
                except Exception as e:
                    logger.error(f"Error loading cache for {file_path}: {e}")
        
        # Check cache (pure check, no mutation)
        email_lower = email.lower()
        return email_lower in self._seen_emails_cache[file_path]
    
    def _mark_email_as_saved(self, file_path: str, email: str):
        """
        Mark email as saved in the cache AFTER successful write.
        
        Args:
            file_path: Path to the output file
            email: Email to mark as saved
        """
        # Ensure cache exists for this file
        if file_path not in self._seen_emails_cache:
            self._seen_emails_cache[file_path] = set()
        
        # Add to cache
        email_lower = email.lower()
        self._seen_emails_cache[file_path].add(email_lower)
    
    def get_output_info(self) -> dict:
        """
        Get output file information for display in summary.
        
        Returns:
            Dictionary with output directory and file paths
        """
        return {
            'valid_dir': self.valid_output_dir,
            'risk_dir': self.risk_output_dir,
            'invalid_file': self.invalid_output,
            'unknown_file': self.unknown_output
        }
