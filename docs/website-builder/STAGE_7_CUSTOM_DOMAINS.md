# Stage 7: Custom Domains and Subdomains

## Overview

This document describes the implementation of Stage 7 - custom domain and subdomain support for the Website Builder. This feature allows users to:

1. Access their websites via free subdomains: `{slug}.rsd-ai.ru`
2. Connect and use their own custom domains (e.g., `example.com`)
3. Verify domain ownership via DNS TXT records
4. Automatic SSL certificate provisioning for custom domains

## Architecture

### Routing Methods

The system supports three ways to access a website:

1. **Path-based**: `https://rsd-ai.ru/w/{slug}`
2. **Subdomain-based**: `https://{slug}.rsd-ai.ru`
3. **Custom domain**: `https://example.com`

### Resolution Flow

```
User Request
    ↓
Host Header Check
    ↓
┌─────────────────────┬─────────────────────┬─────────────────────┐
│ System Domain       │ Subdomain Pattern   │ Custom Domain       │
│ (rsd-ai.ru)         │ (*.rsd-ai.ru)       │ (example.com)       │
└─────────────────────┴─────────────────────┴─────────────────────┘
    ↓                       ↓                       ↓
Main Application      Extract slug from         Query WebsiteDomain
                       subdomain                table for verified
                                                domain record
    ↓                       ↓                       ↓
                    Load website by            Load website by
                    slug from Website          website_id from
                                               domain record
```

## Backend Implementation

### API Endpoints

#### Domain Management (Authenticated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/websites/{id}/domains` | List all domains for a website |
| POST | `/api/v1/websites/{id}/domains` | Add a custom domain |
| DELETE | `/api/v1/websites/{id}/domains/{domain_id}` | Remove a custom domain |
| POST | `/api/v1/websites/{id}/domains/{domain_id}/verify` | Verify domain via DNS TXT |

#### Public Access (Unauthenticated)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/websites/by-slug/{slug}/schema` | Get website by slug |
| GET | `/api/v1/websites/by-domain/{domain}/schema` | Get website by custom domain |
| GET | `/public-website/schema` | Get website by Host header |

### Models

#### WebsiteDomain

```python
class WebsiteDomain(Base):
    id: int
    website_id: int (FK -> Website)
    domain: str (unique)
    ssl_enabled: bool
    verification_status: str (pending | verified | failed)
    verification_token: str
    verified_at: datetime
    dns_check_error: str
    created_at: datetime
    updated_at: datetime
```

### Utilities

#### DNS Verification

The `verify_dns_txt_record()` function in `router_websites/utils.py` performs DNS lookups to verify domain ownership:

```python
def verify_dns_txt_record(domain: str, expected_token: str) -> tuple[bool, str | None]:
    """Verify DNS TXT record for domain ownership."""
    # Uses dnspython to query TXT records
    # Returns (is_verified, error_message)
```

#### Host Header Detection

```python
def extract_website_slug_from_host(host: str, base_domain: str) -> Optional[str]:
    """Extract website slug from subdomain."""
    # mysite.rsd-ai.ru -> mysite

def is_system_domain(host: str, system_domains: set[str]) -> bool:
    """Check if host is a reserved system domain."""
    # api.rsd-ai.ru -> True
    # mysite.rsd-ai.ru -> False
```

## Frontend Implementation

### Domain Manager Panel

The `DomainManagerPanel` component provides:
- Add custom domain form
- DNS TXT record instructions
- Verify domain button
- Remove domain functionality
- Subdomain URL display

### useWebsite Hook

Extended to support domain-based loading:

```javascript
// Load by slug
const { schema } = useWebsite(null, 'my-site');

// Load by custom domain
const { schema } = useWebsite(null, null, 'example.com');

// Auto-detect from window.location
const { schema, detectedDomain } = useWebsiteByCurrentDomain();
```

## Nginx Configuration

### Required DNS Setup

1. **Wildcard DNS**: `*.rsd-ai.ru` -> Server IP
2. **Custom domains**: Point user's domain A/AAAA records to server IP

### Nginx Server Blocks

#### Wildcard Subdomain Server

```nginx
server {
    listen 443 ssl http2;
    server_name *.rsd-ai.ru;

    # Wildcard SSL certificate
    ssl_certificate /etc/letsencrypt/live/rsd-ai.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rsd-ai.ru/privkey.pem;

    # Pass to backend with Host header
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Custom Domain Server (Catch-all)

```nginx
server {
    listen 443 ssl http2 default_server;
    server_name _;

    # Fallback certificate (will be replaced by certbot for specific domains)
    ssl_certificate /etc/letsencrypt/live/rsd-ai.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rsd-ai.ru/privkey.pem;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Website-Host $host;
    }
}
```

## SSL/TLS Certificates

### Wildcard Certificate (for *.rsd-ai.ru)

```bash
# Obtain via Let's Encrypt
sudo certbot certonly --dns-route53 -d rsd-ai.ru -d *.rsd-ai.ru

