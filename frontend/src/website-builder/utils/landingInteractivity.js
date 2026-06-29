/**

 * Self-contained JS injected into AI-generated landing pages at render time.

 * Activates burger menus, carousels, FAQ accordions, tabs, and lead forms.

 */



const LANDING_UI_RUNTIME_BODY = `

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

    document.querySelectorAll('[data-carousel], [data-slider], .carousel, .slider, [class*="carousel"], [class*="slider"]').forEach(function(root) {

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



  function bindAccordionTrigger(trigger, panel, singleOpenRoot) {

    if (!trigger || !panel || trigger.dataset.rsdAccordionBound) return;

    trigger.dataset.rsdAccordionBound = '1';

    trigger.addEventListener('click', function(e) {

      e.preventDefault();

      var willOpen = isElementHidden(panel);

      if (singleOpenRoot && willOpen) {

        singleOpenRoot.querySelectorAll('[data-accordion-panel]').forEach(function(other) {

          if (other !== panel) setElementVisible(other, false);

        });

        singleOpenRoot.querySelectorAll('[data-accordion-trigger]').forEach(function(otherBtn) {

          if (otherBtn !== trigger) otherBtn.setAttribute('aria-expanded', 'false');

        });

      }

      setElementVisible(panel, willOpen);

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

        root.querySelectorAll('[data-accordion-trigger]').forEach(function(trigger) {

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

  }



  function initTabs() {

    document.querySelectorAll('[data-tabs]').forEach(function(root) {

      if (root.dataset.rsdTabsBound) return;

      var triggers = root.querySelectorAll('[data-tab-trigger]');

      var panels = root.querySelectorAll('[data-tab-panel]');

      if (!triggers.length || !panels.length) return;

      root.dataset.rsdTabsBound = '1';



      function activate(activeIndex) {

        for (var i = 0; i < triggers.length; i++) {

          var active = i === activeIndex;

          triggers[i].setAttribute('aria-selected', active ? 'true' : 'false');

          if (panels[i]) setElementVisible(panels[i], active);

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

`;



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

${LANDING_UI_RUNTIME_BODY}

  onReady(function() {

    initMobileMenus();

    initCarousels();

    initAccordions();

    initTabs();

  });

})();

`;



const FORM_RUNTIME_BODY = `

  function normalizeFieldKey(key) {

    return String(key || '').toLowerCase().replace(/[^a-z\u0430-\u044f\u04510-9]/gi, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');

  }



  var FIO_ALIASES = ['fio', 'name', 'client_name', 'fullname', 'full_name', 'your_name', 'username', 'contact_name', '\u0438\u043c\u044f', '\u0444\u0438\u043e'];

  var PHONE_ALIASES = ['phone', 'tel', 'telephone', 'mobile', 'your_phone', 'phonenumber', '\u0442\u0435\u043b\u0435\u0444\u043e\u043d'];



  function pickFieldValue(fields, aliases) {

    for (var key in fields) {

      if (!Object.prototype.hasOwnProperty.call(fields, key)) continue;

      var norm = normalizeFieldKey(key);

      for (var i = 0; i < aliases.length; i++) {

        if (norm === aliases[i]) return fields[key];

      }

    }

    return '';

  }



  function collectFormFields(form) {

    var fields = {};

    form.querySelectorAll('input, textarea, select').forEach(function(el) {

      if (el.type === 'submit' || el.type === 'button' || el.type === 'hidden') return;

      var key = el.name || el.id;

      if (!key) {

        if (el.type === 'tel') key = 'phone';

        else if (el.type === 'email') key = 'email';

        else return;

      }

      var val = (el.value || '').trim();

      if (val) fields[key] = val;

    });

    return fields;

  }



  function resolveLeadFields(form, fields) {

    var fio = pickFieldValue(fields, FIO_ALIASES) || fields.fio || fields.name || fields.client_name || '';

    var phone = pickFieldValue(fields, PHONE_ALIASES) || fields.phone || fields.tel || '';

    if (!phone) {

      var telEl = form.querySelector('input[type="tel"]');

      if (telEl && telEl.value) phone = telEl.value.trim();

    }

    if (!fio) {

      form.querySelectorAll('input[type="text"], input:not([type])').forEach(function(el) {

        if (fio) return;

        var k = normalizeFieldKey(el.name || el.id || '');

        if (FIO_ALIASES.indexOf(k) >= 0 && el.value) fio = el.value.trim();

      });

    }

    return { fio: fio, phone: phone };

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



  function bindLeadForm(form, cfg) {

    form.dataset.rsdFormBound = '1';

    form.setAttribute('method', 'post');

    form.removeAttribute('action');

    form.addEventListener('submit', function(e) {

      e.preventDefault();

      var fields = collectFormFields(form);

      var lead = resolveLeadFields(form, fields);

      if (!String(lead.fio).trim() || !String(lead.phone).trim()) {

        showFormMessage(form, '\u0423\u043a\u0430\u0436\u0438\u0442\u0435 \u0424\u0418\u041e \u0438 \u0442\u0435\u043b\u0435\u0444\u043e\u043d', true);

        return;

      }



      var submitBtn = form.querySelector('[type="submit"]');

      if (submitBtn) submitBtn.disabled = true;



      fetch(cfg.apiBase.replace(/\\/$/, '') + '/api/v1/agents/' + cfg.agentId + '/website/leads', {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({

          fields: fields,

          client_name: String(lead.fio).trim() || null,

        }),

      })

        .then(function(res) {

          return res.json().then(function(data) {

            if (!res.ok) throw new Error(data.detail || '\u041e\u0448\u0438\u0431\u043a\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0438');

            showFormMessage(form, data.message || '\u0417\u0430\u044f\u0432\u043a\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0430!', false);

            form.reset();

          });

        })

        .catch(function(err) {

          showFormMessage(form, err.message || '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0437\u0430\u044f\u0432\u043a\u0443', true);

        })

        .finally(function() {

          if (submitBtn) submitBtn.disabled = false;

        });

    });

  }



  function initWebsiteForms() {

    var cfg = window.__RSD_LANDING__;

    if (!cfg || !cfg.agentId || !cfg.apiBase) return;



    document.querySelectorAll('form').forEach(function(form) {

      if (form.dataset.rsdFormBound) return;

      if (form.querySelector('input[type="search"]')) return;



      var formType = (form.getAttribute('data-rsd-form') || 'lead').toLowerCase();

      if (formType === 'search') return;



      bindLeadForm(form, cfg);

    });

  }

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

${FORM_RUNTIME_BODY}

  onReady(initWebsiteForms);

})();

`;



/** Full runtime (menus + carousels + FAQ + tabs + forms) for pages without backend-injected scripts. */

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

${LANDING_UI_RUNTIME_BODY}

${FORM_RUNTIME_BODY}

  onReady(function() {

    initMobileMenus();

    initCarousels();

    initAccordions();

    initTabs();

    initWebsiteForms();

  });

})();

`;


