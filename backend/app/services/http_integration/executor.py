from __future__ import annotations

import base64
import ipaddress
import json
import logging
import re
import time
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from .errors import HttpIntegrationValidationError

logger = logging.getLogger(__name__)

_PATH_PARAM_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_MAX_JSON_BODY_BYTES = 96_000
_MAX_RESPONSE_BYTES = 384_000


def hostname_is_blocked(hostname: str) -> bool:
    raw = (hostname or "").strip().lower().rstrip(".")
    if not raw:
        return True
    if raw == "localhost" or raw.endswith(".localhost"):
        return True
    if raw.endswith(".local"):
        return True
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_safe_relative_path(path_template: str) -> str:
    pt = (path_template or "").strip()
    if not pt.startswith("/"):
        raise HttpIntegrationValidationError("Integration tool path must start with '/'")
    if "\n" in pt or "\r" in pt:
        raise HttpIntegrationValidationError("Integration tool path contains invalid characters")
    if "://" in pt:
        raise HttpIntegrationValidationError("Integration tool path must not contain '://'")
    if ".." in pt:
        raise HttpIntegrationValidationError("Integration tool path must not contain '..'")
    return pt


def merge_auth_headers(*, auth_cfg: dict[str, Any] | None, base_headers: dict[str, str]) -> dict[str, str]:
    merged = {str(k): str(v) for k, v in (base_headers or {}).items() if k}
    auth = auth_cfg if isinstance(auth_cfg, dict) else {}
    atype = str(auth.get("type") or "none").strip().lower()
    if atype in {"", "none"}:
        return merged
    if atype == "bearer":
        token = str(auth.get("token") or "").strip()
        if not token:
            raise HttpIntegrationValidationError("auth.type=bearer requires token")
        merged["Authorization"] = f"Bearer {token}"
        return merged
    if atype == "header":
        hname = str(auth.get("name") or "").strip()
        if not hname:
            raise HttpIntegrationValidationError("auth.type=header requires name")
        merged[hname] = str(auth.get("value") or "")
        return merged
    if atype == "basic":
        user = str(auth.get("username") or "").strip()
        password = str(auth.get("password") or "").strip()
        if not user:
            raise HttpIntegrationValidationError("auth.type=basic requires username")
        blob = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        merged["Authorization"] = f"Basic {blob}"
        return merged
    raise HttpIntegrationValidationError(f"Unsupported auth.type: {atype}")


def build_url(*, base_url: str, path_template: str, path_args: dict[str, Any]) -> str:
    base = (base_url or "").strip().rstrip("/")
    split_b = urlsplit(base)
    if split_b.scheme not in {"http", "https"}:
        raise HttpIntegrationValidationError("base_url must use http or https")
    host = (split_b.hostname or "").strip().lower()
    if not host or hostname_is_blocked(host):
        raise HttpIntegrationValidationError("Integration base_url host is not allowed")
    pt = assert_safe_relative_path(path_template)

    def _replace(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in path_args:
            raise HttpIntegrationValidationError(f"Missing path parameter '{key}' for integration request")
        raw_val = path_args[key]
        if raw_val is None:
            raise HttpIntegrationValidationError(f"Path parameter '{key}' cannot be null")
        return quote(str(raw_val), safe="")

    rendered = _PATH_PARAM_RE.sub(_replace, pt)
    if _PATH_PARAM_RE.search(rendered):
        raise HttpIntegrationValidationError("Unresolved path parameters in integration path")
    merged_path = (split_b.path or "").rstrip("/") + "/" + rendered.lstrip("/")
    return urlunsplit((split_b.scheme, split_b.netloc, merged_path, "", ""))


def coerce_query_value(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)) or value is None:
        if value is None:
            return ""
        return value
    raise HttpIntegrationValidationError("Query parameters must be scalar values")


