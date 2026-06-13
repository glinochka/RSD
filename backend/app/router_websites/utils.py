"""Utilities for Website Builder: slug generation, domain validation, etc."""
import re
import secrets
import unicodedata
import dns.resolver
import dns.exception
from typing import Optional

# Reserved slugs that cannot be used
RESERVED_SLUGS = {
    # System paths
    "api", "admin", "administrator", "auth", "login", "logout", "callback",
    "oauth", "webhook", "hooks", "health", "ping", "status", "metrics",
    # Common reserved words
    "www", "mail", "ftp", "smtp", "pop", "imap", "ns", "ns1", "ns2",
    "cdn", "static", "assets", "img", "images", "css", "js", "scripts",
    "app", "application", "dashboard", "panel", "control", "manage",
    # Search engines / SEO
    "sitemap", "robots", "favicon", "apple-touch", "crossdomain",
    # Common terms
    "new", "edit", "delete", "create", "update", "remove", "list", "show",
    "index", "home", "main", "default", "root", "null", "none", "nil",
    "true", "false", "yes", "no", "on", "off", "enable", "disable",
    "test", "demo", "example", "sample", "tmp", "temp", "cache",
}

# Reserved domain subdomains/prefixes
RESERVED_SUBDOMAINS = {
    "www", "mail", "ftp", "smtp", "pop", "imap", "ns", "ns1", "ns2",
    "cdn", "api", "admin", "app", "staging", "dev", "test", "demo",
}

# Valid slug pattern
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Valid domain pattern (simplified, allows internationalized domains via punycode)
DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
)


def normalize_string_for_slug(value: str) -> str:
    """Normalize a string for use in a slug.

    - Transliterate cyrillic and other non-ASCII characters
    - Remove accents
    - Convert to lowercase
    - Replace spaces and special chars with hyphens
    - Collapse multiple hyphens
    """
    if not value:
        return ""

    # Normalize unicode (NFD decomposition to remove accents)
    value = unicodedata.normalize('NFD', value)
    value = ''.join(c for c in value if unicodedata.category(c) != 'Mn')

    # Basic cyrillic transliteration
    transliteration_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    }

    result = []
    for char in value:
        if char in transliteration_map:
            result.append(transliteration_map[char])
        elif char.isalnum():
            result.append(char)
        else:
            result.append('-')

    return ''.join(result)


def generate_slug_from_name(name: str, existing_slugs: set[str] | None = None) -> str:
    """Generate a URL-friendly slug from a name.

    Args:
        name: The business/agent name to generate slug from
        existing_slugs: Set of already taken slugs to avoid collision

    Returns:
        A unique slug string
    """
    if not name:
        raise ValueError("Name cannot be empty")

    # Normalize the name
    base_slug = normalize_string_for_slug(name).lower()

    # Clean up: remove non-alphanumeric except hyphens
    base_slug = re.sub(r'[^a-z0-9-]+', '-', base_slug)
    base_slug = re.sub(r'-+', '-', base_slug)  # collapse multiple hyphens
    base_slug = base_slug.strip('-')

    # Ensure minimum length
    if len(base_slug) < 3:
        # Pad with random chars if too short
        base_slug = f"{base_slug}-{secrets.token_hex(4)}"

    # Truncate if too long
    if len(base_slug) > 50:
        base_slug = base_slug[:50].rsplit('-', 1)[0]  # cut at word boundary

    slug = base_slug
    counter = 1

    # Check against reserved slugs and existing slugs
    existing = existing_slugs or set()

    while slug in RESERVED_SLUGS or slug in existing or len(slug) < 3:
        suffix = f"-{counter}"
        slug = f"{base_slug[:50 - len(suffix)]}{suffix}"
        counter += 1

        if counter > 1000:
            # Fallback to random suffix
            slug = f"{base_slug[:40]}-{secrets.token_hex(4)}"
            break

    return slug


def is_valid_slug(slug: str) -> bool:
    """Check if a slug is valid (format only, not checking uniqueness or reserved)."""
    if not slug or len(slug) < 3 or len(slug) > 50:
        return False

    if not SLUG_PATTERN.match(slug):
        return False

    # Additional checks
    if slug.startswith('-') or slug.endswith('-'):
        return False

    if '--' in slug:
        return False

    return True


def validate_slug(slug: str) -> tuple[bool, str]:
    """Validate a slug and return (is_valid, error_message)."""
    if not slug:
        return False, "Slug is required"

    if len(slug) < 3:
        return False, "Slug must be at least 3 characters"

    if len(slug) > 50:
        return False, "Slug must be at most 50 characters"

    if slug in RESERVED_SLUGS:
        return False, f"Slug '{slug}' is reserved and cannot be used"

    if not SLUG_PATTERN.match(slug):
        return False, "Slug can only contain lowercase letters, numbers, and hyphens"

    if slug.startswith('-') or slug.endswith('-'):
        return False, "Slug cannot start or end with a hyphen"

    if '--' in slug:
        return False, "Slug cannot contain consecutive hyphens"

    return True, ""


def is_valid_domain(domain: str) -> bool:
    """Check if a domain string looks valid (format only)."""
    if not domain or len(domain) > 253:
        return False

    domain = domain.lower().strip()

    # Check pattern
    if not DOMAIN_PATTERN.match(domain):
        return False

    # Check individual labels
    labels = domain.split('.')
    for label in labels:
        if len(label) > 63:
            return False
        if not label or label.startswith('-') or label.endswith('-'):
            return False

    # Check reserved subdomains
    if labels[0] in RESERVED_SUBDOMAINS:
        return False

    # Must have at least one dot (not just a TLD)
    if len(labels) < 2:
        return False

    return True


