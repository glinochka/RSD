"""Post-process helpers for AI-generated landing HTML."""

from __future__ import annotations

import re

# Marker to avoid double-injecting runtime on repeated saves.
RUNTIME_MARKER = "data-rsd-landing-runtime"

# Shared runtime: menus, carousels, FAQ accordions, tabs.
# Kept in sync with frontend/src/website-builder/utils/landingInteractivity.js
_LANDING_RUNTIME_JS = """
(function() {
  'use strict';
  function onReady(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }
  function isHidden(el) {
    if (!el) return true;
    if (el.classList.contains('hidden')) return true;
    var s = window.getComputedStyle(el);
    return s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0';
  }
  function setVisible(el, v) {
    if (!el) return;
    el.classList.toggle('hidden', !v);
    el.classList.toggle('invisible', !v);
    el.style.display = v ? '' : 'none';
    el.setAttribute('aria-hidden', v ? 'false' : 'true');
  }
  function bindMenuToggle(btn, menu) {
    if (!btn || !menu || btn.dataset.rsdMenuBound) return;
    btn.dataset.rsdMenuBound = '1';
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      var open = isHidden(menu);
      setVisible(menu, open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  function initMenus() {
    document.querySelectorAll('[data-menu-toggle]').forEach(function(btn) {
      var menu = document.querySelector('[data-mobile-menu]');
      if (!menu) {
        var h = btn.closest('header, nav');
        menu = h && h.querySelector('[data-mobile-menu], [id*="mobile"], [class*="mobile-menu"]');
      }
      bindMenuToggle(btn, menu);
    });
    document.querySelectorAll('[data-mobile-menu-toggle]').forEach(function(btn) {
      var menu = document.querySelector('[data-mobile-menu]');
      if (!menu) {
        var controls = btn.getAttribute('aria-controls');
        menu = controls ? document.getElementById(controls) : null;
      }
      bindMenuToggle(btn, menu);
    });
    document.querySelectorAll('button').forEach(function(btn) {
      if (btn.dataset.rsdMenuBound || btn.type === 'submit') return;
      var label = (btn.getAttribute('aria-label') || btn.textContent || '').toLowerCase();
      var className = String(btn.className || '');
      var inNavigation = !!btn.closest('header, nav, [class*="nav"], [id*="nav"], [class*="menu"], [id*="menu"]');
      var looksLikeBurger = label.indexOf('меню') >= 0 || label.indexOf('menu') >= 0
        || /burger|hamburger|menu-toggle/i.test(className)
        || (btn.hasAttribute('aria-controls') && inNavigation);
      if (!looksLikeBurger) return;
      var menu = null;
      var controls = btn.getAttribute('aria-controls');
      if (controls) menu = document.getElementById(controls);
      if (!menu) {
        var scope = btn.closest('header, nav') || document;
        menu = scope.querySelector('[id*="mobile"], [id*="Mobile"], [class*="mobile-menu"], [data-mobile-menu]');
      }
      if (!menu) {
        var sibling = btn.nextElementSibling;
        if (sibling && sibling.tagName !== 'BUTTON') menu = sibling;
      }
      bindMenuToggle(btn, menu);
    });
  }
  function initCarousels() {
    document.querySelectorAll('[data-carousel], [data-slider], .carousel, .slider, [class*="carousel"], [class*="slider"], [id*="review"], [id*="testimonial"], [class*="review"], [class*="testimonial"]').forEach(function(root) {
      if (root.dataset.rsdCarouselBound) return;
      var slides = root.querySelectorAll('[data-slide], .carousel-slide, .slide');
      if (slides.length < 2) {
        slides = Array.prototype.filter.call(root.children, function(n) {
          return n.nodeType === 1 && (n.tagName === 'DIV' || n.tagName === 'SECTION' || n.tagName === 'ARTICLE');
        });
      }
      if (slides.length < 2) return;
      root.dataset.rsdCarouselBound = '1';
      var idx = 0;
      function show(i) {
        idx = (i + slides.length) % slides.length;
        for (var j = 0; j < slides.length; j++) setVisible(slides[j], j === idx);
      }
      show(0);
      var prev = root.querySelector('[data-carousel-prev], [data-prev], .carousel-prev, button[aria-label*="ред"], button[aria-label*="Prev"], button[aria-label*="Назад"]');
      var next = root.querySelector('[data-carousel-next], [data-next], .carousel-next, button[aria-label*="лед"], button[aria-label*="Next"], button[aria-label*="Впер"]');
      if (prev) prev.addEventListener('click', function(e) { e.preventDefault(); show(idx - 1); });
      if (next) next.addEventListener('click', function(e) { e.preventDefault(); show(idx + 1); });
      var touchStartX = 0;
      root.addEventListener('touchstart', function(e) {
        if (e.touches && e.touches[0]) touchStartX = e.touches[0].clientX;
      }, { passive: true });
      root.addEventListener('touchend', function(e) {
        if (!e.changedTouches || !e.changedTouches[0]) return;
        var delta = e.changedTouches[0].clientX - touchStartX;
        if (Math.abs(delta) > 40) show(idx + (delta < 0 ? 1 : -1));
      });
    });
  }
  function bindAccordionTrigger(trigger, panel, singleOpenRoot) {
    if (!trigger || !panel || trigger.dataset.rsdAccordionBound) return;
    trigger.dataset.rsdAccordionBound = '1';
    trigger.addEventListener('click', function(e) {
      e.preventDefault();
      var willOpen = isHidden(panel);
      if (singleOpenRoot && willOpen) {
        singleOpenRoot.querySelectorAll('[data-accordion-panel]').forEach(function(other) {
          if (other !== panel) setVisible(other, false);
        });
        singleOpenRoot.querySelectorAll('[data-accordion-trigger]').forEach(function(otherBtn) {
          if (otherBtn !== trigger) otherBtn.setAttribute('aria-expanded', 'false');
        });
      }
      setVisible(panel, willOpen);
      trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
  }
  function initAccordions() {
    document.querySelectorAll('[data-accordion]').forEach(function(root) {
      root.querySelectorAll('[data-accordion-item]').forEach(function(item) {
        bindAccordionTrigger(
          item.querySelector('[data-accordion-trigger]'),
          item.querySelector('[data-accordion-panel]'),
          root
        );
      });
      if (!root.querySelector('[data-accordion-item]')) {
        var triggers = root.querySelectorAll('[data-accordion-trigger]');
        triggers.forEach(function(trigger) {
          var panel = trigger.nextElementSibling;
          if (panel && panel.matches('[data-accordion-panel]')) {
            bindAccordionTrigger(trigger, panel, root);
          }
        });
      }
    });
    document.querySelectorAll('[data-faq-toggle]').forEach(function(trigger) {
      var panel = trigger.nextElementSibling;
      if (panel && (panel.matches('[data-faq-panel]') || panel.matches('[data-accordion-panel]'))) {
        bindAccordionTrigger(trigger, panel, null);
      }
    });
    document.querySelectorAll('section, div').forEach(function(root) {
      if (root.dataset.rsdGenericAccordionBound) return;
      var marker = ((root.id || '') + ' ' + (root.className || '')).toLowerCase();
      if (marker.indexOf('faq') < 0 && marker.indexOf('accordion') < 0 && marker.indexOf('вопрос') < 0) return;
      var triggers = root.querySelectorAll('button');
      if (triggers.length < 2 || triggers.length > 30) return;
      var bound = 0;
      triggers.forEach(function(trigger) {
        if (trigger.dataset.rsdAccordionBound) return;
        var panel = trigger.nextElementSibling;
        if (!panel || panel.tagName === 'BUTTON') return;
        if (!panel.matches('div, section, article, p, ul, ol')) return;
        trigger.setAttribute('data-accordion-trigger', '');
        panel.setAttribute('data-accordion-panel', '');
        var expanded = trigger.getAttribute('aria-expanded') === 'true';
        if (!expanded && !panel.classList.contains('hidden')) panel.classList.add('hidden');
        bindAccordionTrigger(trigger, panel, root);
        if (expanded) setVisible(panel, true);
        bound += 1;
      });
      if (bound > 0) {
        root.dataset.rsdGenericAccordionBound = '1';
        root.setAttribute('data-accordion', '');
      }
    });
  }
  function initTabs() {
    document.querySelectorAll('[data-tabs]').forEach(function(root) {
      if (root.dataset.rsdTabsBound) return;
      var triggers = root.querySelectorAll('[data-tab-trigger]');
      var panels = root.querySelectorAll('[data-tab-panel]');
      if (!triggers.length || !panels.length) return;
      root.dataset.rsdTabsBound = '1';
      function activate(index) {
        for (var i = 0; i < triggers.length; i++) {
          var active = i === index;
          triggers[i].setAttribute('aria-selected', active ? 'true' : 'false');
          if (panels[i]) setVisible(panels[i], active);
        }
      }
      triggers.forEach(function(trigger, index) {
        trigger.addEventListener('click', function(e) {
          e.preventDefault();
          activate(index);
        });
      });
      activate(0);
    });
  }
  onReady(function() {
    initMenus();
    initCarousels();
    initAccordions();
    initTabs();
  });
})();
"""


def inject_landing_interactivity_runtime(html: str) -> str:
    """Append platform interactivity runtime for menus, carousels, FAQ, tabs."""
    if not html or RUNTIME_MARKER in html:
        return html

    script = f'<script {RUNTIME_MARKER}="1">{_LANDING_RUNTIME_JS.strip()}</script>'

    if re.search(r"</body>\s*$", html, re.IGNORECASE):
        return re.sub(r"</body>\s*$", script + "\n</body>", html, count=1, flags=re.IGNORECASE)
    return html + script
