"""Website Export Service — generates static HTML/CSS/JS files for ZIP export."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp

from ..alembic.database import async_session_maker
from ..alembic.models import Website, WebsiteBlock
from ..config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EXPORT_TEMP_DIR = Path(os.environ.get("EXPORT_TEMP_DIR", "/tmp/website-exports"))
EXPORT_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB per user quota
EXPORT_TTL_HOURS = 24
EXPORT_SMALL_IMAGE_THRESHOLD = 5 * 1024  # 5KB for base64 encoding


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ExportResult:
    """Result of website export operation."""

    success: bool
    archive_path: str | None = None
    archive_size_bytes: int = 0
    error_message: str | None = None
    files_included: list[str] = field(default_factory=list)
    download_url: str | None = None


@dataclass
class ExportStatus:
    """Current status of an export job."""

    website_id: int
    status: str  # pending | processing | completed | failed
    progress_percent: int = 0
    created_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    download_token: str | None = None
    expires_at: datetime | None = None


# ---------------------------------------------------------------------------
# HTML Templates
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{meta_description}">
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{og_description}">
    {og_image_meta}
    {favicon_link}
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        primary: '{primary_color}',
                        secondary: '{secondary_color}',
                        accent: '{accent_color}',
                    }},
                    fontFamily: {{
                        sans: ['{font_family}', 'system-ui', 'sans-serif'],
                    }},
                }}
            }}
        }}
    </script>
    <style>
        {custom_css}
    </style>
    {widget_config_script}
</head>
<body class="{body_classes}">
    {content}
    
    {widget_script}
    
    <script src="js/main.js"></script>
</body>
</html>"""

WIDGET_CONFIG_TEMPLATE = """
<script>
    window.AgentWidgetConfig = {{
        agentId: {agent_id},
        apiKey: '{widget_api_key}',
        theme: {{
            primaryColor: '{primary_color}',
            position: 'bottom-right'
        }},
        welcomeMessage: 'Здравствуйте! Чем могу помочь?'
    }};
</script>
"""

WIDGET_SCRIPT_TEMPLATE = """
<script>
    (function() {{
        var script = document.createElement('script');
        script.src = '{widget_script_url}';
        script.async = true;
        script.onerror = function() {{
            console.warn('Failed to load agent widget');
        }};
        document.head.appendChild(script);
    }})();
</script>
"""

README_TEMPLATE = """# Инструкция по развертыванию сайта

## Файлы в архиве

- `index.html` — главная страница сайта
- `css/styles.css` — стили (опционально, если встроены в HTML)
- `js/main.js` — JavaScript для интерактивности
- `assets/images/` — изображения
- `assets/favicon/` — favicon файлы

## Развертывание

### Вариант 1: Статический хостинг (рекомендуется)
1. Загрузите все файлы на статический хостинг:
   - Netlify
   - Vercel
   - GitHub Pages
   - Cloudflare Pages
   - Firebase Hosting

2. Или на обычный хостинг с поддержкой статических файлов.

### Вариант 2: Локальный просмотр
Откройте `index.html` в браузере. Для полной функциональности рекомендуется использовать локальный сервер:

```bash
cd website-{slug}
python -m http.server 8000
```

Затем откройте http://localhost:8000

## Настройка

### Цвета
Цвета настраиваются в `index.html` в секции `<script>` Tailwind CSS.

### Контент
Редактируйте текст прямо в `index.html`.

### Виджет агента
Виджет автоматически загружается с сервера RSD AI. 
Для отключения удалите секцию `AgentWidgetConfig` и соответствующий `<script>`.

## Поддержка

По вопросам обращайтесь: support@rsd-ai.ru

---
Сгенерировано: {generated_at}
Сайт: {website_slug}
"""

