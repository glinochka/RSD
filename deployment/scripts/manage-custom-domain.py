#!/usr/bin/env python3
"""
Script to manage custom domains for Website Builder (Stage 7).

Usage:
    python manage-custom-domain.py add example.com <website_id>
    python manage-custom-domain.py remove example.com
    python manage-custom-domain.py verify example.com
    python manage-custom-domain.py list
    python manage-custom-domain.py generate-nginx

This script:
1. Generates Nginx configuration for custom domains
2. Obtains SSL certificates via Certbot
3. Reloads Nginx to apply changes
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Configuration
NGINX_SITES_DIR = "/etc/nginx/sites-available"
NGINX_ENABLED_DIR = "/etc/nginx/sites-enabled"
DOMAIN_DB_FILE = "/var/lib/website-builder/domains.json"
BACKEND_UPSTREAM = "backend"


def ensure_domain_db():
    """Ensure domain database file exists."""
    db_path = Path(DOMAIN_DB_FILE)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db_path.write_text(json.dumps({"domains": {}}, indent=2))


def load_domain_db() -> dict:
    """Load domain database."""
    ensure_domain_db()
    return json.loads(Path(DOMAIN_DB_FILE).read_text())


def save_domain_db(data: dict):
    """Save domain database."""
    Path(DOMAIN_DB_FILE).write_text(json.dumps(data, indent=2))


def generate_nginx_config(domain: str, website_id: int) -> str:
    """Generate Nginx server block for a custom domain."""
    return f"""# Auto-generated configuration for {domain}
# Website ID: {website_id}

