"""Base protocol for article platform publishers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PublishResult:
    success: bool
    url: str | None = None
    error: str | None = None
    platform_post_id: str | None = None


class ArticlePublisher(Protocol):
    """Platform publisher interface."""

    async def publish(
        self,
        *,
        title: str,
        html_content: str,
        image_path: str | None = None,
    ) -> PublishResult:
        """Publish an article and return the result."""
        ...
