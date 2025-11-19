"""
Quick security tests to verify Task 1 implementation.
Run with: python test_security.py
"""
import sys

def test_secure_slug_generation():
    """Test that slug generation uses secure random."""
    from hashing import generate_secure_slug
    
    # Generate multiple slugs
    slugs = [generate_secure_slug() for _ in range(100)]
    
    # Check they're all different (no collisions in 100 attempts)
    assert len(set(slugs)) == 100, "Slugs should be unique"
    
    # Check length
    assert all(len(s) == 7 for s in slugs), "Default slug length should be 7"
    
    # Check characters are alphanumeric
    import string
    allowed = set(string.ascii_letters + string.digits)
    assert all(all(c in allowed for c in s) for s in slugs), "Slugs should be alphanumeric"
    
    print("✓ Secure slug generation works correctly")


def test_ssrf_prevention():
    """Test that SSRF prevention blocks private IPs."""
    from url_validator import validate_url, is_private_ip
    
    # Test private IP detection
    assert is_private_ip("192.168.1.1") == True, "Should detect private IP"
    assert is_private_ip("10.0.0.1") == True, "Should detect private IP"
    assert is_private_ip("127.0.0.1") == True, "Should detect loopback"
    assert is_private_ip("169.254.1.1") == True, "Should detect link-local"
    assert is_private_ip("8.8.8.8") == False, "Should allow public IP"
    
    # Test URL validation (without DNS check for speed)
    valid, msg = validate_url("https://example.com", check_dns=False)
    assert valid == True, "Should allow valid URL"
    
    valid, msg = validate_url("http://192.168.1.1", check_dns=False)
    assert valid == False, "Should block private IP URL"
    assert "private" in msg.lower(), "Error message should mention private IP"
    
    valid, msg = validate_url("file:///etc/passwd", check_dns=False)
    assert valid == False, "Should block file:// scheme"
    
    valid, msg = validate_url("javascript:alert(1)", check_dns=False)
    assert valid == False, "Should block javascript: scheme"
    
    print("✓ SSRF prevention works correctly")


def test_url_normalization():
    """Test URL normalization for deduplication."""
    from url_validator import normalize_url
    
    # Test scheme normalization
    url1 = normalize_url("HTTP://EXAMPLE.COM/path")
    url2 = normalize_url("http://example.com/path")
    assert url1 == url2, "Should normalize scheme and hostname to lowercase"
    
    # Test default port removal
    url1 = normalize_url("http://example.com:80/path")
    url2 = normalize_url("http://example.com/path")
    assert url1 == url2, "Should remove default port 80"
    
    url1 = normalize_url("https://example.com:443/path")
    url2 = normalize_url("https://example.com/path")
    assert url1 == url2, "Should remove default port 443"
    
    # Test query parameter sorting
    url1 = normalize_url("http://example.com?b=2&a=1")
    url2 = normalize_url("http://example.com?a=1&b=2")
    assert url1 == url2, "Should sort query parameters"
    
    print("✓ URL normalization works correctly")


def test_input_validation():
    """Test Pydantic schema validation."""
    from schemas import URLCreate
    from pydantic import ValidationError
    
    # Valid input
    try:
        data = URLCreate(target_url="https://example.com")
        assert data.target_url == "https://example.com"
        print("✓ Valid URL accepted")
    except ValidationError as e:
        print(f"✗ Valid URL rejected: {e}")
        sys.exit(1)
    
    # Invalid custom slug
    try:
        data = URLCreate(target_url="https://example.com", custom_slug="ab")
        print("✗ Short slug should be rejected")
        sys.exit(1)
    except ValidationError:
        print("✓ Short slug rejected correctly")
    
    # Invalid custom slug with special chars
    try:
        data = URLCreate(target_url="https://example.com", custom_slug="test@123")
        print("✗ Slug with special chars should be rejected")
        sys.exit(1)
    except ValidationError:
        print("✓ Slug with special chars rejected correctly")
    
    # Reserved slug
    try:
        data = URLCreate(target_url="https://example.com", custom_slug="admin")
        print("✗ Reserved slug should be rejected")
        sys.exit(1)
    except ValidationError:
        print("✓ Reserved slug rejected correctly")


def test_config_loading():
    """Test configuration loading from environment."""
    from config import settings
    
    # Check that settings loaded
    assert settings.APP_NAME is not None
    assert settings.DATABASE_URL is not None
    assert settings.SECRET_KEY is not None
    
    # Check defaults
    assert settings.DEFAULT_SLUG_LENGTH == 7
    assert settings.MAX_EXPIRATION_DAYS == 365
    
    print("✓ Configuration loading works correctly")


def main():
    """Run all security tests."""
    print("\n🔒 Running Security Tests for Task 1\n")
    print("=" * 50)
    
    try:
        test_secure_slug_generation()
        test_ssrf_prevention()
        test_url_normalization()
        test_input_validation()
        test_config_loading()
        
        print("=" * 50)
        print("\n✅ All security tests passed!\n")
        print("Task 1 (Security Hardening) is complete and verified.")
        print("\nKey improvements:")
        print("  • Cryptographically secure slug generation")
        print("  • SSRF prevention with IP validation")
        print("  • URL normalization for deduplication")
        print("  • Comprehensive input validation")
        print("  • Environment-based configuration")
        print("\nYou can now safely proceed to Task 2.")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
