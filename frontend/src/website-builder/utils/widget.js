/**
 * RSD chat widget helpers (matches /api/agents/external/widget.js embed).
 */

export function openAgentWidget() {
  const toggle = document.querySelector('.rsd-widget-root .rsd-widget-toggle');
  if (toggle) {
    toggle.click();
    return true;
  }
  return false;
}

export function injectAgentWidgetScript({
  apiKey,
  apiBase = typeof window !== 'undefined' ? window.location.origin : '',
  position = 'bottom-right',
  title = 'Онлайн-консультант',
  greeting = 'Здравствуйте! Чем могу помочь?',
  theme = 'dark',
  placeholder = 'Напишите ваш вопрос...',
}) {
  if (!apiKey || typeof document === 'undefined') return () => {};

  const existing = document.querySelector('script[data-rsd-widget="1"]');
  if (existing) {
    if (existing.dataset.apiKey !== apiKey) {
      existing.remove();
      const root = document.querySelector('.rsd-widget-root');
      if (root) root.remove();
      window.RSDChatWidgetInitialized = false;
    } else {
      return () => {};
    }
  }

  const script = document.createElement('script');
  script.src = `${apiBase.replace(/\/$/, '')}/api/agents/external/widget.js`;
  script.async = true;
  script.dataset.rsdWidget = '1';
  script.dataset.apiBase = apiBase.replace(/\/$/, '');
  script.dataset.apiKey = apiKey;
  script.dataset.position = position;
  script.dataset.title = title;
  script.dataset.greeting = greeting;
  script.dataset.theme = theme;
  script.dataset.placeholder = placeholder;

  document.body.appendChild(script);

  return () => {
    script.remove();
    const root = document.querySelector('.rsd-widget-root');
    if (root) root.remove();
    window.RSDChatWidgetInitialized = false;
  };
}