MAIN_JS_TEMPLATE = """// Main JavaScript for website
(function() {
    'use strict';
    
    // Mobile menu toggle
    document.addEventListener('DOMContentLoaded', function() {
        var menuToggle = document.querySelector('[data-menu-toggle]');
        var mobileMenu = document.querySelector('[data-mobile-menu]');
        
        if (menuToggle && mobileMenu) {
            menuToggle.addEventListener('click', function() {
                mobileMenu.classList.toggle('hidden');
            });
        }
        
        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
            anchor.addEventListener('click', function(e) {
                e.preventDefault();
                var target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
        
        // Lazy load images
        if ('IntersectionObserver' in window) {
            var imageObserver = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        var img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                        }
                        imageObserver.unobserve(img);
                    }
                });
            });
            
            document.querySelectorAll('img[data-src]').forEach(function(img) {
                imageObserver.observe(img);
            });
        }
    });
})();
"""


# ---------------------------------------------------------------------------
# Block Renderers
# ---------------------------------------------------------------------------

def render_hero_block(block: dict) -> str:
    """Render hero section block."""
    content = block.get("content", {})
    styles = block.get("styles", {})
    
    headline = content.get("headline", "Добро пожаловать")
    subheadline = content.get("subheadline", "")
    cta_text = content.get("cta_text", "Узнать больше")
    cta_link = content.get("cta_link", "#contacts")
    background_image = content.get("background_image_url", "")
    
    bg_class = "bg-gradient-to-r from-primary/10 to-secondary/10"
    bg_style = ""
    if background_image:
        bg_style = f' style="background-image: url(\'{background_image}\'); background-size: cover; background-position: center;"'
        bg_class += " relative"
    
    text_align = styles.get("textAlign", "center")
    padding = styles.get("padding", "py-20 md:py-32")
    
    return f"""
    <section class="{bg_class}"{bg_style}>
        <div class="container mx-auto px-4 {padding} text-{text_align}">
            <h1 class="text-4xl md:text-6xl font-bold text-gray-900 mb-6">{headline}</h1>
            {f'<p class="text-xl md:text-2xl text-gray-600 mb-8 max-w-2xl mx-auto">{subheadline}</p>' if subheadline else ''}
            <a href="{cta_link}" class="inline-block bg-primary text-white px-8 py-4 rounded-lg font-semibold hover:opacity-90 transition-opacity">
                {cta_text}
            </a>
        </div>
    </section>
    """


def render_services_block(block: dict) -> str:
    """Render services section block."""
    content = block.get("content", {})
    styles = block.get("styles", {})
    
    title = content.get("title", "Наши услуги")
    items = content.get("items", [])
    
    bg_color = styles.get("backgroundColor", "bg-white")
    text_align = styles.get("textAlign", "center")
    
    services_html = ""
    for item in items:
        name = item.get("name", "Услуга")
        description = item.get("description", "")
        price = item.get("price", "")
        icon = item.get("icon", "")
        
        icon_html = f'<div class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4"><span class="text-2xl">{icon}</span></div>' if icon else ""
        price_html = f'<p class="text-primary font-semibold mt-2">{price}</p>' if price else ""
        
        services_html += f"""
        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
            {icon_html}
            <h3 class="text-xl font-semibold text-gray-900 mb-2">{name}</h3>
            {f'<p class="text-gray-600">{description}</p>' if description else ''}
            {price_html}
        </div>
        """
    
    grid_cols = "grid-cols-1 md:grid-cols-2 lg:grid-cols-3" if len(items) >= 3 else "grid-cols-1 md:grid-cols-2"
    
    return f"""
    <section class="{bg_color} py-16 md:py-24">
        <div class="container mx-auto px-4">
            <h2 class="text-3xl md:text-4xl font-bold text-{text_align} mb-12">{title}</h2>
            <div class="grid {grid_cols} gap-8">
                {services_html}
            </div>
        </div>
    </section>
    """


