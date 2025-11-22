#!/usr/bin/env python3
"""
Test script to verify the three critical fixes:
1. A-record fallback logic
2. Cache completeness
3. Plus-addressing provider-aware logic
"""

from validators import EmailValidationService, HTTPDNSChecker, DisposableDomainChecker

def test_plus_addressing():
    """Test provider-aware plus-addressing logic."""
    print("="*70)
    print("TEST 1: Provider-aware Plus-addressing Logic")
    print("="*70)
    
    # Initialize components
    disposable_checker = DisposableDomainChecker('data/disposable_domains.txt')
    dns_checker = HTTPDNSChecker(cache_size=100)
    validation_service = EmailValidationService(
        disposable_checker=disposable_checker,
        dns_checker=dns_checker,
        deliverable_address=False  # Disable DNS check for this test
    )
    
    # Test cases
    test_cases = [
        # Gmail/Google domains - should be INVALID
        ("user+tag@gmail.com", False, "Plus-addressing rejected for Gmail"),
        ("test+alias@googlemail.com", False, "Plus-addressing rejected for Google Mail"),
        ("admin+test@google.com", False, "Plus-addressing rejected for Google"),
        
        # Other domains - should be VALID (syntax-wise)
        ("user+tag@yahoo.com", True, "Plus-addressing allowed for Yahoo"),
        ("test+alias@outlook.com", True, "Plus-addressing allowed for Outlook"),
        ("admin+test@example.org", True, "Plus-addressing allowed for other domains"),
        
        # Non plus-addressing - should be VALID (syntax-wise)
        ("user@gmail.com", True, "Normal Gmail address allowed"),
        ("test@yahoo.com", True, "Normal Yahoo address allowed"),
    ]
    
    print("\nTesting plus-addressing validation:\n")
    all_passed = True
    
    for email, expected_valid, description in test_cases:
        _, is_valid, reason, category = validation_service.validate(email)
        status = "✓ PASS" if is_valid == expected_valid else "✗ FAIL"
        
        if is_valid != expected_valid:
            all_passed = False
            
        print(f"{status} | {email:30s} | Expected: {'VALID' if expected_valid else 'INVALID':7s} | Got: {'VALID' if is_valid else 'INVALID':7s} | {description}")
        if not is_valid:
            print(f"       Reason: {reason}")
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL PLUS-ADDRESSING TESTS PASSED!")
    else:
        print("✗ SOME PLUS-ADDRESSING TESTS FAILED!")
    print("="*70 + "\n")
    
    return all_passed


def test_dns_parsing():
    """Test DNS response parsing (Issues 1 and 2)."""
    print("="*70)
    print("TEST 2: DNS Response Parsing (A-record fallback & Cache)")
    print("="*70)
    
    dns_checker = HTTPDNSChecker(cache_size=100)
    
    # Test the _parse_dns_response method directly with mock data
    test_cases = [
        {
            "name": "Valid MX records",
            "data": {
                "status": "OK",
                "records": {
                    "MX": [{"exchange": "mail.example.com"}],
                    "A": []
                }
            },
            "expected": (True, "")
        },
        {
            "name": "No MX, but valid A records",
            "data": {
                "status": "OK",
                "records": {
                    "MX": [],
                    "A": ["192.168.1.1"]
                }
            },
            "expected": (True, "")
        },
        {
            "name": "MX records exist but invalid (should NOT fall back to A)",
            "data": {
                "status": "OK",
                "records": {
                    "MX": [{"exchange": ""}],
                    "A": ["192.168.1.1"]
                }
            },
            "expected": (False, "MX records exist but are invalid")
        },
        {
            "name": "No MX and no A records",
            "data": {
                "status": "OK",
                "records": {
                    "MX": [],
                    "A": []
                }
            },
            "expected": (False, "No MX or A records found")
        },
        {
            "name": "Invalid status (should return None for retry)",
            "data": {
                "status": "ERROR",
                "records": {}
            },
            "expected": None
        }
    ]
    
    print("\nTesting DNS response parsing:\n")
    all_passed = True
    
    for test_case in test_cases:
        result = dns_checker._parse_dns_response("test.com", test_case["data"])
        expected = test_case["expected"]
        
        if result == expected:
            print(f"✓ PASS | {test_case['name']}")
        else:
            all_passed = False
            print(f"✗ FAIL | {test_case['name']}")
            print(f"       Expected: {expected}")
            print(f"       Got: {result}")
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL DNS PARSING TESTS PASSED!")
    else:
        print("✗ SOME DNS PARSING TESTS FAILED!")
    print("="*70 + "\n")
    
    return all_passed


def test_exception_safety():
    """Test that _parse_dns_response never raises exceptions."""
    print("="*70)
    print("TEST 3: Exception Safety (Cache completeness)")
    print("="*70)
    
    dns_checker = HTTPDNSChecker(cache_size=100)
    
    # Test cases that could potentially cause exceptions
    test_cases = [
        {"name": "Malformed data (missing status)", "data": {}},
        {"name": "Malformed data (missing records)", "data": {"status": "OK"}},
        {"name": "Malformed MX (not a dict)", "data": {"status": "OK", "records": {"MX": ["string"]}}},
        {"name": "Malformed A (not a list)", "data": {"status": "OK", "records": {"A": "string"}}},
        {"name": "None data", "data": None},
    ]
    
    print("\nTesting exception safety:\n")
    all_passed = True
    
    for test_case in test_cases:
        try:
            result = dns_checker._parse_dns_response("test.com", test_case["data"])
            # Should always return either a tuple or None, never raise
            if result is None or isinstance(result, tuple):
                print(f"✓ PASS | {test_case['name']} - Returned {type(result).__name__}")
            else:
                all_passed = False
                print(f"✗ FAIL | {test_case['name']} - Returned unexpected type: {type(result)}")
        except Exception as e:
            all_passed = False
            print(f"✗ FAIL | {test_case['name']} - Raised exception: {e}")
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL EXCEPTION SAFETY TESTS PASSED!")
    else:
        print("✗ SOME EXCEPTION SAFETY TESTS FAILED!")
    print("="*70 + "\n")
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "="*70)
    print("CRITICAL FIXES VERIFICATION TEST SUITE")
    print("="*70 + "\n")
    
    # Run all tests
    result1 = test_plus_addressing()
    result2 = test_dns_parsing()
    result3 = test_exception_safety()
    
    # Final summary
    print("\n" + "="*70)
    print("FINAL TEST SUMMARY")
    print("="*70)
    print(f"Plus-addressing tests:  {'✓ PASSED' if result1 else '✗ FAILED'}")
    print(f"DNS parsing tests:      {'✓ PASSED' if result2 else '✗ FAILED'}")
    print(f"Exception safety tests: {'✓ PASSED' if result3 else '✗ FAILED'}")
    print("="*70)
    
    if result1 and result2 and result3:
        print("✓ ALL CRITICAL FIXES VERIFIED SUCCESSFULLY!")
    else:
        print("✗ SOME CRITICAL FIXES FAILED VERIFICATION!")
    print("="*70 + "\n")
