"""
URL validation and security module.
Prevents SSRF attacks, validates URL schemes, and normalizes URLs.
"""
import ipaddress
import socket
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Tuple, Optional


# Allowed URL schemes
ALLOWED_SCHEMES = {'http', 'https'}

# Blocked schemes that could be used for attacks
BLOCKED_SCHEMES = {'file', 'ftp', 'data', 'javascript', 'vbscript', 'about'}

# Tracking parameters to remove during normalization (optional)
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'msclkid', '_ga', 'mc_cid', 'mc_eid'
}


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private, loopback, or link-local.
    
    Args:
        ip_str: IP address as string
        
    Returns:
        True if IP is private/internal, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private or 
            ip.is_loopback or 
            ip.is_link_local or
            ip.is_multicast or
            ip.is_reserved
        )
    except ValueError:
        return False


def validate_url(url: str, check_dns: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate a URL for security and correctness.
    
    Args:
        url: The URL to validate
        check_dns: Whether to perform DNS resolution check (default: True)
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
        
    Security checks:
        - Scheme must be http or https
        - URL must not resolve to private IP addresses (SSRF prevention)
        - Hostname must be valid
    """
    if not url or not isinstance(url, str):
        return False, "URL is required and must be a string"
    
    # Basic length check
    if len(url) > 2048:
        return False, "URL is too long (max 2048 characters)"
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"
    
    # Check scheme
    if not parsed.scheme:
        return False, "URL must include a scheme (http:// or https://)"
    
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Only {', '.join(ALLOWED_SCHEMES)} schemes are allowed"
    
    if parsed.scheme.lower() in BLOCKED_SCHEMES:
        return False, f"Scheme '{parsed.scheme}' is not allowed for security reasons"
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a valid hostname"
    
    # Check if hostname is an IP address
    try:
        # Try to parse as IP address
        ip = ipaddress.ip_address(hostname)
        if is_private_ip(str(ip)):
            return False, "URLs with private IP addresses are not allowed"
    except ValueError:
        # Not an IP address, it's a domain name - this is fine
        pass
    
    # DNS resolution check to prevent SSRF
    if check_dns:
        try:
            # Resolve hostname to IP addresses
            addr_info = socket.getaddrinfo(hostname, None)
            
            # Check all resolved IPs
            for info in addr_info:
                ip_address = info[4][0]
                if is_private_ip(ip_address):
                    return False, f"URL resolves to private IP address ({ip_address})"
        
        except socket.gaierror:
            return False, f"Cannot resolve hostname: {hostname}"
        except Exception as e:
            return False, f"DNS resolution error: {str(e)}"
    
    return True, None


def normalize_url(url: str, remove_tracking: bool = False, remove_fragment: bool = True) -> str:
    """
    Normalize a URL for consistency and deduplication.
    
    Args:
        url: The URL to normalize
        remove_tracking: Whether to remove tracking parameters (default: False)
        remove_fragment: Whether to remove URL fragment (#) (default: True)
        
    Returns:
        Normalized URL string
        
    Normalization steps:
        - Convert scheme and hostname to lowercase
        - Remove default ports (80 for http, 443 for https)
        - Sort query parameters alphabetically
        - Optionally remove tracking parameters
        - Optionally remove fragment
        - Remove trailing slash from path (unless it's the root)
    """
    parsed = urlparse(url.strip())
    
    # Normalize scheme and hostname to lowercase
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove default ports
    if ':80' in netloc and scheme == 'http':
        netloc = netloc.replace(':80', '')
    elif ':443' in netloc and scheme == 'https':
        netloc = netloc.replace(':443', '')
    
    # Parse and sort query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Remove tracking parameters if requested
    if remove_tracking:
        query_params = {k: v for k, v in query_params.items() if k not in TRACKING_PARAMS}
    
    # Sort parameters and rebuild query string
    sorted_query = urlencode(sorted(query_params.items()), doseq=True)
    
    # Handle path
    path = parsed.path
    if path and path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    if not path:
        path = '/'
    
    # Remove fragment if requested
    fragment = '' if remove_fragment else parsed.fragment
    
    # Rebuild URL
    normalized = urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        sorted_query,
        fragment
    ))
    
    return normalized


def get_url_hash(url: str) -> str:
    """
    Generate a hash of a normalized URL for deduplication.
    
    Args:
        url: The URL to hash
        
    Returns:
        SHA-256 hash of the normalized URL
    """
    import hashlib
    normalized = normalize_url(url, remove_tracking=True, remove_fragment=True)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
