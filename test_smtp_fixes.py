#!/usr/bin/env python3
"""
Test script to verify the three critical SMTP validation fixes:
1. SMTP validation executes when smtp_validation=True (even if deliverable_address=False)
2. Thread-safe socket patching (no global side effects)
3. Rate limiting doesn't serialize threads (lock released before sleep)
"""

import time
import threading
from unittest.mock import Mock, patch, MagicMock
from validators.core import EmailValidationService
from validators.smtp_validator import SMTPValidator
from validators.proxy_manager import ProxyManager
from validators.disposable import DisposableDomainChecker
from validators.http_dns_checker import HTTPDNSChecker


def test_smtp_validation_executes():
    """
    Test CRITICAL FIX 1: SMTP validation should execute even if deliverable_address=False
    """
    print("="*70)
    print("TEST 1: SMTP validation executes when smtp_validation=True")
    print("="*70)
    
    # Mock dependencies
    disposable_checker = Mock()
    disposable_checker.is_disposable = Mock(return_value=False)
    
    dns_checker = Mock()
    dns_checker.check_domain = Mock(return_value=(True, ""))
    dns_checker.get_mx_servers = Mock(return_value=['mx.example.com'])
    
    smtp_validator = Mock()
    smtp_validator.validate_mailbox = Mock(return_value=('valid', 250, 'OK', False))
    
    # Create service with deliverable_address=False but smtp_validation=True
    service = EmailValidationService(
        disposable_checker=disposable_checker,
        dns_checker=dns_checker,
        smtp_validator=smtp_validator,
        deliverable_address=False,  # DNS check disabled
        smtp_validation=True         # SMTP validation enabled
    )
    
    # Mock syntax validator
    service.syntax_validator.validate = Mock(return_value=(True, ""))
    service.syntax_validator.extract_domain = Mock(return_value="example.com")
    
    # Validate an email
    result = service.validate("test@example.com")
    
    # Verify SMTP validation was called
    if smtp_validator.validate_mailbox.called:
        print("✓ PASS: SMTP validation was executed")
        print(f"  - Called with: {smtp_validator.validate_mailbox.call_args}")
        print(f"  - Result: {result}")
        return True
    else:
        print("✗ FAIL: SMTP validation was NOT executed")
        print(f"  - dns_checker.check_domain called: {dns_checker.check_domain.called}")
        print(f"  - dns_checker.get_mx_servers called: {dns_checker.get_mx_servers.called}")
        return False


def test_thread_safe_socket_patching():
    """
    Test CRITICAL FIX 2: Socket patching is thread-safe (uses lock)
    """
    print("\n" + "="*70)
    print("TEST 2: Thread-safe socket patching")
    print("="*70)
    
    # Verify the SMTPValidator has a _socket_lock
    if hasattr(SMTPValidator, '_socket_lock'):
        print("✓ PASS: SMTPValidator has _socket_lock class attribute")
        
        # Verify it's a Lock by checking its type name
        lock_type = type(SMTPValidator._socket_lock).__name__
        if lock_type == 'lock':
            print(f"✓ PASS: _socket_lock is a threading.Lock instance (type: {lock_type})")
            return True
        else:
            print(f"✗ FAIL: _socket_lock is not a Lock instance (type: {lock_type})")
            return False
    else:
        print("✗ FAIL: SMTPValidator does not have _socket_lock")
        return False