def render_about_block(block: dict) -> str:
    """Render about section block."""
    content = block.get("content", {})
    styles = block.get("styles", {})
    
    title = content.get("title", "О нас")
    text = content.get("text", "")
    image_url = content.get("image_url", "")
    
    layout = styles.get("layout", "text-left")
    bg_color = styles.get("backgroundColor", "bg-gray-50")
    
    image_html = f"""
    <div class="lg:w-1/2">
        <img src="{image_url}" alt="{title}" class="rounded-2xl shadow-lg w-full object-cover" loading="lazy">
    </div>
    """ if image_url else ""
    
    content_html = f"""
    <div class="lg:w-1/2">
        <h2 class="text-3xl md:text-4xl font-bold text-gray-900 mb-6">{title}</h2>
        <div class="prose prose-lg text-gray-600">
            {text.replace(chr(10), '<br>')}
        </div>
    </div>
    """
    
    if layout == "image-right":
        inner = content_html + image_html
    else:
        inner = image_html + content_html if image_url else content_html
    
    return f"""
    <section class="{bg_color} py-16 md:py-24">
        <div class="container mx-auto px-4">
            <div class="flex flex-col lg:flex-row gap-12 items-center">
                {inner}
            </div>
        </div>
    </section>
    """


def render_contacts_block(block: dict, agent_contacts: dict | None = None) -> str:
    """Render contacts section block."""
    content = block.get("content", {})
    styles = block.get("styles", {})
    
    title = content.get("title", "Контакты")
    contact_info = content.get("contact_info", {})
    show_form = content.get("show_form", True)
    
    # Merge with agent contacts if available
    if agent_contacts:
        contact_info.update(agent_contacts)
    
    bg_color = styles.get("backgroundColor", "bg-white")
    
    phone = contact_info.get("phone", "")
    email = contact_info.get("email", "")
    address = contact_info.get("address", "")
    telegram = contact_info.get("telegram", "")
    whatsapp = contact_info.get("whatsapp", "")
    working_hours = contact_info.get("working_hours", "")
    
    contact_items = []
    
    if phone:
        contact_items.append(f"""
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
            </div>
            <div>
                <p class="text-sm text-gray-500">Телефон</p>
                <a href="tel:{phone}" class="text-lg font-medium text-gray-900 hover:text-primary">{phone}</a>
            </div>
        </div>
        """)
    
    if email:
        contact_items.append(f"""
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
            </div>
            <div>
                <p class="text-sm text-gray-500">Email</p>
                <a href="mailto:{email}" class="text-lg font-medium text-gray-900 hover:text-primary">{email}</a>
            </div>
        </div>
        """)
    
    if telegram:
        tg_username = telegram.replace("@", "")
        contact_items.append(f"""
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-primary" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.161c-.18 1.897-.962 6.502-1.359 8.627-.168.9-.5 1.201-.82 1.23-.697.064-1.226-.461-1.901-.903-1.056-.692-1.653-1.123-2.678-1.799-1.185-.781-.417-1.21.258-1.911.177-.184 3.247-2.977 3.307-3.23.007-.032.015-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.062 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.442-.751-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.523 5.831-2.529 6.998-3.015 3.333-1.386 4.025-1.627 4.477-1.635.099-.002.321.023.465.141.121.099.154.232.17.325.015.093.034.305.019.471z"/></svg>
            </div>
            <div>
                <p class="text-sm text-gray-500">Telegram</p>
                <a href="https://t.me/{tg_username}" target="_blank" class="text-lg font-medium text-gray-900 hover:text-primary">@{tg_username}</a>
            </div>
        </div>
        """)
    
    if whatsapp:
        contact_items.append(f"""
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-primary" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
            </div>
            <div>
                <p class="text-sm text-gray-500">WhatsApp</p>
                <a href="https://wa.me/{whatsapp}" target="_blank" class="text-lg font-medium text-gray-900 hover:text-primary">{whatsapp}</a>
            </div>
        </div>
        """)
    
    if address:
        contact_items.append(f"""
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
            </div>
            <div>
                <p class="text-sm text-gray-500">Адрес</p>
                <p class="text-lg font-medium text-gray-900">{address}</p>
            </div>
        </div>
        """)
    
    if working_hours:
        contact_items.append(f"""
        <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            </div>
            <div>
                <p class="text-sm text-gray-500">Часы работы</p>
                <p class="text-lg font-medium text-gray-900">{working_hours}</p>
            </div>
        </div>
        """)
    
    form_html = """
    <div class="bg-gray-50 p-8 rounded-2xl">
        <h3 class="text-xl font-semibold text-gray-900 mb-6">Отправить сообщение</h3>
        <form id="contact-form" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Имя</label>
                <input type="text" name="name" required class="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-transparent" placeholder="Ваше имя">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Email или телефон</label>
                <input type="text" name="contact" required class="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-transparent" placeholder="your@email.com">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Сообщение</label>
                <textarea name="message" rows="4" required class="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-transparent" placeholder="Ваше сообщение..."></textarea>
            </div>
            <button type="submit" class="w-full bg-primary text-white px-6 py-3 rounded-lg font-semibold hover:opacity-90 transition-opacity">
                Отправить
            </button>
        </form>
    </div>
    """ if show_form else ""
    
    return f"""
    <section id="contacts" class="{bg_color} py-16 md:py-24">
        <div class="container mx-auto px-4">
            <h2 class="text-3xl md:text-4xl font-bold text-center mb-12">{title}</h2>
            <div class="grid md:grid-cols-2 gap-12">
                <div class="space-y-6">
                    {''.join(contact_items)}
                </div>
                {form_html}
            </div>
        </div>
    </section>
    """


