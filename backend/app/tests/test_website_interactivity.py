"""Tests for landing page interactivity and sanitization."""

from app.services.website_interactivity import (
    RUNTIME_MARKER,
    inject_landing_interactivity_runtime,
)
from app.services.website_sanitization_service import get_website_sanitization_service


SAMPLE_INTERACTIVE_HTML = """
<header>
  <button type="button" data-menu-toggle aria-label="Меню" aria-expanded="false">☰</button>
  <div data-mobile-menu class="hidden md:hidden">Links</div>
</header>
<section id="reviews">
  <div data-carousel>
    <div data-slide>Review 1</div>
    <div data-slide class="hidden">Review 2</div>
    <button type="button" data-carousel-prev>←</button>
    <button type="button" data-carousel-next>→</button>
  </div>
</section>
<section id="faq">
  <div data-accordion>
    <div data-accordion-item>
      <button type="button" data-accordion-trigger aria-expanded="false">Вопрос?</button>
      <div data-accordion-panel class="hidden">Ответ.</div>
    </div>
  </div>
</section>
"""


def test_sanitize_fullpage_preserves_interactivity_data_attributes():
    service = get_website_sanitization_service()
    sanitized = service.sanitize_fullpage_html(SAMPLE_INTERACTIVE_HTML)

    assert 'data-menu-toggle' in sanitized
    assert 'data-mobile-menu' in sanitized
    assert 'data-carousel' in sanitized
    assert 'data-slide' in sanitized
    assert 'data-carousel-prev' in sanitized
    assert 'data-accordion-trigger' in sanitized
    assert 'data-accordion-panel' in sanitized
    assert 'aria-expanded' in sanitized
    assert 'aria-label' in sanitized


def test_sanitize_fullpage_strips_onclick_handlers():
    service = get_website_sanitization_service()
    html = '<button onclick="alert(1)" data-menu-toggle>Menu</button>'
    sanitized = service.sanitize_fullpage_html(html)

    assert 'onclick' not in sanitized.lower()
    assert 'data-menu-toggle' in sanitized


def test_inject_landing_interactivity_runtime_adds_script_once():
    html = SAMPLE_INTERACTIVE_HTML
    injected = inject_landing_interactivity_runtime(html)

    assert RUNTIME_MARKER in injected
    assert injected.count(RUNTIME_MARKER) == 1
    assert 'initAccordions' in injected


def test_inject_landing_interactivity_runtime_is_idempotent():
    html = inject_landing_interactivity_runtime(SAMPLE_INTERACTIVE_HTML)
    again = inject_landing_interactivity_runtime(html)

    assert again.count(RUNTIME_MARKER) == 1
