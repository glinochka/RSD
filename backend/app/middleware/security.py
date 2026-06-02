"""Security middleware for Website Builder.

Provides CSP headers, security headers, rate limiting, and audit logging.
"""

import hashlib
import json
import time
from functools import wraps
from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.config.website_domains import BASE_DOMAIN

# Redis is optional for rate limiting
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# In-memory rate limit store (fallback when Redis unavailable)
_rate_limit_store: dict[str, dict] = {}


def get_redis_client() -> Optional["redis.Redis"]:
    """Get Redis client if available."""
    if not REDIS_AVAILABLE:
        return None
    try:
        # Try to connect to Redis
        client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=getattr(settings, 'REDIS_DB', 0),
            decode_responses=True,
            socket_connect_timeout=1,
        )
        client.ping()
        return client
    except Exception:
        return None


class CSPMiddleware(BaseHTTPMiddleware):
    """Add Content Security Policy headers to responses.
    
    CSP helps prevent XSS attacks by controlling what resources
    can be loaded and executed on the page.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Only add CSP to website-related endpoints
        path = request.url.path
        if not self._is_website_endpoint(path):
            return response
        
        # Build CSP directive
        # Allow scripts/styles from self and rsd-ai.ru domain
        # Allow images from self, data URIs, and https
        csp_directives = [
            "default-src 'self'",
            f"script-src 'self' 'unsafe-inline' 'unsafe-eval' *.{BASE_DOMAIN} {BASE_DOMAIN}",
            f"style-src 'self' 'unsafe-inline' *.{BASE_DOMAIN} {BASE_DOMAIN} fonts.googleapis.com",
            "img-src 'self' data: https: blob:",
            "font-src 'self' fonts.gstatic.com data:",
            f"connect-src 'self' *.{BASE_DOMAIN} {BASE_DOMAIN}",
            "frame-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "upgrade-insecure-requests",
        ]
        
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Additional security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        return response
    
    def _is_website_endpoint(self, path: str) -> bool:
        """Check if path is a website-related endpoint."""
        website_prefixes = (
            "/api/v1/websites",
            "/public-website",
            "/w/",  # Public website paths
            "/preview/",
        )
        return any(path.startswith(prefix) for prefix in website_prefixes)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for website builder endpoints.
    
    Uses Redis when available, falls back to in-memory storage.
    """
    
    # Rate limit configurations: (requests, window_seconds)
    RATE_LIMITS = {
        "website_generate": (10, 3600),    # 10 per hour
        "website_export": (5, 3600),       # 5 per hour
        "website_publish": (20, 3600),   # 20 per hour
        "website_domain_verify": (10, 300),  # 10 per 5 minutes
    }
    
    def __init__(self, app):
        super().__init__(app)
        self.redis_client = get_redis_client()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if this endpoint needs rate limiting
        rate_limit_key = self._get_rate_limit_key(request)
        
        if rate_limit_key:
            client_id = self._get_client_id(request)
            if not self._check_rate_limit(rate_limit_key, client_id):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "retry_after": self._get_retry_after(rate_limit_key),
                    },
                )
        
        return await call_next(request)
    
    def _get_rate_limit_key(self, request: Request) -> Optional[str]:
        """Determine rate limit key based on endpoint."""
        path = request.url.path
        method = request.method
        
        if method != "POST":
            return None
        
        if "/generate" in path:
            return "website_generate"
        elif "/export" in path:
            return "website_export"
        elif "/publish" in path:
            return "website_publish"
        elif "/verify" in path and "/domains/" in path:
            return "website_domain_verify"
        
        return None
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"
    
    def _check_rate_limit(self, key: str, client_id: str) -> bool:
        """Check if request is within rate limit."""
        limit, window = self.RATE_LIMITS[key]
        full_key = f"rate_limit:{key}:{client_id}"
        now = time.time()
        
        if self.redis_client:
            # Use Redis
            try:
                pipe = self.redis_client.pipeline()
                pipe.zremrangebyscore(full_key, 0, now - window)
                pipe.zcard(full_key)
                pipe.zadd(full_key, {str(now): now})
                pipe.expire(full_key, window)
                _, current_count, _, _ = pipe.execute()
                return current_count < limit
            except Exception:
                # Fall back to memory on Redis error
                pass
        
        # Use in-memory store
        if full_key not in _rate_limit_store:
            _rate_limit_store[full_key] = {"requests": [], "window": window}
        
        store = _rate_limit_store[full_key]
        store["requests"] = [t for t in store["requests"] if now - t < window]
        
        if len(store["requests"]) >= limit:
            return False
        
        store["requests"].append(now)
        return True
    
    def _get_retry_after(self, key: str) -> int:
        """Get retry-after header value."""
        _, window = self.RATE_LIMITS[key]
        return window


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Security audit logging middleware.
    
    Logs suspicious activities and potential security issues.
    """
    
    SUSPICIOUS_PATTERNS = {
        "xss_attempt": [
            "<script",
            "javascript:",
            "onerror=",
            "onload=",
            "onclick=",
            "eval(",
        ],
        "sql_injection": [
            "' OR ",
            "' AND ",
            "; DROP ",
            "UNION SELECT",
            "--",
        ],
        "path_traversal": [
            "../",
            "..\\",
            "%2f..%2f",
            "%5c..%5c",
        ],
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check for suspicious patterns
        suspicious_activity = self._detect_suspicious_activity(request)
        
        if suspicious_activity:
            await self._log_suspicious_activity(request, suspicious_activity)
            
            # Block obviously malicious requests
            if suspicious_activity["severity"] == "high":
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Request blocked due to security policy violation."},
                )
        
        response = await call_next(request)
        
        # Log security-relevant responses
        if response.status_code in (401, 403, 429):
            await self._log_security_event(request, response)
        
        return response
    
    def _detect_suspicious_activity(self, request: Request) -> Optional[dict]:
        """Detect suspicious patterns in request."""
        url = str(request.url)
        body = ""
        
        # Check URL for suspicious patterns
        for pattern_type, patterns in self.SUSPICIOUS_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in url.lower():
                    return {
                        "type": pattern_type,
                        "pattern": pattern,
                        "location": "url",
                        "severity": "high" if pattern_type in ("xss_attempt", "sql_injection") else "medium",
                    }
        
        # Check query parameters
        for key, values in request.query_params.multi_items():
            for pattern_type, patterns in self.SUSPICIOUS_PATTERNS.items():
                for pattern in patterns:
                    if pattern.lower() in str(values).lower():
                        return {
                            "type": pattern_type,
                            "pattern": pattern,
                            "location": "query",
                            "severity": "high" if pattern_type in ("xss_attempt", "sql_injection") else "medium",
                        }
        
        return None
    
    async def _log_suspicious_activity(self, request: Request, activity: dict):
        """Log suspicious activity."""
        from logging import getLogger
        logger = getLogger("security.audit")
        
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        logger.warning(
            "Suspicious activity detected",
            extra={
                "activity_type": activity["type"],
                "pattern": activity["pattern"],
                "location": activity["location"],
                "severity": activity["severity"],
                "client_ip": client_ip,
                "user_agent": user_agent,
                "url": str(request.url),
                "method": request.method,
            }
        )
    
    async def _log_security_event(self, request: Request, response: Response):
        """Log security-relevant response events."""
        from logging import getLogger
        logger = getLogger("security.audit")
        
        client_ip = request.client.host if request.client else "unknown"
        
        logger.info(
            f"Security event: HTTP {response.status_code}",
            extra={
                "status_code": response.status_code,
                "client_ip": client_ip,
                "url": str(request.url),
                "method": request.method,
            }
        )


def require_website_owner(website_id_param: str = "website_id"):
    """Decorator to require website ownership for access.
    
    Usage:
        @router.get("/{website_id}/...")
        @require_website_owner()
        async def endpoint(website_id: int, current_user: User = Depends(...)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract website_id and current_user from kwargs
            website_id = kwargs.get(website_id_param)
            current_user = kwargs.get('current_user') or kwargs.get('user')
            
            if not website_id or not current_user:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required parameters"
                )
            
            # Check ownership via database
            from app.router_websites.dao import WebsiteDAO
            from app.alembic.database import async_session_maker
            
            async with async_session_maker() as session:
                dao = WebsiteDAO(session)
                website = await dao.find_one_by_filter(id=website_id)
                
                if not website:
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Website not found"
                    )
                
                if website.owner_id != current_user.id:
                    from fastapi import HTTPException
                    # Log potential security violation
                    from logging import getLogger
                    logger = getLogger("security.audit")
                    logger.warning(
                        "Ownership check failed",
                        extra={
                            "website_id": website_id,
                            "attempted_user_id": current_user.id,
                            "actual_owner_id": website.owner_id,
                        }
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: not the website owner"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