def render_cta_block(block: dict) -> str:
    """Render call-to-action section block."""
    content = block.get("content", {})
    styles = block.get("styles", {})
    
    title = content.get("title", "Готовы начать?")
    subtitle = content.get("subtitle", "")
    button_text = content.get("button_text", "Связаться")
    button_link = content.get("button_link", "#contacts")
    
    bg_color = styles.get("backgroundColor", "bg-primary")
    text_color = "text-white" if bg_color in ["bg-primary", "bg-gray-900"] else "text-gray-900"
    
    return f"""
    <section class="{bg_color} py-16 md:py-20">
        <div class="container mx-auto px-4 text-center">
            <h2 class="text-3xl md:text-4xl font-bold {text_color} mb-4">{title}</h2>
            {f'<p class="text-xl {text_color} opacity-90 mb-8">{subtitle}</p>' if subtitle else ''}
            <a href="{button_link}" class="inline-block bg-white text-primary px-8 py-4 rounded-lg font-semibold hover:bg-gray-100 transition-colors">
                {button_text}
            </a>
        </div>
    </section>
    """


def render_footer_block(block: dict) -> str:
    """Render footer section block."""
    content = block.get("content", {})
    
    company_name = content.get("company_name", "Моя компания")
    copyright_text = content.get("copyright_text", f"© {datetime.now().year} Все права защищены")
    
    return f"""
    <footer class="bg-gray-900 text-white py-12">
        <div class="container mx-auto px-4">
            <div class="flex flex-col md:flex-row justify-between items-center">
                <div class="mb-4 md:mb-0">
                    <p class="text-lg font-semibold">{company_name}</p>
                    <p class="text-gray-400 text-sm mt-1">{copyright_text}</p>
                </div>
                <div class="text-gray-400 text-sm">
                    <p>Сделано с помощью <a href="https://rsd-ai.ru" target="_blank" class="text-primary hover:underline">RSD AI</a></p>
                </div>
            </div>
        </div>
    </footer>
    """


def render_custom_block(block: dict) -> str:
    """Render custom HTML block."""
    content = block.get("content", {})
    styles = block.get("styles", {})
    
    custom_html = content.get("html", "")
    bg_color = styles.get("backgroundColor", "")
    padding = styles.get("padding", "py-16")
    
    bg_class = f" {bg_color}" if bg_color else ""
    
    return f"""
    <section class="{padding}{bg_class}">
        <div class="container mx-auto px-4">
            {custom_html}
        </div>
    </section>
    """


BLOCK_RENDERERS = {
    "hero": render_hero_block,
    "services": render_services_block,
    "about": render_about_block,
    "contacts": render_contacts_block,
    "cta": render_cta_block,
    "footer": render_footer_block,
    "custom": render_custom_block,
}


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def sanitize_filename(filename: str) -> str:
    """Sanitize a string to be used as a filename."""
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(" .")
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    return sanitized or "unnamed"


def get_image_extension(content_type: str | None, url: str) -> str:
    """Determine image extension from content type or URL."""
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
        "image/webp": ".webp",
        "image/avif": ".avif",
    }
    
    if content_type:
        ext = ext_map.get(content_type.lower())
        if ext:
            return ext
    
    # Try to extract from URL
    parsed = urlparse(url)
    path = parsed.path.lower()
    for ext in [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".avif"]:
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    
    return ".jpg"  # Default


def generate_download_token(website_id: int) -> str:
    """Generate a unique download token for an export."""
    data = f"{website_id}:{datetime.now(timezone.utc).timestamp()}:{os.urandom(16).hex()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Image Processing
# ---------------------------------------------------------------------------

class ImageProcessor:
    """Handles downloading and processing of images for export."""

    def __init__(self, session: aiohttp.ClientSession, base_path: Path):
        self.session = session
        self.base_path = base_path
        self.images_path = base_path / "assets" / "images"
        self.images_path.mkdir(parents=True, exist_ok=True)
        self.processed_urls: dict[str, str] = {}  # url -> local_path
        self.downloaded_count = 0
        self.base64_count = 0

    async def process_image(self, url: str, allow_base64: bool = True) -> str:
        """Process an image: download or convert to base64. Returns new path."""
        if not url or url.startswith("data:"):
            return url
        
        if url in self.processed_urls:
            return self.processed_urls[url]
        
        try:
            # Try to download
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    logger.warning(f"Failed to download image {url}: HTTP {response.status}")
                    return url
                
                content = await response.read()
                content_type = response.headers.get("Content-Type", "")
                
                # Check size for base64 conversion
                if allow_base64 and len(content) < EXPORT_SMALL_IMAGE_THRESHOLD:
                    # Convert to base64
                    b64 = base64.b64encode(content).decode()
                    ext = get_image_extension(content_type, url)
                    data_url = f"data:{content_type or 'image/jpeg'};base64,{b64}"
                    self.base64_count += 1
                    self.processed_urls[url] = data_url
                    return data_url
                
                # Save to file
                ext = get_image_extension(content_type, url)
                filename = f"image_{self.downloaded_count:04d}{ext}"
                filepath = self.images_path / filename
                
                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(content)
                
                relative_path = f"assets/images/{filename}"
                self.processed_urls[url] = relative_path
                self.downloaded_count += 1
                return relative_path
                
        except Exception as e:
            logger.warning(f"Failed to process image {url}: {e}")
            return url

    async def process_html_images(self, html: str) -> str:
        """Find and process all images in HTML content."""
        # Find img src attributes
        pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        
        async def replace_url(match: re.Match) -> str:
            original_url = match.group(1)
            if original_url.startswith("data:"):
                return match.group(0)
            new_url = await self.process_image(original_url)
            return match.group(0).replace(original_url, new_url)
        
        # Process sequentially to avoid race conditions
        result = html
        for match in re.finditer(pattern, html):
            replacement = await replace_url(match)
            result = result.replace(match.group(0), replacement, 1)
        
        return result


# ---------------------------------------------------------------------------
# Website Export Service
# ---------------------------------------------------------------------------

