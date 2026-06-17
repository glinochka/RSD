"""Cleanup helpers for AI-generated landing HTML."""

from __future__ import annotations

import re

# Decorative chat FABs / bubbles that duplicate the platform widget.
_CHAT_CLASS_PATTERN = re.compile(
    r"\b(?:chat-widget|chat-bubble|live-chat|messenger-widget|floating-chat|"
    r"chat-button|online-chat|support-chat|chat-fab|chat-icon-btn)\b",
    re.IGNORECASE,
)

_CHAT_LABEL_PATTERN = re.compile(
    r"(?:чат|chat|написать\s+нам|online\s*chat|live\s*chat|open\s*chat|"
    r"задать\s+вопрос|онлайн[-\s]?консультант)",
    re.IGNORECASE,
)

_FIXED_CORNER_PATTERN = re.compile(
    r"\b(?:fixed|sticky)\b.*\b(?:bottom-|right-|z-\[?\d{2,})",
    re.IGNORECASE,
)


def _tag_attr_blob(tag_html: str) -> str:
    return tag_html.lower()


def _looks_like_decorative_chat(tag_html: str) -> bool:
    blob = _tag_attr_blob(tag_html)
    if _CHAT_CLASS_PATTERN.search(blob):
        return True
    if re.search(r'\b(?:id|class|aria-label|title)=["\'][^"\']*', blob):
        for attr in ("aria-label", "title", "id", "class"):
            match = re.search(rf'{attr}=["\']([^"\']+)["\']', blob, re.IGNORECASE)
            if match and _CHAT_LABEL_PATTERN.search(match.group(1)):
                if _FIXED_CORNER_PATTERN.search(blob) or "rounded-full" in blob:
                    return True
    if _CHAT_LABEL_PATTERN.search(blob) and "rounded-full" in blob and _FIXED_CORNER_PATTERN.search(blob):
        return True
    return False


def _remove_matching_tags(html: str, predicate) -> str:
    """Remove outermost tags matching predicate(opening_tag_html)."""
    result = html
    pattern = re.compile(
        r"<(button|a|div|span)\b([^>]*)>",
        re.IGNORECASE,
    )
    changed = True
    while changed:
        changed = False
        for match in pattern.finditer(result):
            opening = match.group(0)
            if not predicate(opening):
                continue
            tag = match.group(1).lower()
            start = match.start()
            # Self-closing or find closing tag (shallow — decorative widgets are small)
            close = re.search(
                rf"</{tag}\s*>",
                result[match.end() : match.end() + 4000],
                re.IGNORECASE,
            )
            if close:
                end = match.end() + close.end()
                result = result[:start] + result[end:]
                changed = True
                break
    return result


def strip_decorative_chat_widgets(html: str) -> str:
    """Remove fake chat buttons/bubbles; the platform injects a working widget."""
    if not html:
        return html
    cleaned = _remove_matching_tags(html, _looks_like_decorative_chat)
    # Remove empty fixed-position wrappers left behind
    cleaned = re.sub(
        r'<div\b[^>]*class="[^"]*\bfixed\b[^"]*\b(?:bottom-|right-)[^"]*"[^>]*>\s*</div>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned
