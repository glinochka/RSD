/**
 * Self-contained JS injected into AI-generated landing pages at render time.
 * Fixes common broken patterns: mobile burger menus and carousels/sliders.
 */
export const LANDING_INTERACTIVITY_RUNTIME = `
(function() {
  'use strict';

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function isElementHidden(el) {
    if (!el) return true;
    if (el.classList.contains('hidden')) return true;
    var style = window.getComputedStyle(el);
    return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
  }

  function setElementVisible(el, visible) {
    if (!el) return;
    el.classList.toggle('hidden', !visible);
    el.classList.toggle('invisible', !visible);
    el.style.display = visible ? '' : 'none';
    el.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  function bindMenuToggle(btn, menu) {
    if (!btn || !menu || btn.dataset.rsdMenuBound) return;
    btn.dataset.rsdMenuBound = '1';
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      var willShow = isElementHidden(menu);
      setElementVisible(menu, willShow);
      btn.setAttribute('aria-expanded', willShow ? 'true' : 'false');
    });
  }

  function initMobileMenus() {
    document.querySelectorAll('[data-menu-toggle]').forEach(function(btn) {
      var menu = document.querySelector('[data-mobile-menu]');
      if (!menu) {
        var header = btn.closest('header, nav');
        menu = header && header.querySelector('[data-mobile-menu], [id*="mobile"], [class*="mobile-menu"]');
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

    document.querySelectorAll('header button, nav button').forEach(function(btn) {
      if (btn.dataset.rsdMenuBound || btn.type === 'submit') return;
      var label = (btn.getAttribute('aria-label') || btn.textContent || '').toLowerCase();
      var looksLikeBurger = label.indexOf('меню') >= 0 || label.indexOf('menu') >= 0
        || btn.querySelector('svg') || (btn.className && /burger|hamburger|menu-toggle/i.test(btn.className));
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
    var roots = document.querySelectorAll('[data-carousel], [data-slider], .carousel, .slider, [class*="carousel"], [class*="slider"]');
    roots.forEach(function(root) {
      if (root.dataset.rsdCarouselBound) return;

      var slides = root.querySelectorAll('[data-slide], .carousel-slide, .slide');
      if (slides.length < 2) {
        slides = Array.prototype.filter.call(root.children, function(node) {
          return node.nodeType === 1 && (node.tagName === 'DIV' || node.tagName === 'SECTION' || node.tagName === 'ARTICLE');
        });
      }
      if (slides.length < 2) return;

      root.dataset.rsdCarouselBound = '1';
      var index = 0;

      function show(nextIndex) {
        index = (nextIndex + slides.length) % slides.length;
        for (var i = 0; i < slides.length; i++) {
          setElementVisible(slides[i], i === index);
        }
      }

      show(0);

      var prev = root.querySelector('[data-carousel-prev], [data-prev], .carousel-prev, button[aria-label*="ред"], button[aria-label*="Prev"], button[aria-label*="Назад"]');
      var next = root.querySelector('[data-carousel-next], [data-next], .carousel-next, button[aria-label*="лед"], button[aria-label*="Next"], button[aria-label*="Впер"]');

      if (prev) {
        prev.addEventListener('click', function(e) {
          e.preventDefault();
          show(index - 1);
        });
      }
      if (next) {
        next.addEventListener('click', function(e) {
          e.preventDefault();
          show(index + 1);
        });
      }

      var touchStartX = 0;
      root.addEventListener('touchstart', function(e) {
        if (e.touches && e.touches[0]) touchStartX = e.touches[0].clientX;
      }, { passive: true });
      root.addEventListener('touchend', function(e) {
        if (!e.changedTouches || !e.changedTouches[0]) return;
        var delta = e.changedTouches[0].clientX - touchStartX;
        if (Math.abs(delta) > 40) show(index + (delta < 0 ? 1 : -1));
      });
    });
  }

  onReady(function() {
    initMobileMenus();
    initCarousels();
  });
})();
`;