class WebsiteExportService:
    """Service for exporting websites as static ZIP archives."""

    def __init__(self):
        self.temp_dir = EXPORT_TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _generate_custom_css(self, styles: dict) -> str:
        """Generate custom CSS from style configuration."""
        css_parts = []
        
        primary_color = styles.get("primary_color", "#2563EB")
        secondary_color = styles.get("secondary_color", "#1E40AF")
        accent_color = styles.get("accent_color", "#3B82F6")
        background_color = styles.get("background_color", "#FFFFFF")
        text_color = styles.get("text_color", "#1F2937")
        
        css_parts.append(f"""
:root {{
    --color-primary: {primary_color};
    --color-secondary: {secondary_color};
    --color-accent: {accent_color};
    --color-background: {background_color};
    --color-text: {text_color};
}}
        """)
        
        # Add any additional custom CSS
        custom_css = styles.get("custom_css", "")
        if custom_css:
            css_parts.append(custom_css)
        
        return "\n".join(css_parts)

    def _render_blocks(self, blocks: list[dict], agent_contacts: dict | None = None) -> str:
        """Render all blocks to HTML."""
        html_parts = []
        
        for block in blocks:
            block_type = block.get("type", "custom")
            renderer = BLOCK_RENDERERS.get(block_type, render_custom_block)
            
            try:
                if block_type == "contacts":
                    html = renderer(block, agent_contacts)
                else:
                    html = renderer(block)
                html_parts.append(html)
            except Exception as e:
                logger.error(f"Failed to render block {block_type}: {e}")
                # Render empty section as fallback
                html_parts.append(f'<!-- Failed to render {block_type} block -->')
        
        return "\n".join(html_parts)

    def _build_html(
        self,
        website_data: dict,
        blocks_html: str,
        widget_config: dict | None = None,
    ) -> str:
        """Build the complete HTML document."""
        styles = website_data.get("styles", {})
        
        title = website_data.get("title", "Мой сайт")
        meta_description = website_data.get("meta_description", "")
        og_title = website_data.get("og_title", title)
        og_description = website_data.get("og_description", meta_description)
        og_image_url = website_data.get("og_image_url", "")
        favicon_url = website_data.get("favicon_url", "")
        
        primary_color = styles.get("primary_color", "#2563EB")
        secondary_color = styles.get("secondary_color", "#1E40AF")
        accent_color = styles.get("accent_color", "#3B82F6")
        font_family = styles.get("font_family", "Inter")
        dark_mode = styles.get("dark_mode", False)
        
        # Build OG image meta tag
        og_image_meta = f'<meta property="og:image" content="{og_image_url}">' if og_image_url else ""
        
        # Build favicon link
        if favicon_url:
            ext = favicon_url.split(".")[-1].lower()
            if ext == "ico":
                favicon_link = f'<link rel="icon" type="image/x-icon" href="{favicon_url}">'
            elif ext == "svg":
                favicon_link = f'<link rel="icon" type="image/svg+xml" href="{favicon_url}">'
            else:
                favicon_link = f'<link rel="icon" type="image/{ext}" href="{favicon_url}">'
        else:
            favicon_link = ""
        
        # Build widget config
        widget_config_script = ""
        widget_script = ""
        if widget_config and widget_config.get("agent_id"):
            widget_config_script = WIDGET_CONFIG_TEMPLATE.format(
                agent_id=widget_config["agent_id"],
                widget_api_key=widget_config.get("api_key", ""),
                primary_color=primary_color,
            )
            
            base_url = settings.BASE_URL or "https://rsd-ai.ru"
            widget_script_url = f"{base_url}/widget/main.js"
            widget_script = WIDGET_SCRIPT_TEMPLATE.format(
                widget_script_url=widget_script_url
            )
        
        # Build body classes
        body_classes = "min-h-screen bg-white"
        if dark_mode:
            body_classes += " dark"
        
        custom_css = self._generate_custom_css(styles)
        
        return HTML_TEMPLATE.format(
            title=title,
            meta_description=meta_description,
            og_title=og_title,
            og_description=og_description,
            og_image_meta=og_image_meta,
            favicon_link=favicon_link,
            primary_color=primary_color,
            secondary_color=secondary_color,
            accent_color=accent_color,
            font_family=font_family,
            custom_css=custom_css,
            widget_config_script=widget_config_script,
            body_classes=body_classes,
            content=blocks_html,
            widget_script=widget_script,
        )

    async def _create_zip_archive(
        self,
        website_slug: str,
        html_content: str,
        base_path: Path,
    ) -> tuple[str, int, list[str]]:
        """Create ZIP archive with all website files."""
        files_included = []
        
        # Create directories
        css_path = base_path / "css"
        js_path = base_path / "js"
        assets_path = base_path / "assets"
        favicon_path = assets_path / "favicon"
        
        css_path.mkdir(parents=True, exist_ok=True)
        js_path.mkdir(parents=True, exist_ok=True)
        assets_path.mkdir(parents=True, exist_ok=True)
        favicon_path.mkdir(parents=True, exist_ok=True)
        
        # Write index.html
        index_path = base_path / "index.html"
        async with aiofiles.open(index_path, "w", encoding="utf-8") as f:
            await f.write(html_content)
        files_included.append("index.html")
        
        # Write main.js
        js_file_path = js_path / "main.js"
        async with aiofiles.open(js_file_path, "w", encoding="utf-8") as f:
            await f.write(MAIN_JS_TEMPLATE)
        files_included.append("js/main.js")
        
        # Write README.txt
        readme_path = base_path / "README.txt"
        readme_content = README_TEMPLATE.format(
            slug=website_slug,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            website_slug=website_slug,
        )
        async with aiofiles.open(readme_path, "w", encoding="utf-8") as f:
            await f.write(readme_content)
        files_included.append("README.txt")
        
        # Create ZIP archive
        zip_filename = f"website-{website_slug}-{int(datetime.now(timezone.utc).timestamp())}.zip"
        zip_path = self.temp_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    file_path = Path(root) / file
                    arc_name = str(file_path.relative_to(base_path))
                    zf.write(file_path, arc_name)
        
        archive_size = zip_path.stat().st_size
        
        return str(zip_path), archive_size, files_included

    async def export_website(
        self,
        website_id: int,
        website_data: dict,
        agent_contacts: dict | None = None,
        widget_config: dict | None = None,
    ) -> ExportResult:
        """Export a website to a ZIP archive.
        
        Args:
            website_id: The website ID
            website_data: Dict containing website metadata, styles, blocks
            agent_contacts: Optional dict with agent contact information
            widget_config: Optional dict with widget configuration
            
        Returns:
            ExportResult with archive details
        """
        website_slug = website_data.get("slug", f"site-{website_id}")
        export_id = f"{website_slug}-{int(datetime.now(timezone.utc).timestamp())}"
        
        base_path = self.temp_dir / export_id
        base_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create aiohttp session for downloading images
            async with aiohttp.ClientSession() as session:
                image_processor = ImageProcessor(session, base_path)
                
                # Render blocks
                blocks = website_data.get("blocks", [])
                blocks_html = self._render_blocks(blocks, agent_contacts)
                
                # Process images in HTML
                blocks_html = await image_processor.process_html_images(blocks_html)
                
                # Build complete HTML
                html_content = self._build_html(website_data, blocks_html, widget_config)
                
                # Create ZIP archive
                archive_path, archive_size, files_included = await self._create_zip_archive(
                    website_slug, html_content, base_path
                )
                
                # Generate download URL
                download_token = generate_download_token(website_id)
                base_url = settings.BASE_URL or "https://rsd-ai.ru"
                download_url = f"{base_url}/api/v1/websites/{website_id}/download?token={download_token}"
                
                return ExportResult(
                    success=True,
                    archive_path=archive_path,
                    archive_size_bytes=archive_size,
                    files_included=files_included,
                    download_url=download_url,
                )
                
        except Exception as e:
            logger.exception(f"Export failed for website {website_id}: {e}")
            return ExportResult(
                success=False,
                error_message=str(e),
            )
        finally:
            # Cleanup temp files (keep the zip, remove the folder)
            import shutil
            if base_path.exists():
                shutil.rmtree(base_path, ignore_errors=True)

    async def cleanup_old_exports(self) -> int:
        """Clean up export archives older than EXPORT_TTL_HOURS.
        
        Returns:
            Number of files deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=EXPORT_TTL_HOURS)
        deleted_count = 0
        
        for file_path in self.temp_dir.glob("*.zip"):
            try:
                stat = file_path.stat()
                file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                
                if file_mtime < cutoff:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old export: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {file_path}: {e}")
        
        return deleted_count


# Singleton instance
_export_service: WebsiteExportService | None = None


def get_website_export_service() -> WebsiteExportService:
    """Get or create singleton instance of WebsiteExportService."""
    global _export_service
    if _export_service is None:
        _export_service = WebsiteExportService()
    return _export_service
