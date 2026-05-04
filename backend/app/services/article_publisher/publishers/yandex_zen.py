"""Yandex Zen article publisher via browser emulation (Playwright)."""
from __future__ import annotations

import logging
import os
import random
import re
from pathlib import Path

from .base import PublishResult

logger = logging.getLogger(__name__)

_EDITOR_URL = "https://dzen.ru/editor"
_DEFAULT_UA_POOL = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)


def _to_plain_text(html: str) -> str:
    text = re.sub(r"</(h1|h2|p|li)>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class YandexZenPublisher:
    """Publish articles to Yandex Zen via browser emulation."""

    def __init__(self, *, login: str, password: str, channel_id: str | None = None):
        self.login = login
        self.password = password
        self.channel_id = channel_id

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
            logger.exception("Playwright is not available for Zen publisher: %s", exc)
            return PublishResult(success=False, error="Playwright is required for Zen browser emulation")

        headless = os.environ.get("ARTICLE_PUBLISHER_ZEN_HEADLESS", "true").strip().lower() != "false"
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

                await page.goto("https://dzen.ru/", wait_until="domcontentloaded", timeout=90_000)
                if await self._requires_login(page):
                    await self._perform_login(page)
                    await self._dismiss_post_login_prompts(page)
                    await context.storage_state(path=str(state_path))
                else:
                    await self._dismiss_post_login_prompts(page)

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
            return PublishResult(success=False, error="Zen browser flow timeout")
        except Exception as exc:
            logger.exception("YandexZenPublisher.publish failed: %s", exc)
            return PublishResult(success=False, error=str(exc)[:500])

    async def _requires_login(self, page) -> bool:
        if "passport.yandex" in (page.url or ""):
            return True
        selectors = [
            "input[name='login']",
            "input[data-t='field:input-login']",
            "a[href*='passport.yandex']",
            "button:has-text('Войти')",
        ]
        for selector in selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return False

    async def _perform_login(self, page) -> None:
        await page.goto("https://dzen.ru/", wait_until="domcontentloaded", timeout=90_000)
        sign_in_btn = page.locator("button:has-text('Войти'), a:has-text('Войти')").first
        if await sign_in_btn.count() > 0:
            await sign_in_btn.click()

        yandex_id_btn = page.locator("button:has-text('Яндекс ID'), a:has-text('Яндекс ID')").first
        if await yandex_id_btn.count() > 0:
            await yandex_id_btn.click()

        await page.wait_for_timeout(1_500)

        # Login
        login_input = page.locator("input[name='login'], input[data-t='field:input-login']").first
        await login_input.wait_for(timeout=60_000)
        await login_input.click()
        await self._human_type(page, self.login)
        await page.keyboard.press("Enter")

        # Password (when password flow is enabled)
        password_input = page.locator("input[name='passwd'], input[type='password']").first
        if await password_input.count() > 0:
            await password_input.wait_for(timeout=60_000)
            await password_input.click()
            await self._human_type(page, self.password)
            await page.keyboard.press("Enter")

        try:
            await page.wait_for_url(re.compile(r"https://(dzen|passport\\.yandex)\\..*"), timeout=90_000)
        except Exception:
            # If 2FA/captcha appears, return explicit error.
            if (
                await page.locator("text=Подтвердите вход").count() > 0
                or await page.locator("text=Введите код").count() > 0
                or await page.locator("text=Отправить код повторно").count() > 0
            ):
                raise RuntimeError(
                    "Yandex ID requires OTP/push confirmation. "
                    "Authorize once manually in headed mode to persist browser session."
                )
            # One more redirect attempt.
            await page.goto(_EDITOR_URL, wait_until="domcontentloaded", timeout=90_000)
            if "passport.yandex" in (page.url or ""):
                raise RuntimeError("Yandex login failed")

    async def _create_article_in_editor(self, *, page, title: str, html_content: str, image_path: str | None) -> None:
        await page.goto("https://dzen.ru/", wait_until="domcontentloaded", timeout=90_000)
        await self._dismiss_post_login_prompts(page)

        # Follow real user flow: avatar -> studio -> plus -> write article.
        avatar_btn = page.locator("[aria-label*='Профиль'], img[alt*='avatar'], button:has(img)").first
        if await avatar_btn.count() > 0:
            try:
                await avatar_btn.click(timeout=5_000)
            except Exception:
                pass

        studio_link = page.locator("a:has-text('Студия'), button:has-text('Студия')").first
        if await studio_link.count() > 0:
            await studio_link.click()
            await page.wait_for_timeout(2_000)

        plus_btn = page.locator("button:has-text('+'), button[aria-label*='Создать'], button[aria-label*='Написать']").first
        if await plus_btn.count() > 0:
            await plus_btn.click()

        write_article = page.locator("text=Написать статью").first
        if await write_article.count() > 0:
            await write_article.click()
        else:
            await page.goto(_EDITOR_URL, wait_until="domcontentloaded", timeout=90_000)

        # Try title field variants.
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
            # Fallback: type into first editable area.
            editable = page.locator("[contenteditable='true']").first
            await editable.click()
            await page.keyboard.type(title)
            await page.keyboard.press("Enter")

        body_text = _to_plain_text(html_content)
        body_locator = page.locator("[contenteditable='true']").last
        await body_locator.click()
        await self._human_type(page, body_text)

        if image_path and Path(image_path).exists():
            file_inputs = page.locator("input[type='file']")
            if await file_inputs.count() > 0:
                await file_inputs.first.set_input_files(str(Path(image_path)))

        publish_buttons = [
            "button:has-text('Опубликовать')",
            "button:has-text('Публикация')",
            "button[data-testid='publish-button']",
        ]
        clicked = False
        for selector in publish_buttons:
            btn = page.locator(selector).first
            if await btn.count() > 0:
                await btn.click()
                clicked = True
                break
        if not clicked:
            raise RuntimeError("Zen publish button not found in editor")

        # Confirm modal if present.
        confirm_btn = page.locator("button:has-text('Подтвердить'), button:has-text('Опубликовать')").first
        if await confirm_btn.count() > 0:
            try:
                await confirm_btn.click(timeout=5_000)
            except Exception:
                pass

        await page.wait_for_timeout(5_000)

    async def _dismiss_post_login_prompts(self, page) -> None:
        # "Напомнить позже" and similar post-login hardening prompts.
        for selector in (
            "button:has-text('Напомнить позже')",
            "button:has-text('Позже')",
            "button:has-text('Не сейчас')",
            "button:has-text('Пропустить')",
        ):
            btn = page.locator(selector).first
            if await btn.count() > 0:
                try:
                    await btn.click(timeout=2_000)
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

    def _state_path(self) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", self.login.strip().lower())[:120] or "default"
        state_dir = os.environ.get("ARTICLE_PUBLISHER_ZEN_STATE_DIR", "").strip()
        if state_dir:
            return Path(state_dir) / f"{safe}.json"
        backend_root = Path(__file__).resolve().parents[4]
        return backend_root / "app" / "uploads" / "article_publisher" / "dzen_state" / f"{safe}.json"

    def _build_context_options(self) -> dict:
        user_agent = random.choice(_DEFAULT_UA_POOL)
        width = random.randint(1280, 1920)
        height = random.randint(720, 1080)
        return {
            "user_agent": user_agent,
            "viewport": {"width": width, "height": height},
            "screen": {"width": width, "height": height},
            "locale": "ru-RU",
            "timezone_id": os.environ.get("ARTICLE_PUBLISHER_BROWSER_TIMEZONE", "Europe/Moscow"),
            "color_scheme": "light",
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False,
        }

    async def _apply_stealth_script(self, page) -> None:
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'language', { get: () => 'ru-RU' });
            Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4] });
            window.chrome = window.chrome || { runtime: {} };
            """
        )

    async def _human_type(self, page, text: str) -> None:
        for char in text:
            await page.keyboard.type(char, delay=random.randint(35, 110))
