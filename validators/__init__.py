"""
Email validation package with modular components.
"""

from .core import EmailValidationService
from .http_dns_checker import HTTPDNSChecker
from .disposable import DisposableDomainChecker
from .io_handler import EmailIOHandler
from .syntax_validator import EmailSyntaxValidator

__all__ = [
    'EmailValidationService',
    'HTTPDNSChecker',
    'DisposableDomainChecker',
    'EmailIOHandler',
    'EmailSyntaxValidator'
]
