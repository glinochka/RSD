"""
CORS allowed origins for the FastAPI app.
Must include the origin (scheme + host + port) the frontend is served from,
so the browser allows API requests (backend runs on port 8000; frontend port here).

Production: set CORS_ALLOWED_ORIGINS in .env (comma-separated).
If unset in production, defaults are derived from BASE_URL.
"""

import socket
from urllib.parse import urlparse

from .config import settings

# Frontend dev server port — must match frontend (e.g. vite.config.js server.port)
FRONTEND_PORT = 3000
# Optional: Vite default port if frontend is run without custom port
FRONTEND_PORT_ALT = 5173


def get_ip_address():
    """Get this machine's local IP (for LAN access). Tries UDP to 8.8.8.8, then hostname."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)


def _get_origins_from_env() -> list[str]:
    raw_value = settings.CORS_ALLOWED_ORIGINS.strip()
    if not raw_value:
        return []
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def _get_default_dev_origins() -> list[str]:
    ip = get_ip_address()
    return [
        f"http://localhost:{FRONTEND_PORT}",
        f"https://localhost:{FRONTEND_PORT}",
        f"http://127.0.0.1:{FRONTEND_PORT}",
        f"https://127.0.0.1:{FRONTEND_PORT}",
        f"http://{ip}:{FRONTEND_PORT}",
        f"https://{ip}:{FRONTEND_PORT}",
        f"http://localhost:{FRONTEND_PORT_ALT}",
        f"https://localhost:{FRONTEND_PORT_ALT}",
        f"http://127.0.0.1:{FRONTEND_PORT_ALT}",
        f"https://127.0.0.1:{FRONTEND_PORT_ALT}",
        f"http://{ip}:{FRONTEND_PORT_ALT}",
        f"https://{ip}:{FRONTEND_PORT_ALT}",
    ]


def _get_default_production_origins() -> list[str]:
    """Fallback when CORS_ALLOWED_ORIGINS is empty and ENVIRONMENT is production."""
    candidates: list[str] = []
    base_url = (settings.BASE_URL or "").strip().rstrip("/")
    if base_url:
        candidates.append(base_url)
        parsed = urlparse(base_url)
        if parsed.scheme and parsed.netloc:
            host = parsed.netloc
            scheme = parsed.scheme
            if not host.startswith("www."):
                candidates.append(f"{scheme}://www.{host}")
            api_host = host if host.startswith("api.") else f"api.{host}"
            candidates.append(f"{scheme}://{api_host}")
    # Known production hosts (safe fallback if BASE_URL unset)
    candidates.extend(
        [
            "https://rsd-ai.ru",
            "https://www.rsd-ai.ru",
            "https://api.rsd-ai.ru",
        ]
    )
    seen: set[str] = set()
    result: list[str] = []
    for origin in candidates:
        if origin and origin not in seen:
            seen.add(origin)
            result.append(origin)
    return result


def resolve_allowed_origins() -> list[str]:
    from_env = _get_origins_from_env()
    if from_env:
        return from_env
    if settings.ENVIRONMENT == "development":
        return _get_default_dev_origins()
    return _get_default_production_origins()


origins = resolve_allowed_origins()
