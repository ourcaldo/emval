"""
Email validation package with modular components.
"""

from .core import EmailValidationService
from .http_dns_checker import HTTPDNSChecker
from .local_dns_checker import LocalDNSChecker
from .disposable import DisposableDomainChecker
from .io_handler import EmailIOHandler
from .syntax_validator import EmailSyntaxValidator
from .proxy_manager import ProxyManager

__all__ = [
    'EmailValidationService',
    'HTTPDNSChecker',
    'LocalDNSChecker',
    'DisposableDomainChecker',
    'EmailIOHandler',
    'EmailSyntaxValidator',
    'ProxyManager'
]