def validate_parameters_schema(schema: dict[str, Any]) -> None:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise HttpIntegrationValidationError(
            "Each tool must declare parameters as a JSON Schema object (type: object)"
        )
    props = schema.get("properties")
    if props is not None:
        if not isinstance(props, dict):
            raise HttpIntegrationValidationError("parameters.properties must be an object")
        for pk in props.keys():
            if not isinstance(pk, str) or not pk.strip() or len(pk) > 128:
                raise HttpIntegrationValidationError("parameters.properties has invalid keys")
    req = schema.get("required")
    if isinstance(req, list):
        if not isinstance(props, dict):
            raise HttpIntegrationValidationError(
                "parameters.required requires parameters.properties to be an object mapping fields"
            )
        allow = set(props.keys())
        for item in req:
            k = str(item)
            if k not in allow:
                raise HttpIntegrationValidationError(
                    f"parameters.required mentions unknown property '{k}'"
                )


def assert_args_match_schema(schema: dict[str, Any], args: dict[str, Any]) -> None:
    validate_parameters_schema(schema)
    props = schema.get("properties")
    if isinstance(props, dict) and props:
        unknown = set(args) - set(props)
        if unknown:
            sample = ", ".join(sorted(unknown)[:10])
            raise HttpIntegrationValidationError(f"Unknown tool argument keys: {sample}")
    required = schema.get("required")
    if isinstance(required, list):
        missing = [str(k) for k in required if str(k) not in args]
        if missing:
            raise HttpIntegrationValidationError(f"Missing required tool arguments: {', '.join(missing[:10])}")


def split_path_and_rest(
    *, path_template: str, args: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    keys = set(_PATH_PARAM_RE.findall(path_template))
    path_args: dict[str, Any] = {}
    for k in keys:
        if k not in args:
            raise HttpIntegrationValidationError(f"Missing path argument '{k}'")
        path_args[k] = args[k]
    rest = {k: v for k, v in args.items() if k not in keys}
    return path_args, rest


async def execute_http_tool(
    *,
    base_url: str,
    method: str,
    path_template: str,
    headers: dict[str, str],
    args: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    m = (method or "GET").strip().upper()
    if m not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise HttpIntegrationValidationError(f"Unsupported HTTP method: {method}")

    path_args, rest = split_path_and_rest(path_template=path_template, args=args)
    url = build_url(base_url=base_url, path_template=path_template, path_args=path_args)

    final = urlsplit(url)
    if hostname_is_blocked((final.hostname or "").lower()):
        raise HttpIntegrationValidationError("Request target host is blocked")

    payload: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    if m == "GET":
        params = {}
        for key, value in rest.items():
            params[str(key)] = coerce_query_value(value)
    else:
        payload = dict(rest)

    body: bytes | None = None
    request_headers = dict(headers)
    if payload is not None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(raw) > _MAX_JSON_BODY_BYTES:
            raise HttpIntegrationValidationError("Request JSON body is too large")
        body = raw
        request_headers.setdefault("Content-Type", "application/json")

    timeout = httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.request(
                m,
                url,
                headers=request_headers,
                content=body,
                params=params,
            )
    except httpx.HTTPError as exc:
        logger.info("http_integration request failed: %s", exc.__class__.__name__)
        return {"http_status": None, "ok": False, "error": str(exc)}

    raw_bytes = response.content or b""
    if len(raw_bytes) > _MAX_RESPONSE_BYTES:
        text = raw_bytes[:_MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")
        parsed: Any = {"raw": text, "truncated": True}
    else:
        text = raw_bytes.decode("utf-8", errors="replace").strip()
        parsed = None
        ct = (response.headers.get("content-type") or "").lower()
        if "json" in ct and text:
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = {"raw": text}
        elif text:
            parsed = {"raw": text}
        else:
            parsed = {}

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    return {
        "ok": 200 <= response.status_code < 300,
        "http_status": response.status_code,
        "latency_ms": latency_ms,
        "result": parsed,
    }