def test_rate_limiting_concurrency():
    """
    Test CRITICAL FIX 3: Rate limiting doesn't hold lock while sleeping
    """
    print("\n" + "="*70)
    print("TEST 3: Rate limiting allows concurrency")
    print("="*70)
    
    # Create a temporary proxy file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        # Write 3 proxies
        f.write("proxy1.example.com:1080\n")
        f.write("proxy2.example.com:1080\n")
        f.write("proxy3.example.com:1080\n")
        proxy_file = f.name
    
    try:
        # Create proxy manager with 0.5 second rate limit
        pm = ProxyManager(proxy_file, rate_limit_seconds=0.5)
        
        # Verify proxies loaded
        if pm.get_proxy_count() != 3:
            print(f"✗ FAIL: Expected 3 proxies, got {pm.get_proxy_count()}")
            return False
        
        print(f"✓ Loaded {pm.get_proxy_count()} proxies")
        
        # Test concurrent access
        results = []
        times = []
        
        def get_proxy_with_timing(index):
            start = time.time()
            proxy = pm.get_next_proxy()
            end = time.time()
            results.append((index, proxy['host'], end - start))
            times.append(end)
        
        # Start 6 threads (2x the number of proxies)
        threads = []
        start_time = time.time()
        
        for i in range(6):
            t = threading.Thread(target=get_proxy_with_timing, args=(i,))
            t.start()
            threads.append(t)
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        total_time = time.time() - start_time
        
        print(f"\n  Concurrent proxy requests:")
        for index, host, duration in sorted(results):
            print(f"    Thread {index}: {host} (waited {duration:.3f}s)")
        
        print(f"\n  Total time: {total_time:.3f}s")
        
        # Analysis: If lock is held while sleeping, threads would be serialized
        # With 6 threads and 3 proxies with 0.5s rate limit:
        # - If concurrent: ~0.5s total (first 3 get proxies immediately, next 3 wait 0.5s)
        # - If serialized: ~1.5s total (each waits for previous)
        
        if total_time < 1.0:
            print(f"✓ PASS: Concurrent execution (total time: {total_time:.3f}s < 1.0s)")
            print("  - Lock is released before sleeping, enabling parallelism")
            return True
        else:
            print(f"✗ FAIL: Serialized execution (total time: {total_time:.3f}s >= 1.0s)")
            print("  - Lock might be held during sleep, blocking threads")
            return False
    
    finally:
        import os
        os.unlink(proxy_file)


def test_smtp_result_mapping():
    """
    Test that SMTP results are correctly mapped to output categories
    """
    print("\n" + "="*70)
    print("TEST 4: SMTP result mapping to output categories")
    print("="*70)
    
    # Mock dependencies
    disposable_checker = Mock()
    disposable_checker.is_disposable = Mock(return_value=False)
    
    dns_checker = Mock()
    dns_checker.check_domain = Mock(return_value=(True, ""))
    dns_checker.get_mx_servers = Mock(return_value=['mx.example.com'])
    
    smtp_validator = Mock()
    
    service = EmailValidationService(
        disposable_checker=disposable_checker,
        dns_checker=dns_checker,
        smtp_validator=smtp_validator,
        deliverable_address=True,
        smtp_validation=True
    )
    
    service.syntax_validator.validate = Mock(return_value=(True, ""))
    service.syntax_validator.extract_domain = Mock(return_value="example.com")
    
    test_cases = [
        # (smtp_status, smtp_code, smtp_message, is_catchall) -> expected_category
        (('valid', 250, 'OK', False), 'valid'),
        (('catch-all', 250, 'Catch-all enabled', True), 'risk'),
        (('invalid', 550, 'No such user', False), 'invalid'),
        (('unknown', 0, 'Connection failed', False), 'unknown'),
    ]
    
    all_passed = True
    
    for smtp_result, expected_category in test_cases:
        smtp_validator.validate_mailbox.return_value = smtp_result
        
        _, is_valid, reason, category = service.validate("test@example.com")
        
        if category == expected_category:
            print(f"✓ PASS: SMTP {smtp_result[0]} -> category '{category}'")
        else:
            print(f"✗ FAIL: SMTP {smtp_result[0]} -> expected '{expected_category}', got '{category}'")
            all_passed = False
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "="*70)
    print("CRITICAL FIXES VERIFICATION TEST SUITE")
    print("="*70 + "\n")
    
    # Run all tests
    result1 = test_smtp_validation_executes()
    result2 = test_thread_safe_socket_patching()
    result3 = test_rate_limiting_concurrency()
    result4 = test_smtp_result_mapping()
    
    # Final summary
    print("\n" + "="*70)
    print("FINAL TEST SUMMARY")
    print("="*70)
    print(f"Issue 1 - SMTP validation executes:    {'✓ PASSED' if result1 else '✗ FAILED'}")
    print(f"Issue 2 - Thread-safe socket patching: {'✓ PASSED' if result2 else '✗ FAILED'}")
    print(f"Issue 3 - Rate limiting concurrency:   {'✓ PASSED' if result3 else '✗ FAILED'}")
    print(f"Bonus   - SMTP result mapping:         {'✓ PASSED' if result4 else '✗ FAILED'}")
    print("="*70)
    
    if result1 and result2 and result3 and result4:
        print("✓ ALL CRITICAL FIXES VERIFIED SUCCESSFULLY!")
        exit(0)
    else:
        print("✗ SOME CRITICAL FIXES FAILED VERIFICATION!")
        exit(1)
    print("="*70 + "\n")
