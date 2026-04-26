"""Kling rendering adapter for content_factory pipeline."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_SUBMIT_CACHE_TTL_SECONDS = 6 * 60 * 60
_SUBMIT_IDEMPOTENCY_CACHE: dict[str, tuple[str, float]] = {}


def _compact_error(value: Any, limit: int = 400) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text


def _cleanup_submit_cache(now_ts: float) -> None:
    stale_keys = [k for k, (_, ts) in _SUBMIT_IDEMPOTENCY_CACHE.items() if now_ts - ts > _SUBMIT_CACHE_TTL_SECONDS]
    for key in stale_keys:
        _SUBMIT_IDEMPOTENCY_CACHE.pop(key, None)


class KlingClient:
    """External adapter for Kling API with retries/backoff/idempotency."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._api_key = (api_key or settings.KLING_API_KEY or "").strip()
        self._base_url = (base_url or settings.KLING_API_BASE_URL or "").strip().rstrip("/")
        self._max_retries = max(1, int(max_retries or settings.KLING_MAX_RETRIES or 3))
        timeout_value = float(timeout_seconds or settings.KLING_TIMEOUT_SECONDS or 30.0)
        self._timeout = httpx.Timeout(timeout_value, connect=min(timeout_value, 10.0))

    async def submit_render(
        self,
        *,
        script_text: str,
        duration_seconds: int,
        model: str = "kling-v1",
        idempotency_key: str | None = None,
    ) -> str:
        """Submit render request and return Kling task id."""
        self._assert_configured()

        normalized_script = str(script_text or "").strip()
        if not normalized_script:
            raise RuntimeError("Kling submit failed: empty script_text")
        duration = max(1, min(int(duration_seconds), 8))
        effective_model = str(model or "kling-v1").strip() or "kling-v1"
        key = self._compute_idempotency_key(
            explicit_key=idempotency_key,
            script_text=normalized_script,
            duration_seconds=duration,
            model=effective_model,
        )
        now_ts = time.time()
        _cleanup_submit_cache(now_ts)
        cached = _SUBMIT_IDEMPOTENCY_CACHE.get(key)
        if cached:
            task_id, _ = cached
            logger.info("Kling submit idempotent replay key=%s task_id=%s", key[:12], task_id)
            return task_id

        payload = {
            "prompt": normalized_script,
            "duration_seconds": duration,
            "model": effective_model,
        }
        headers = self._headers(idempotency_key=key)
        data = await self._request_json("POST", "/v1/videos/generations", json_body=payload, headers=headers)

        task_id = str(data.get("task_id") or data.get("id") or "").strip()
        if not task_id:
            raise RuntimeError("Kling submit failed: response missing task_id")
        _SUBMIT_IDEMPOTENCY_CACHE[key] = (task_id, now_ts)
        logger.info("Kling render submitted task_id=%s model=%s", task_id, effective_model)
        return task_id

    async def poll_render(self, *, task_id: str) -> dict[str, Any]:
        """Poll Kling render status. Returns {status, video_url, error}."""
        self._assert_configured()
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            raise RuntimeError("Kling poll failed: empty task_id")

        data = await self._request_json("GET", f"/v1/videos/generations/{normalized_task_id}")
        raw_status = str(data.get("status") or "").strip().lower()
        video_url = str(data.get("video_url") or data.get("result_url") or "").strip() or None
        error = data.get("error") or data.get("error_message")
        error_text = _compact_error(error) or None

        status = "rendering"
        if raw_status in {"success", "succeeded", "done", "completed", "finished"}:
            status = "rendered"
        elif raw_status in {"failed", "error", "cancelled", "canceled"}:
            status = "failed"
        elif raw_status in {"queued", "pending", "running", "processing", "rendering"}:
            status = "rendering"
        elif video_url:
            status = "rendered"

        logger.info("Kling poll task_id=%s status=%s", normalized_task_id, status)
        return {
            "status": status,
            "video_url": video_url,
            "error": error_text,
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None
        request_headers = headers or self._headers()

        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(method, url, headers=request_headers, json=json_body)
                if response.is_success:
                    if not response.content:
                        return {}
                    payload = response.json()
                    return payload if isinstance(payload, dict) else {"data": payload}

                detail = _compact_error(response.text)
                code = int(response.status_code)
                if self._is_retryable_http_code(code) and attempt < self._max_retries:
                    await self._sleep_with_backoff(attempt)
                    continue
                raise RuntimeError(f"Kling request failed: HTTP {code} {detail}")
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await self._sleep_with_backoff(attempt)
                    continue
                raise RuntimeError("Kling request timeout") from exc
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await self._sleep_with_backoff(attempt)
                    continue
                raise RuntimeError(f"Kling transport error: {_compact_error(exc)}") from exc
            except json.JSONDecodeError as exc:
                raise RuntimeError("Kling response is not valid JSON") from exc

        raise RuntimeError(f"Kling request failed after retries: {_compact_error(last_error)}")

    @staticmethod
    async def _sleep_with_backoff(attempt: int) -> None:
        # 0.5s, 1s, 2s ... capped to 8s.
        delay = min(0.5 * (2 ** max(0, attempt - 1)), 8.0)
        await asyncio.sleep(delay)

    @staticmethod
    def _is_retryable_http_code(code: int) -> bool:
        return code in {408, 409, 425, 429, 500, 502, 503, 504}

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _assert_configured(self) -> None:
        if not self._api_key:
            raise RuntimeError("Kling API key is not configured")
        if not self._base_url:
            raise RuntimeError("Kling API base_url is not configured")

    @staticmethod
    def _compute_idempotency_key(
        *,
        explicit_key: str | None,
        script_text: str,
        duration_seconds: int,
        model: str,
    ) -> str:
        raw = str(explicit_key or "").strip()
        if raw:
            return raw
        payload = f"{model}|{duration_seconds}|{script_text}"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"kling-submit-{digest[:32]}"


_kling_client: KlingClient | None = None


def get_kling_client() -> KlingClient:
    global _kling_client
    if _kling_client is None:
        _kling_client = KlingClient()
    return _kling_client