def validate_domain(domain: str) -> tuple[bool, str]:
    """Validate a custom domain and return (is_valid, error_message)."""
    if not domain:
        return False, "Domain is required"

    domain = domain.lower().strip()

    if len(domain) > 253:
        return False, "Domain is too long (max 253 characters)"

    # Check for protocol prefix
    if domain.startswith(('http://', 'https://', '//')):
        return False, "Domain should not include protocol (http:// or https://)"

    # Check for path
    if '/' in domain:
        return False, "Domain should not include path"

    # Check for port
    if ':' in domain:
        return False, "Domain should not include port number"

    if not DOMAIN_PATTERN.match(domain):
        return False, "Invalid domain format"

    # Check individual labels
    labels = domain.split('.')

    for label in labels:
        if len(label) > 63:
            return False, "Domain label too long (max 63 characters per label)"
        if not label:
            return False, "Empty domain label"
        if label.startswith('-') or label.endswith('-'):
            return False, "Domain labels cannot start or end with hyphens"

    # Must have at least one dot (not just a TLD)
    if len(labels) < 2:
        return False, "Domain must include at least one dot (e.g., example.com)"

    # Check reserved subdomains
    if labels[0] in RESERVED_SUBDOMAINS:
        return False, f"Subdomain '{labels[0]}' is reserved"

    # Check for numeric-only TLD
    if labels[-1].isdigit():
        return False, "Invalid TLD"

    return True, ""


def generate_verification_token() -> str:
    """Generate a unique verification token for domain TXT record."""
    return f"rsd-verification={secrets.token_urlsafe(32)}"


def generate_dns_verification_record(domain: str, token: str) -> tuple[str, str]:
    """Generate the DNS TXT record details for domain verification.

    Returns:
        Tuple of (record_name, record_value)
    """
    # For root domain, use @ or domain itself
    # For subdomain, use the subdomain
    record_name = "@" if not domain.startswith('*') else domain
    record_value = token if token.startswith('rsd-verification=') else f"rsd-verification={token}"

    return record_name, record_value


def verify_dns_txt_record(domain: str, expected_token: str) -> tuple[bool, str | None]:
    """Verify DNS TXT record for domain verification.

    Args:
        domain: The domain to verify
        expected_token: The expected TXT record value (with or without rsd-verification= prefix)

    Returns:
        Tuple of (is_verified, error_message)
    """
    # Normalize expected token
    expected_value = expected_token
    if not expected_value.startswith('rsd-verification='):
        expected_value = f"rsd-verification={expected_value}"

    try:
        # Query TXT records for the domain
        answers = dns.resolver.resolve(domain, 'TXT')

        for rdata in answers:
            for txt_string in rdata.strings:
                try:
                    txt_value = txt_string.decode('utf-8') if isinstance(txt_string, bytes) else txt_string
                    if txt_value == expected_value:
                        return True, None
                except (UnicodeDecodeError, AttributeError):
                    continue

        return False, "TXT record not found or value does not match"

    except dns.resolver.NXDOMAIN:
        return False, "Domain does not exist (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        return False, "No TXT records found for domain"
    except dns.resolver.Timeout:
        return False, "DNS lookup timed out"
    except dns.exception.DNSException as e:
        return False, f"DNS lookup error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during DNS lookup: {str(e)}"


def is_system_domain(host: str, system_domains: set[str]) -> bool:
    """Check if host is a system domain (not a custom website domain).

    Args:
        host: The Host header value
        system_domains: Set of system domains (e.g., {'rsd-ai.ru', 'api.rsd-ai.ru'})

    Returns:
        True if host is a system domain
    """
    host_lower = host.lower().strip()

    # Remove port if present
    if ':' in host_lower:
        host_lower = host_lower.split(':')[0]

    # Check exact match
    if host_lower in system_domains:
        return True

    # Check if it's a subdomain of any system domain
    for system_domain in system_domains:
        if host_lower == system_domain:
            return True
        if host_lower.endswith(f".{system_domain}"):
            # It's a subdomain like www.rsd-ai.ru or api.rsd-ai.ru
            subdomain = host_lower[:-len(system_domain) - 1]
            # If subdomain is in reserved list, it's a system domain
            if subdomain in RESERVED_SUBDOMAINS:
                return True

    return False


def extract_website_slug_from_host(host: str, base_domain: str) -> Optional[str]:
    """Extract website slug from Host header for subdomain-based routing.

    Example: mysite.rsd-ai.ru -> mysite

    Args:
        host: The Host header value
        base_domain: The base domain (e.g., 'rsd-ai.ru')

    Returns:
        Website slug if it matches pattern, None otherwise
    """
    host_lower = host.lower().strip()

    # Remove port if present
    if ':' in host_lower:
        host_lower = host_lower.split(':')[0]

    base_lower = base_domain.lower().strip()

    # Check if host ends with .{base_domain}
    suffix = f".{base_lower}"
    if host_lower.endswith(suffix):
        slug = host_lower[:-len(suffix)]

        # Validate that slug is valid format
        if slug and is_valid_slug(slug):
            return slug

    return None
