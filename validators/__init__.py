"""
Email validation package with modular components.
"""

from .core import EmailValidationService
from .dns_checker import DNSChecker
from .disposable import DisposableDomainChecker
from .io_handler import EmailIOHandler

__all__ = [
    'EmailValidationService',
    'DNSChecker',
    'DisposableDomainChecker',
    'EmailIOHandler'
]
