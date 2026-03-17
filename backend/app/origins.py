"""
CORS allowed origins for the FastAPI app.
Must include the origin (scheme + host + port) the frontend is served from,
so the browser allows API requests (backend runs on port 8000; frontend port here).
"""

import socket

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


_ip = get_ip_address()

origins = [
    f"http://localhost:{FRONTEND_PORT}",
    f"http://127.0.0.1:{FRONTEND_PORT}",
    f"http://{_ip}:{FRONTEND_PORT}",
    f"http://localhost:{FRONTEND_PORT_ALT}",
    f"http://127.0.0.1:{FRONTEND_PORT_ALT}",
    f"http://{_ip}:{FRONTEND_PORT_ALT}",
]
