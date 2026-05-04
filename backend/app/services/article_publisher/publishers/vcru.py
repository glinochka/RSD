"""vc.ru article publisher via browser emulation (Playwright)."""
from __future__ import annotations

import logging
import os
import random
import re
from pathlib import Path

from .base import PublishResult

logger = logging.getLogger(__name__)

_VC_HOME = "https://vc.ru/"
_VC_WRITE = "https://vc.ru/write"
_UA_POOL = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
)


def _to_plain_text(html: str) -> str:
    text = re.sub(r"</(h1|h2|p|li)>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class VcRuPublisher:
    """Publish articles to vc.ru via browser emulation."""

    def __init__(self, *, email: str, password: str, subsite_id: str | None = None):
        # `email` can be email/phone/login used by Yandex ID.
        self.email = email
        self.password = password
        self.subsite_id = subsite_id

    async def publish(
        self,
        *,
        title: str,
        html_content: str,
        image_path: str | None = None,
    ) -> PublishResult:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except Exception as exc:
            logger.exception("Playwright is not available for vc.ru publisher: %s", exc)
            return PublishResult(success=False, error="Playwright is required for vc.ru browser emulation")

        headless = os.environ.get("ARTICLE_PUBLISHER_VC_HEADLESS", "true").strip().lower() != "false"
        state_path = self._state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=headless,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context_kwargs = {}
                if state_path.exists():
                    context_kwargs["storage_state"] = str(state_path)
                context_kwargs.update(self._build_context_options())
                context = await browser.new_context(**context_kwargs)
                page = await context.new_page()
                await self._apply_stealth_script(page)

                await page.goto(_VC_HOME, wait_until="domcontentloaded", timeout=90_000)
                if await self._requires_login(page):
                    await self._perform_login(page)
                    await context.storage_state(path=str(state_path))

                await self._create_article_in_editor(
                    page=page,
                    title=title,
                    html_content=html_content,
                    image_path=image_path,
                )

                published_url = page.url
                await context.storage_state(path=str(state_path))
                await context.close()
                await browser.close()
                return PublishResult(success=True, url=published_url)
        except PlaywrightTimeoutError:
            return PublishResult(success=False, error="vc.ru browser flow timeout")
        except Exception as exc:
            logger.exception("VcRuPublisher.publish failed: %s", exc)
            return PublishResult(success=False, error=str(exc)[:500])

    async def _requires_login(self, page) -> bool:
        if "id.yandex" in (page.url or "") or "passport.yandex" in (page.url or ""):
            return True
        selectors = [
            "button:has-text('Войти')",
            "a:has-text('Войти')",
        ]
        for selector in selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return False

    async def _perform_login(self, page) -> None:
        await page.goto(_VC_HOME, wait_until="domcontentloaded", timeout=90_000)

        login_btn = page.locator("button:has-text('Войти'), a:has-text('Войти')").first
        if await login_btn.count() > 0:
            await login_btn.click()

        yandex_btn = page.locator("button:has-text('Яндекс ID'), a:has-text('Яндекс ID')").first
        if await yandex_btn.count() > 0:
            await yandex_btn.click()

        # Yandex ID step (can be phone/email/login)
        login_input = page.locator("input[name='login'], input[data-t='field:input-login']").first
        if await login_input.count() > 0:
            await login_input.click()
            await self._human_type(page, self.email)
            await page.keyboard.press("Enter")

            password_input = page.locator("input[name='passwd'], input[type='password']").first
            if await password_input.count() > 0:
                await password_input.click()
                await self._human_type(page, self.password)
                await page.keyboard.press("Enter")

        await page.wait_for_timeout(4_000)
        if await self._requires_login(page):
            raise RuntimeError(
                "vc.ru requires additional Yandex confirmation (OTP/captcha). "
                "Sign in manually once in headed mode to persist session."
            )

    async def _create_article_in_editor(self, *, page, title: str, html_content: str, image_path: str | None) -> None:
        await page.goto(_VC_WRITE, wait_until="domcontentloaded", timeout=90_000)

        # Title
        title_locators = [
            "textarea[placeholder*='Заголовок']",
            "input[placeholder*='Заголовок']",
            "[contenteditable='true'][data-placeholder*='Заголовок']",
        ]
        title_filled = False
        for selector in title_locators:
            locator = page.locator(selector).first
            if await locator.count() > 0:
                await locator.click()
                await self._human_type(page, title)
                title_filled = True
                break
        if not title_filled:
            editable = page.locator("[contenteditable='true']").first
            await editable.click()
            await self._human_type(page, title)
            await page.keyboard.press("Enter")

        # Body
        body_text = _to_plain_text(html_content)
        body_locator = page.locator("[contenteditable='true']").last
        await body_locator.click()
        await self._human_type(page, body_text)

        # Image upload if editor exposes file input
        if image_path and Path(image_path).exists():
            file_inputs = page.locator("input[type='file']")
            if await file_inputs.count() > 0:
                await file_inputs.first.set_input_files(str(Path(image_path)))

        # Publish + confirm
        publish_btn = page.locator("button:has-text('Опубликовать')").first
        if await publish_btn.count() == 0:
            raise RuntimeError("vc.ru publish button not found")
        await publish_btn.click()

        confirm_btn = page.locator("button:has-text('Опубликовать'), button:has-text('Подтвердить')").first
        if await confirm_btn.count() > 0:
            try:
                await confirm_btn.click(timeout=5_000)
            except Exception:
                pass

        await page.wait_for_timeout(5_000)

    def _state_path(self) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", self.email.strip().lower())[:120] or "default"
        state_dir = os.environ.get("ARTICLE_PUBLISHER_VC_STATE_DIR", "").strip()
        if state_dir:
            return Path(state_dir) / f"{safe}.json"
        backend_root = Path(__file__).resolve().parents[4]
        return backend_root / "app" / "uploads" / "article_publisher" / "vc_state" / f"{safe}.json"

    def _build_context_options(self) -> dict:
        width = random.randint(1280, 1920)
        height = random.randint(720, 1080)
        return {
            "user_agent": random.choice(_UA_POOL),
            "viewport": {"width": width, "height": height},
            "screen": {"width": width, "height": height},
            "locale": "ru-RU",
            "timezone_id": os.environ.get("ARTICLE_PUBLISHER_BROWSER_TIMEZONE", "Europe/Moscow"),
            "color_scheme": "light",
            "device_scale_factor": 1,
        }

    async def _apply_stealth_script(self, page) -> None:
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'language', { get: () => 'ru-RU' });
            Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            window.chrome = window.chrome || { runtime: {} };
            """
        )

    async def _human_type(self, page, text: str) -> None:
        for char in text:
            await page.keyboard.type(char, delay=random.randint(30, 95))
