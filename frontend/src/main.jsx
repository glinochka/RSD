import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

function initRsdWidget() {
  const env = import.meta.env;
  const apiKey = (env.VITE_WIDGET_API_KEY || '').trim();
  if (!apiKey || typeof document === 'undefined') return;
  if (window.location.pathname.startsWith('/custom')) return;

  if (document.querySelector('script[data-rsd-widget="1"]')) return;

  const apiBase = (env.VITE_WIDGET_API_BASE || 'https://rsd-ai.ru').trim() || 'https://rsd-ai.ru';
  const script = document.createElement('script');
  script.src = apiBase.replace(/\/$/, '') + '/api/agents/external/widget.js';
  script.async = true;
  script.dataset.rsdWidget = '1';
  script.dataset.apiBase = apiBase;
  script.dataset.apiKey = apiKey;
  script.dataset.position = (env.VITE_WIDGET_POSITION || 'bottom-right').trim();
  script.dataset.title = (env.VITE_WIDGET_TITLE || 'Онлайн-консультант RSD AI').trim();
  script.dataset.greeting = (env.VITE_WIDGET_GREETING || 'Здравствуйте! Чем могу помочь?').trim();
  script.dataset.placeholder = (env.VITE_WIDGET_PLACEHOLDER || 'Напишите ваш вопрос...').trim();
  script.dataset.theme = (env.VITE_WIDGET_THEME || 'dark').trim();

  const proactiveMessage = (env.VITE_WIDGET_PROACTIVE_MESSAGE || '').trim();
  const proactiveDelay = (env.VITE_WIDGET_PROACTIVE_DELAY || '').trim();
  const proactiveMessage2 = (env.VITE_WIDGET_PROACTIVE_MESSAGE_2 || '').trim();
  const proactiveDelay2 = (env.VITE_WIDGET_PROACTIVE_DELAY_2 || '').trim();
  if (proactiveMessage) script.dataset.proactiveMessage = proactiveMessage;
  if (proactiveDelay) script.dataset.proactiveDelay = proactiveDelay;
  if (proactiveMessage2) script.dataset.proactiveMessage2 = proactiveMessage2;
  if (proactiveDelay2) script.dataset.proactiveDelay2 = proactiveDelay2;

  document.body.appendChild(script);
}

initRsdWidget();

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found. Make sure your HTML has a div with id="root"');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
