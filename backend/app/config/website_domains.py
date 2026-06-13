"""
Configuration for Website Builder Custom Domains (Stage 7).

This module provides settings for custom domain and subdomain support.
"""
import os
from typing import Set

# Base domain for subdomain routing
# Websites will be accessible at {slug}.{BASE_DOMAIN}
BASE_DOMAIN = os.getenv("WEBSITE_BASE_DOMAIN", "rsd-ai.ru")

# System domains that should not be treated as website domains
# These are reserved for platform use
SYSTEM_DOMAINS: Set[str] = {
    BASE_DOMAIN,
    f"www.{BASE_DOMAIN}",
    f"api.{BASE_DOMAIN}",
    f"admin.{BASE_DOMAIN}",
    f"staging.{BASE_DOMAIN}",
    f"dev.{BASE_DOMAIN}",
    f"cdn.{BASE_DOMAIN}",
    f"static.{BASE_DOMAIN}",
    f"app.{BASE_DOMAIN}",
    f"mail.{BASE_DOMAIN}",
    f"ftp.{BASE_DOMAIN}",
}

# Reserved subdomains that cannot be used for websites
RESERVED_SUBDOMAINS: Set[str] = {
    "www", "api", "admin", "staging", "dev", "cdn", "static",
    "app", "mail", "ftp", "smtp", "pop", "imap", "ns", "ns1", "ns2",
    "test", "demo", "old", "new", "beta", "alpha", "prod", "production",
}

# Wildcard SSL certificate paths (for *.BASE_DOMAIN)
WILDCARD_SSL_CERT_PATH = os.getenv(
    "WILDCARD_SSL_CERT_PATH",
    f"/etc/letsencrypt/live/{BASE_DOMAIN}/fullchain.pem"
)
WILDCARD_SSL_KEY_PATH = os.getenv(
    "WILDCARD_SSL_KEY_PATH",
    f"/etc/letsencrypt/live/{BASE_DOMAIN}/privkey.pem"
)

# Custom domain SSL configuration
CUSTOM_DOMAIN_CERT_DIR = os.getenv(
    "CUSTOM_DOMAIN_CERT_DIR",
    "/etc/letsencrypt/live"
)

# Enable/disable custom domain features
ENABLE_CUSTOM_DOMAINS = os.getenv("ENABLE_CUSTOM_DOMAINS", "true").lower() == "true"
ENABLE_SUBDOMAIN_ROUTING = os.getenv("ENABLE_SUBDOMAIN_ROUTING", "true").lower() == "true"

# Rate limiting for public website access
PUBLIC_WEBSITE_RATE_LIMIT_REQUESTS = int(os.getenv("WEBSITE_RATE_LIMIT_REQUESTS", "100"))
PUBLIC_WEBSITE_RATE_LIMIT_WINDOW = int(os.getenv("WEBSITE_RATE_LIMIT_WINDOW", "60"))  # seconds

# DNS verification settings
DNS_VERIFICATION_TIMEOUT = int(os.getenv("DNS_VERIFICATION_TIMEOUT", "30"))  # seconds
DNS_VERIFICATION_RETRIES = int(os.getenv("DNS_VERIFICATION_RETRIES", "3"))


def is_system_domain(host: str) -> bool:
    """Check if a hostname is a system domain."""
    host = host.lower().strip()

    # Remove port if present
    if ":" in host:
        host = host.split(":")[0]

    # Check exact match
    if host in SYSTEM_DOMAINS:
        return True

    # Check reserved subdomains
    for subdomain in RESERVED_SUBDOMAINS:
        if host == f"{subdomain}.{BASE_DOMAIN}":
            return True

    return False


def get_custom_domain_cert_paths(domain: str) -> tuple[str, str]:
    """Get SSL certificate paths for a custom domain.

    Args:
        domain: Custom domain name

    Returns:
        Tuple of (cert_path, key_path)
    """
    cert_path = os.path.join(CUSTOM_DOMAIN_CERT_DIR, domain, "fullchain.pem")
    key_path = os.path.join(CUSTOM_DOMAIN_CERT_DIR, domain, "privkey.pem")
    return cert_path, key_path