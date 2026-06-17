/**
 * Self-contained JS injected into AI-generated landing pages at render time.
 * Fixes common broken patterns: mobile burger menus, carousels, and lead forms.
 */

export const LANDING_MENU_CAROUSEL_RUNTIME = `
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

export const LANDING_FORM_RUNTIME = `
(function() {
  'use strict';

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function collectFormFields(form) {
    var fields = {};
    form.querySelectorAll('input, textarea, select').forEach(function(el) {
      if (!el.name && !el.id) return;
      if (el.type === 'submit' || el.type === 'button' || el.type === 'hidden') return;
      var key = el.name || el.id;
      var val = (el.value || '').trim();
      if (val) fields[key] = val;
    });
    return fields;
  }

  function showFormMessage(form, text, isError) {
    var box = form.querySelector('[data-rsd-form-message]');
    if (!box) {
      box = document.createElement('p');
      box.setAttribute('data-rsd-form-message', '1');
      box.style.marginTop = '0.75rem';
      box.style.fontSize = '0.875rem';
      form.appendChild(box);
    }
    box.textContent = text;
    box.style.color = isError ? '#dc2626' : '#16a34a';
  }

  function initWebsiteForms() {
    var cfg = window.__RSD_LANDING__;
    if (!cfg || !cfg.agentId || !cfg.apiBase) return;

    document.querySelectorAll('form').forEach(function(form) {
      if (form.dataset.rsdFormBound) return;
      if ((form.getAttribute('method') || '').toLowerCase() === 'get') return;
      if (form.querySelector('input[type="search"]')) return;

      var formType = (form.getAttribute('data-rsd-form') || 'lead').toLowerCase();
      if (formType === 'search') return;

      form.dataset.rsdFormBound = '1';
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        var fields = collectFormFields(form);
        var fio = fields.fio || fields.name || fields.client_name || '';
        var phone = fields.phone || fields.tel || '';
        if (!String(fio).trim() || !String(phone).trim()) {
          showFormMessage(form, 'Укажите ФИО и телефон', true);
          return;
        }

        var submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        fetch(cfg.apiBase.replace(/\\/$/, '') + '/api/v1/agents/' + cfg.agentId + '/website/leads', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fields: fields,
            client_name: String(fio).trim() || null,
          }),
        })
          .then(function(res) {
            return res.json().then(function(data) {
              if (!res.ok) throw new Error(data.detail || 'Ошибка отправки');
              showFormMessage(form, data.message || 'Заявка отправлена!', false);
              form.reset();
            });
          })
          .catch(function(err) {
            showFormMessage(form, err.message || 'Не удалось отправить заявку', true);
          })
          .finally(function() {
            if (submitBtn) submitBtn.disabled = false;
          });
      });
    });
  }

  onReady(initWebsiteForms);
})();
`;

/** Full runtime (menus + carousels + forms) for pages without backend-injected scripts. */
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
      bindMenuToggle(btn, menu);
    });
  }

  function initCarousels() {
    document.querySelectorAll('[data-carousel], [data-slider], .carousel, .slider').forEach(function(root) {
      if (root.dataset.rsdCarouselBound) return;
      var slides = root.querySelectorAll('[data-slide], .carousel-slide, .slide');
      if (slides.length < 2) return;
      root.dataset.rsdCarouselBound = '1';
      var index = 0;
      function show(nextIndex) {
        index = (nextIndex + slides.length) % slides.length;
        for (var i = 0; i < slides.length; i++) setElementVisible(slides[i], i === index);
      }
      show(0);
      var prev = root.querySelector('[data-carousel-prev], [data-prev]');
      var next = root.querySelector('[data-carousel-next], [data-next]');
      if (prev) prev.addEventListener('click', function(e) { e.preventDefault(); show(index - 1); });
      if (next) next.addEventListener('click', function(e) { e.preventDefault(); show(index + 1); });
    });
  }

  function collectFormFields(form) {
    var fields = {};
    form.querySelectorAll('input, textarea, select').forEach(function(el) {
      if (!el.name && !el.id) return;
      if (el.type === 'submit' || el.type === 'button' || el.type === 'hidden') return;
      var key = el.name || el.id;
      var val = (el.value || '').trim();
      if (val) fields[key] = val;
    });
    return fields;
  }

  function showFormMessage(form, text, isError) {
    var box = form.querySelector('[data-rsd-form-message]');
    if (!box) {
      box = document.createElement('p');
      box.setAttribute('data-rsd-form-message', '1');
      box.style.marginTop = '0.75rem';
      box.style.fontSize = '0.875rem';
      form.appendChild(box);
    }
    box.textContent = text;
    box.style.color = isError ? '#dc2626' : '#16a34a';
  }

  function initWebsiteForms() {
    var cfg = window.__RSD_LANDING__;
    if (!cfg || !cfg.agentId || !cfg.apiBase) return;
    document.querySelectorAll('form').forEach(function(form) {
      if (form.dataset.rsdFormBound) return;
      if ((form.getAttribute('method') || '').toLowerCase() === 'get') return;
      if (form.querySelector('input[type="search"]')) return;
      var formType = (form.getAttribute('data-rsd-form') || 'lead').toLowerCase();
      if (formType === 'search') return;
      form.dataset.rsdFormBound = '1';
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        var fields = collectFormFields(form);
        var fio = fields.fio || fields.name || fields.client_name || '';
        var phone = fields.phone || fields.tel || '';
        if (!String(fio).trim() || !String(phone).trim()) {
          showFormMessage(form, 'Укажите ФИО и телефон', true);
          return;
        }
        var submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;
        fetch(cfg.apiBase.replace(/\\/$/, '') + '/api/v1/agents/' + cfg.agentId + '/website/leads', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fields: fields, client_name: String(fio).trim() || null }),
        })
          .then(function(res) {
            return res.json().then(function(data) {
              if (!res.ok) throw new Error(data.detail || 'Ошибка отправки');
              showFormMessage(form, data.message || 'Заявка отправлена!', false);
              form.reset();
            });
          })
          .catch(function(err) {
            showFormMessage(form, err.message || 'Не удалось отправить заявку', true);
          })
          .finally(function() {
            if (submitBtn) submitBtn.disabled = false;
          });
      });
    });
  }

  onReady(function() {
    initMobileMenus();
    initCarousels();
    initWebsiteForms();
  });
})();
`;
