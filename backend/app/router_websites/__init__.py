"""Website Builder Router.

Important: this module must avoid importing sub-routers at import time.
Some services import `app.router_websites.dao`, and Python will execute this
`__init__.py` first. If we eagerly import `.router` here, it can create
circular imports (router -> services -> router_websites.dao -> __init__ -> router).
"""

from typing import Any

__all__ = ["router", "public_router"]


def __getattr__(name: str) -> Any:
    # Lazy import to prevent circular imports.
    if name == "router":
        from .router import router as _router

        return _router
    if name == "public_router":
        from .public_router import router as _public_router

        return _public_router

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