# Or using DNS challenge
sudo certbot certonly --manual --preferred-challenges dns \
    -d rsd-ai.ru -d *.rsd-ai.ru
```

### Custom Domain Certificates

```bash
# Auto-generated by Certbot when adding domain
sudo certbot --nginx -d example.com -d www.example.com

# Or use the management script
python deployment/scripts/manage-custom-domain.py add example.com <website_id>
sudo certbot --nginx -d example.com
```

## Domain Verification Process

1. **User adds domain** via UI or API
2. **System generates verification token**:
   ```
   TXT record name: @ (or subdomain)
   TXT record value: rsd-verification=<random-token>
   ```
3. **User configures DNS** TXT record at their DNS provider
4. **User clicks "Verify"** or system runs periodic check
5. **System queries DNS** for TXT records using dnspython
6. **If token matches**, domain is marked as verified
7. **SSL certificate** is obtained via Certbot
8. **Nginx config** is generated and reloaded
9. **Website is accessible** at custom domain

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBSITE_BASE_DOMAIN` | rsd-ai.ru | Base domain for subdomains |
| `WILDCARD_SSL_CERT_PATH` | /etc/letsencrypt/live/rsd-ai.ru/fullchain.pem | Wildcard cert path |
| `WILDCARD_SSL_KEY_PATH` | /etc/letsencrypt/live/rsd-ai.ru/privkey.pem | Wildcard key path |
| `ENABLE_CUSTOM_DOMAINS` | true | Enable custom domain feature |
| `ENABLE_SUBDOMAIN_ROUTING` | true | Enable subdomain routing |
| `DNS_VERIFICATION_TIMEOUT` | 30 | DNS lookup timeout (seconds) |

## Deployment Checklist

### Pre-deployment

- [ ] DNS wildcard record configured: `*.rsd-ai.ru -> Server IP`
- [ ] Wildcard SSL certificate obtained
- [ ] Nginx config deployed and tested
- [ ] Environment variables configured

### Testing

- [ ] Access via slug path works: `/w/mysite`
- [ ] Access via subdomain works: `mysite.rsd-ai.ru`
- [ ] Access via custom domain works (after verification)
- [ ] DNS verification works correctly
- [ ] SSL certificates auto-renew

### Security

- [ ] Reserved subdomains blocked (www, api, admin, etc.)
- [ ] DNS verification tokens are cryptographically random
- [ ] Rate limiting enabled for public endpoints
- [ ] HTTP → HTTPS redirects enabled

## Troubleshooting

### Domain not resolving

1. Check DNS records: `dig +short mysite.rsd-ai.ru`
2. Verify wildcard DNS: `dig +short *.rsd-ai.ru`
3. Check Nginx server block configuration

### SSL certificate errors

1. Verify certbot renewal: `sudo certbot renew --dry-run`
2. Check certificate paths in Nginx config
3. Ensure firewall allows 443/tcp

### DNS verification failing

1. Check TXT record: `dig +short TXT example.com`
2. Verify token matches expected value
3. Wait for DNS propagation (up to 24 hours)
4. Check `dns_check_error` field in database

## API Usage Examples

### Add a custom domain

```bash
curl -X POST https://rsd-ai.ru/api/v1/websites/123/domains \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com"}'
```

Response:
```json
{
  "domain": "example.com",
  "verification_token": "rsd-verification=abc123...",
  "verification_status": "pending",
  "dns_record_name": "@",
  "dns_record_value": "rsd-verification=abc123...",
  "instructions": "Add a TXT record to your DNS..."
}
```

### Verify domain

```bash
curl -X POST https://rsd-ai.ru/api/v1/websites/123/domains/456/verify \
  -H "Authorization: Bearer <token>"
```

### Access website by domain

```bash
curl https://rsd-ai.ru/api/v1/websites/by-domain/example.com/schema

# Or with Host header
curl -H "Host: example.com" https://rsd-ai.ru/public-website/schema
```

## Related Files

- Backend:
  - `backend/app/router_websites/router.py` - API endpoints
  - `backend/app/router_websites/utils.py` - Domain validation & DNS verification
  - `backend/app/router_websites/public_router.py` - Public domain-based access
  - `backend/app/router_websites/dao.py` - Data access layer
  - `backend/app/config/website_domains.py` - Configuration

- Frontend:
  - `frontend/src/website-builder/components/constructor/DomainManagerPanel.jsx`
  - `frontend/src/website-builder/hooks/useWebsite.js`
  - `frontend/src/website-builder/pages/WebsitePublicPage.jsx`

- Deployment:
  - `deployment/nginx/website-builder-domains.conf`
  - `deployment/nginx/snippets/website-builder-common.conf`
  - `deployment/scripts/manage-custom-domain.py`