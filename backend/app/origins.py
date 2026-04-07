"""
CORS allowed origins for the FastAPI app.
Must include the origin (scheme + host + port) the frontend is served from,
so the browser allows API requests (backend runs on port 8000; frontend port here).
"""

import socket

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


origins = _get_origins_from_env() or _get_default_dev_origins()
