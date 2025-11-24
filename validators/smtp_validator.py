"""
SMTP Email Validator - RCPT TO and Catch-All Detection.

This module validates email addresses by connecting to mail servers
and checking if the mailbox actually exists using SMTP RCPT TO command.
"""

import socks
import socket
import smtplib
import logging
import random
import string
from typing import Tuple, Optional, Dict, Any
from email.utils import parseaddr
from threading import Lock

logger = logging.getLogger(__name__)


class SMTPValidator:
    """
    Validates email addresses using SMTP RCPT TO command.
    Detects catch-all domains and verifies individual mailboxes.
    """
    
    # Class-level lock for thread-safe socket patching
    _socket_lock = Lock()
    
    VALID_CODES = [250, 251]
    INVALID_CODES = [550, 551, 553]
    MAILBOX_FULL_CODE = 552
    TEMPORARY_ERROR_CODES = [450, 451, 452, 421]
    AMBIGUOUS_CODE = 252
    TLS_REQUIRED_CODE = 530
    
    def __init__(
        self,
        proxy_manager=None,
        from_email: str = "verify@example.com",
        max_retries: int = 2
    ):
        """
        Initialize SMTP validator.
        
        Args:
            proxy_manager: ProxyManager instance for SOCKS5 proxies
            from_email: Email address to use in MAIL FROM command
            max_retries: Maximum retry attempts for SMTP errors
        """
        self.proxy_manager = proxy_manager
        self.timeout = 8
        self.from_email = from_email
        self.max_retries = max_retries
        
        logger.info("SMTPValidator initialized")
        logger.info(f"From: {from_email}, Max retries: {max_retries}")
    
    def _generate_random_email(self, domain: str) -> str:
        """
        Generate random email address for catch-all detection.
        
        Args:
            domain: Email domain
            
        Returns:
            Random email address
        """
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
        return f"verify{random_str}@{domain}"
    
    def _setup_socks5_proxy(self, proxy: Dict[str, Any]) -> None:
        """
        Setup SOCKS5 proxy for socket connections.
        
        Args:
            proxy: Proxy dictionary with host, port, username, password
        """
        if not proxy:
            socks.set_default_proxy()
            socket.socket = socks.socksocket
            return
        
        if proxy.get('username') and proxy.get('password'):
            socks.set_default_proxy(
                socks.SOCKS5,
                proxy['host'],
                proxy['port'],
                username=proxy['username'],
                password=proxy['password']
            )
        else:
            socks.set_default_proxy(
                socks.SOCKS5,
                proxy['host'],
                proxy['port']
            )
        
        socket.socket = socks.socksocket
        logger.debug(f"SOCKS5 proxy configured: {proxy['host']}:{proxy['port']}")
    
    def _reset_socket(self) -> None:
        """Reset socket to default (remove proxy)."""
        socks.set_default_proxy()
        import importlib
        importlib.reload(socket)
    
    def _connect_smtp(self, mx_server: str, use_tls: bool = True) -> Tuple[Optional[smtplib.SMTP], Optional[str]]:
        """
        Connect to SMTP server with TLS support.
        
        Args:
            mx_server: Mail server hostname
            use_tls: Whether to use STARTTLS
            
        Returns:
            Tuple of (SMTP connection, error message)
        """
        try:
            smtp = smtplib.SMTP(timeout=self.timeout)
            smtp.connect(mx_server, 25)
            smtp.ehlo()
            
            if use_tls:
                if smtp.has_extn('STARTTLS'):
                    smtp.starttls()
                    smtp.ehlo()
            
            return smtp, None
        
        except socket.timeout:
            return None, "Connection timeout"
        except smtplib.SMTPException as e:
            return None, f"SMTP error: {str(e)}"
        except socket.error as e:
            return None, f"Socket error: {str(e)}"
        except Exception as e:
            return None, f"Connection error: {str(e)}"
    
    def _check_rcpt_to(self, smtp: smtplib.SMTP, email: str) -> Tuple[int, str]:
        """
        Check if email is accepted using RCPT TO command.
        
        Args:
            smtp: SMTP connection
            email: Email address to check
            
        Returns:
            Tuple of (response code, response message)
        """
        try:
            smtp.mail(self.from_email)
            code, message = smtp.rcpt(email)
            return code, message.decode() if isinstance(message, bytes) else str(message)
        
        except smtplib.SMTPRecipientsRefused as e:
            if email in e.recipients:
                code, msg = e.recipients[email]
                return code, msg.decode() if isinstance(msg, bytes) else str(msg)
            return 550, "Recipient refused"
        
        except smtplib.SMTPResponseException as e:
            return e.smtp_code, str(e.smtp_error)
        
        except Exception as e:
            logger.debug(f"RCPT TO check error: {e}")
            return 0, str(e)
    
    def validate_mailbox(
        self,
        email: str,
        mx_server: str,
        check_catchall: bool = True
    ) -> Tuple[str, int, str, bool]:
        """
        Validate email mailbox using SMTP RCPT TO.
        
        Args:
            email: Email address to validate
            mx_server: Mail server to connect to
            check_catchall: Whether to check for catch-all
            
        Returns:
            Tuple of (status, code, message, is_catchall)
            status: 'valid', 'invalid', 'unknown', 'catch-all'
            code: SMTP response code
            message: Response message
            is_catchall: Whether domain has catch-all enabled
        """
        proxy = None
        if self.proxy_manager and self.proxy_manager.is_enabled():
            proxy = self.proxy_manager.get_next_proxy()
        
        try:
            # Thread-safe socket patching and SMTP connection creation
            with self._socket_lock:
                original_socket = socket.socket
                try:
                    if proxy:
                        self._setup_socks5_proxy(proxy)
                    
                    # Create SMTP connection while socket is patched
                    smtp = smtplib.SMTP(timeout=self.timeout)
                    smtp.connect(mx_server, 25)
                finally:
                    # Restore socket immediately to avoid global side effects
                    socket.socket = original_socket
                    socks.set_default_proxy()
            
            # Continue with SMTP operations outside the lock
            try:
                smtp.ehlo()
                
                # Check for STARTTLS support
                if smtp.has_extn('STARTTLS'):
                    smtp.starttls()
                    smtp.ehlo()
            except Exception as e:
                smtp.close()
                logger.debug(f"Failed SMTP handshake with {mx_server}: {e}")
                return 'unknown', 0, f"SMTP handshake failed: {str(e)}", False
            
            # Step 4: Validate the REAL email FIRST using RCPT TO
            code, message = self._check_rcpt_to(smtp, email)
            
            # If real email is invalid, return immediately
            if code in self.INVALID_CODES or code == self.MAILBOX_FULL_CODE:
                smtp.quit()
                status = 'invalid'
                if code == self.MAILBOX_FULL_CODE:
                    message = f"Mailbox full: {message}"
                logger.debug(f"Step 4 FAIL - SMTP RCPT TO: {email} - {status} (code: {code})")
                return status, code, message, False
            
            # If real email check returned temporary error or ambiguous response
            if code in self.TEMPORARY_ERROR_CODES or code == self.AMBIGUOUS_CODE or code not in self.VALID_CODES:
                smtp.quit()
                status = 'unknown'
                if code == self.AMBIGUOUS_CODE:
                    message = f"Ambiguous response: {message}"
                elif code in self.TEMPORARY_ERROR_CODES:
                    message = f"Temporary error: {message}"
                else:
                    message = f"Unknown code {code}: {message}"
                logger.debug(f"Step 4 UNKNOWN - SMTP RCPT TO: {email} - {status} (code: {code})")
                return status, code, message, False
            
            # Step 5: Real email is valid (250/251), now check for catch-all
            is_catchall = False
            
            if check_catchall:
                domain = email.split('@')[1]
                random_email = self._generate_random_email(domain)
                
                catchall_code, catchall_message = self._check_rcpt_to(smtp, random_email)
                
                if catchall_code in self.VALID_CODES:
                    logger.debug(f"Step 5 FAIL - Catch-all detected for {domain} (random email accepted)")
                    is_catchall = True
                    smtp.quit()
                    # Real email is valid BUT catch-all is enabled → RISK
                    return 'catch-all', code, 'Valid but catch-all enabled (risky)', True
                else:
                    logger.debug(f"Step 5 PASS - Catch-all: {domain} - Not a catch-all domain")
            
            # Real email is valid AND catch-all is NOT detected → VALID (safe)
            smtp.quit()
            
            logger.debug(f"Step 4 PASS - SMTP RCPT TO: {email} - Mailbox exists (code: {code})")
            logger.debug(f"SMTP validation result for {email}: valid (code: {code})")
            
            return 'valid', code, message, is_catchall
        
        except Exception as e:
            logger.error(f"SMTP validation error for {email}: {e}")
            return 'unknown', 0, f"Error: {str(e)}", False
    
    def get_validator_info(self) -> Dict[str, Any]:
        """
        Get validator configuration info.
        
        Returns:
            Dictionary with configuration details
        """
        return {
            'timeout': self.timeout,
            'from_email': self.from_email,
            'max_retries': self.max_retries,
            'proxy_enabled': self.proxy_manager is not None and self.proxy_manager.is_enabled(),
            'proxy_count': self.proxy_manager.get_proxy_count() if self.proxy_manager else 0
        }