server {{
    listen 80;
    listen [::]:80;
    server_name {domain} www.{domain};

    # ACME challenge for Let's Encrypt
    location /.well-known/acme-challenge/ {{
        root /var/www/certbot;
    }}

    # Redirect HTTP to HTTPS
    location / {{
        return 301 https://$host$request_uri;
    }}
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain} www.{domain};

    # SSL certificates (will be updated by certbot)
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

    # Include common website builder configuration
    include /etc/nginx/snippets/website-builder-common.conf;

    # Custom domain marker for backend
    add_header X-Custom-Domain "{domain}" always;
}}
"""


def add_domain(domain: str, website_id: int):
    """Add a custom domain."""
    db = load_domain_db()

    if domain in db["domains"]:
        print(f"Domain {domain} already exists for website {db['domains'][domain]['website_id']}")
        return 1

    # Validate domain format
    if not domain.replace('.', '').replace('-', '').isalnum():
        print(f"Invalid domain format: {domain}")
        return 1

    db["domains"][domain] = {
        "website_id": website_id,
        "status": "pending",
        "created_at": str(subprocess.check_output(["date", "-Iseconds"]).decode().strip()),
    }
    save_domain_db(db)

    # Generate Nginx config
    config = generate_nginx_config(domain, website_id)
    config_path = Path(NGINX_SITES_DIR) / f"website-builder-{domain}.conf"

    # Write config (requires sudo)
    try:
        subprocess.run(
            ["sudo", "tee", str(config_path)],
            input=config.encode(),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to write Nginx config: {e}")
        return 1

    # Enable site
    enabled_link = Path(NGINX_ENABLED_DIR) / f"website-builder-{domain}.conf"
    try:
        subprocess.run(
            ["sudo", "ln", "-sf", str(config_path), str(enabled_link)],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to enable site: {e}")
        return 1

    # Test Nginx config
    try:
        subprocess.run(["sudo", "nginx", "-t"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Nginx configuration test failed: {e}")
        # Remove the bad config
        subprocess.run(["sudo", "rm", str(config_path), str(enabled_link)], check=False)
        return 1

    # Reload Nginx
    try:
        subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to reload Nginx: {e}")
        return 1

    print(f"Domain {domain} added successfully for website {website_id}")
    print(f"Next steps:")
    print(f"  1. Run: sudo certbot --nginx -d {domain} -d www.{domain}")
    print(f"  2. Update DNS to point to this server")
    print(f"  3. The website will be accessible at https://{domain}")

    return 0


def remove_domain(domain: str):
    """Remove a custom domain."""
    db = load_domain_db()

    if domain not in db["domains"]:
        print(f"Domain {domain} not found")
        return 1

    # Remove Nginx config
    config_path = Path(NGINX_SITES_DIR) / f"website-builder-{domain}.conf"
    enabled_link = Path(NGINX_ENABLED_DIR) / f"website-builder-{domain}.conf"

    for path in [config_path, enabled_link]:
        try:
            subprocess.run(["sudo", "rm", "-f", str(path)], check=True)
        except subprocess.CalledProcessError:
            pass

    # Remove from database
    del db["domains"][domain]
    save_domain_db(db)

    # Reload Nginx
    try:
        subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to reload Nginx: {e}")

    print(f"Domain {domain} removed successfully")
    return 0


def list_domains():
    """List all custom domains."""
    db = load_domain_db()

    if not db["domains"]:
        print("No custom domains configured")
        return 0

    print(f"{'Domain':<30} {'Website ID':<12} {'Status':<12}")
    print("-" * 60)
    for domain, info in db["domains"].items():
        print(f"{domain:<30} {info['website_id']:<12} {info['status']:<12}")

    return 0


def verify_domain(domain: str):
    """Verify domain DNS and SSL status."""
    import socket
    import ssl
    import dns.resolver

    print(f"Verifying domain: {domain}")
    print("-" * 40)

    # DNS check
    try:
        answers = dns.resolver.resolve(domain, 'A')
        for rdata in answers:
            print(f"DNS A record: {rdata}")
    except Exception as e:
        print(f"DNS A record: FAILED ({e})")

    # SSL check
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                print(f"SSL Certificate: Valid (expires {cert.get('notAfter')})")
    except Exception as e:
        print(f"SSL Certificate: FAILED ({e})")

    # HTTP check
    try:
        import urllib.request
        response = urllib.request.urlopen(f"https://{domain}/health", timeout=10)
        print(f"HTTP Response: {response.status}")
    except Exception as e:
        print(f"HTTP Response: FAILED ({e})")

    return 0


def generate_all_nginx():
    """Regenerate all Nginx configs from database."""
    db = load_domain_db()

    for domain, info in db["domains"].items():
        config = generate_nginx_config(domain, info["website_id"])
        config_path = Path(NGINX_SITES_DIR) / f"website-builder-{domain}.conf"

        try:
            subprocess.run(
                ["sudo", "tee", str(config_path)],
                input=config.encode(),
                check=True,
                capture_output=True,
            )
            print(f"Generated config for {domain}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate config for {domain}: {e}")

    # Test and reload Nginx
    try:
        subprocess.run(["sudo", "nginx", "-t"], check=True)
        subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
        print("Nginx reloaded successfully")
    except subprocess.CalledProcessError as e:
        print(f"Nginx reload failed: {e}")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description="Manage custom domains for Website Builder")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a custom domain")
    add_parser.add_argument("domain", help="Domain name (e.g., example.com)")
    add_parser.add_argument("website_id", type=int, help="Website ID to link")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a custom domain")
    remove_parser.add_argument("domain", help="Domain name")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify domain configuration")
    verify_parser.add_argument("domain", help="Domain name")

    # List command
    subparsers.add_parser("list", help="List all custom domains")

    # Generate command
    subparsers.add_parser("generate-nginx", help="Regenerate all Nginx configs")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "add":
        return add_domain(args.domain, args.website_id)
    elif args.command == "remove":
        return remove_domain(args.domain)
    elif args.command == "verify":
        return verify_domain(args.domain)
    elif args.command == "list":
        return list_domains()
    elif args.command == "generate-nginx":
        return generate_all_nginx()

    return 0


if __name__ == "__main__":
    sys.exit(main())