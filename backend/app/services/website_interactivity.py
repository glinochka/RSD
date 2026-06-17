"""Post-process helpers for AI-generated landing HTML."""

from __future__ import annotations

import re

# Marker to avoid double-injecting runtime on repeated saves.
RUNTIME_MARKER = "data-rsd-landing-runtime"


def inject_landing_interactivity_runtime(html: str) -> str:
    """Append a small interactivity runtime for burger menus and carousels."""
    if not html or RUNTIME_MARKER in html:
        return html

    script = f"""<script {RUNTIME_MARKER}="1">
(function() {{
  'use strict';
  function onReady(fn) {{
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }}
  function isHidden(el) {{
    if (!el) return true;
    if (el.classList.contains('hidden')) return true;
    var s = window.getComputedStyle(el);
    return s.display === 'none' || s.visibility === 'hidden';
  }}
  function setVisible(el, v) {{
    if (!el) return;
    el.classList.toggle('hidden', !v);
    el.style.display = v ? '' : 'none';
    el.setAttribute('aria-hidden', v ? 'false' : 'true');
  }}
  function bind(btn, menu) {{
    if (!btn || !menu || btn.dataset.rsdMenuBound) return;
    btn.dataset.rsdMenuBound = '1';
    btn.addEventListener('click', function(e) {{
      e.preventDefault();
      var open = isHidden(menu);
      setVisible(menu, open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }});
  }}
  function initMenus() {{
    document.querySelectorAll('[data-menu-toggle]').forEach(function(btn) {{
      var menu = document.querySelector('[data-mobile-menu]');
      if (!menu) {{
        var h = btn.closest('header, nav');
        menu = h && h.querySelector('[data-mobile-menu], [id*="mobile"], [class*="mobile-menu"]');
      }}
      bind(btn, menu);
    }});
    document.querySelectorAll('header button, nav button').forEach(function(btn) {{
      if (btn.dataset.rsdMenuBound || btn.type === 'submit') return;
      var label = (btn.getAttribute('aria-label') || btn.textContent || '').toLowerCase();
      if (label.indexOf('меню') < 0 && label.indexOf('menu') < 0 && !btn.querySelector('svg')) return;
      var menu = null;
      var controls = btn.getAttribute('aria-controls');
      if (controls) menu = document.getElementById(controls);
      if (!menu) {{
        var scope = btn.closest('header, nav') || document;
        menu = scope.querySelector('[data-mobile-menu], [id*="mobile"], [class*="mobile-menu"]');
      }}
      bind(btn, menu);
    }});
  }}
  function initCarousels() {{
    document.querySelectorAll('[data-carousel], [data-slider], .carousel, .slider').forEach(function(root) {{
      if (root.dataset.rsdCarouselBound) return;
      var slides = root.querySelectorAll('[data-slide], .carousel-slide, .slide');
      if (slides.length < 2) {{
        slides = Array.prototype.filter.call(root.children, function(n) {{
          return n.nodeType === 1;
        }});
      }}
      if (slides.length < 2) return;
      root.dataset.rsdCarouselBound = '1';
      var idx = 0;
      function show(i) {{
        idx = (i + slides.length) % slides.length;
        for (var j = 0; j < slides.length; j++) setVisible(slides[j], j === idx);
      }}
      show(0);
      var prev = root.querySelector('[data-carousel-prev], [data-prev], .carousel-prev');
      var next = root.querySelector('[data-carousel-next], [data-next], .carousel-next');
      if (prev) prev.addEventListener('click', function(e) {{ e.preventDefault(); show(idx - 1); }});
      if (next) next.addEventListener('click', function(e) {{ e.preventDefault(); show(idx + 1); }});
    }});
  }}
  onReady(function() {{ initMenus(); initCarousels(); }});
}})();
</script>"""

    if re.search(r"</body>\s*$", html, re.IGNORECASE):
        return re.sub(r"</body>\s*$", script + "\n</body>", html, count=1, flags=re.IGNORECASE)
    return html + script
