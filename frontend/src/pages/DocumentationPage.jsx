import React, { useEffect, useMemo, useState } from 'react';
import MainLayout from '../components/Layout';
import '../styles/documentationPage.css';

const SECTIONS = [
  { id: 'quick-start', title: 'Быстрый старт' },
  { id: 'create-agent', title: 'Создание агента' },
  { id: 'knowledge-base', title: 'База знаний' },
  { id: 'scenarios', title: 'Сценарии использования' },
  { id: 'api-auth', title: 'Авторизация API' },
  { id: 'api-chat-endpoint', title: 'Endpoint внешнего чата' },
  { id: 'message-format', title: 'Формат входящих/исходящих сообщений' },
  { id: 'widget-connector', title: 'Виджет-коннектор' },
  { id: 'telegram-userbot-creds', title: 'api_id и api_hash для Telegram userbot' },
  { id: 'api-errors', title: 'Коды ошибок и диагностика' },
  { id: 'api-js-example', title: 'Пример на JavaScript' },
  { id: 'api-python-example', title: 'Пример на Python' },
  { id: 'production-tips', title: 'Рекомендации для production' },
];

const JS_EXAMPLE = `const API_BASE_URL = 'https://rsd-ai.ru'
const AGENT_API_KEY = 'agnt_xxxxxxxxxxxxxxxxxxxxxxxxx';

async function askAgent(message) {
  const response = await fetch(\`\${API_BASE_URL}/api/agents/external/chat\`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Agent-API-Key': AGENT_API_KEY
    },
    body: JSON.stringify({ message })
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'API request failed');
  }

  return response.json();
}

askAgent('Подскажи условия доставки')
  .then((data) => {
    console.log('Ответ агента:', data.answer);
    console.log('Источники:', data.sources);
  })
  .catch((error) => {
    console.error('Ошибка:', error.message);
  });`;

const PYTHON_EXAMPLE = `import requests

API_BASE_URL = "https://rsd-ai.ru"
AGENT_API_KEY = "agnt_xxxxxxxxxxxxxxxxxxxxxxxxx"

def ask_agent(message: str) -> dict:
    response = requests.post(
        f"{API_BASE_URL}/api/agents/external/chat",
        headers={
            "Content-Type": "application/json",
            "X-Agent-API-Key": AGENT_API_KEY,
        },
        json={"message": message},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    data = ask_agent("Какие услуги вы оказываете?")
    print("Ответ агента:", data.get("answer"))
    print("Источники:", data.get("sources"))`;

const CURL_EXAMPLE = `curl -X POST "https://rsd-ai.ru/api/agents/external/chat" \
  -H "Content-Type: application/json" \
  -H "X-Agent-API-Key: agnt_xxxxxxxxxxxxxxxxxxxxxxxxx" \
  -d '{"message":"Подскажите стоимость внедрения"}'`;

const WIDGET_CONNECTOR_EXAMPLE = `<script
  src="https://rsd-ai.ru/api/agents/external/widget.js"
  data-rsd-widget="1"
  data-api-base="https://rsd-ai.ru"
  data-api-key="agnt_xxxxxxxxxxxxxxxxxxxxxxxxx"

  data-position="bottom-right"
  data-title="Онлайн-консультант"
  data-greeting="Здравствуйте! Чем могу помочь?"
  data-placeholder="Напишите ваш вопрос..."

  data-theme="dark"

  data-proactive-message="Добрый день! Чем могу помочь?"
  data-proactive-delay="3"
  data-proactive-message-2="Готов ответить на любые вопросы 😊"
  data-proactive-delay-2="1"
></script>`;

const DocumentationContent = () => {
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);
  const sectionIds = useMemo(() => SECTIONS.map((s) => s.id), []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]?.target?.id) {
          setActiveSection(visible[0].target.id);
        }
      },
      { rootMargin: '-25% 0px -60% 0px', threshold: [0.2, 0.4, 0.6] },
    );

    sectionIds.forEach((id) => {
      const node = document.getElementById(id);
      if (node) {
        observer.observe(node);
      }
    });

    return () => observer.disconnect();
  }, [sectionIds]);

  return (
    <div className="documentation-page">
      <aside className="documentation-sidebar">
        <h2>Навигация</h2>
        <nav aria-label="Разделы документации">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className={activeSection === section.id ? 'doc-nav-link doc-nav-link--active' : 'doc-nav-link'}
            >
              {section.title}
            </a>
          ))}
        </nav>
      </aside>

      <article className="documentation-content">
        <section id="quick-start">
          <h1>Документация платформы RSD</h1>
          <p>
            Здесь собраны практические инструкции по созданию и настройке агентов, примеры типовых сценариев
            использования и подключению внешних систем через API.
          </p>
          <p>
            Схема работы: вы создаете агента в панели управления, настраиваете промпт и документы, получаете
            персональный API-ключ, после чего можете подключить чат на сайте или любую внешнюю систему.
          </p>
          <ul>
            <li>Если интеграция проходит впервые, начните с теста через cURL.</li>
            <li>После успешного теста перенесите вызов в backend вашего проекта.</li>
            <li>Только потом подключайте frontend-виджет и пользовательские сценарии.</li>
          </ul>
        </section>

        <section id="create-agent">
          <h2>Создание агента</h2>
          <ol>
            <li>Откройте раздел «Создать агента» в верхнем меню сайта.</li>
            <li>Подключите Telegram-бота через токен от BotFather.</li>
            <li>Задайте системный промпт: роль, задачи, стиль ответов и ограничения.</li>
            <li>Сохраните агента и откройте его карточку в разделе «Мои агенты».</li>
          </ol>
          <p>
            Совет: в промпте фиксируйте границы компетенции. Это сильно повышает стабильность качества ответов.
          </p>
        </section>

        <section id="knowledge-base">
          <h2>База знаний</h2>
          <p>
            Добавляйте файлы в карточке агента: платформа автоматически разобьет документы на чанки и проиндексирует
            их. При ответах агент будет опираться на найденный контекст.
          </p>
          <ul>
            <li>Поддерживайте документы в актуальном состоянии.</li>
            <li>Удаляйте устаревшие файлы, чтобы избежать противоречий.</li>
            <li>Разделяйте большие базы знаний по агентам и задачам.</li>
          </ul>
        </section>

        <section id="scenarios">
          <h2>Сценарии использования</h2>
          <h3>1) Онлайн-консультант на сайте</h3>
          <p>
            Подключите внешний виджет и отправляйте сообщения пользователя в API агента. Это подход для FAQ,
            консультаций и первичной квалификации заявок.
          </p>
          <h3>2) Внутренний ассистент команды</h3>
          <p>
            Интегрируйте API в CRM/ERP или внутреннюю панель, чтобы сотрудники быстро получали ответы на основе
            регламентов и базы знаний.
          </p>
          <h3>3) Ассистент для лендингов и форм</h3>
          <p>
            Используйте агента как слой логики перед отправкой формы: можно собирать требования клиента и уточнять
            детали до передачи в отдел продаж.
          </p>
        </section>

        <section id="api-auth">
          <h2>Авторизация API</h2>
          <p>
            У каждого агента есть собственный постоянный API-ключ. Ключ доступен в карточке агента и используется
            только для внешних запросов к конкретному агенту.
          </p>
          <p>
            Передавайте ключ в заголовке <code>X-Agent-API-Key</code>. Не вставляйте ключ в фронтенд в открытом виде:
            используйте серверный прокси для production-среды.
          </p>
        </section>

        <section id="api-chat-endpoint">
          <h2>Endpoint внешнего чата</h2>
          <p>
            <strong>Метод:</strong> <code>POST /api/agents/external/chat</code>
          </p>
          <p>
            <strong>Headers:</strong> <code>Content-Type: application/json</code>,{' '}
            <code>X-Agent-API-Key: &lt;ваш_ключ&gt;</code>
          </p>
          <p>
            <strong>Body:</strong> <code>{'{ "message": "Ваш вопрос" }'}</code> (поле <code>message</code> обязательно)
          </p>
          <p>
            <strong>Response:</strong> <code>{'{ "bot_id": 123, "bot_username": "...", "answer": "...", "sources": [] }'}</code>
          </p>
          <p>
            <strong>Быстрый тест через cURL:</strong>
          </p>
          <pre>
            <code>{CURL_EXAMPLE}</code>
          </pre>
        </section>

        <section id="message-format">
          <h2>Формат входящих/исходящих сообщений</h2>
          <p>
            Внешний endpoint чата принимает одно пользовательское сообщение за запрос и возвращает итоговый ответ
            агента с метаданными.
          </p>
          <h3>Что принимается (request)</h3>
          <ul>
            <li>
              <code>message</code> (<code>string</code>, обязательно) — текст сообщения пользователя.
            </li>
            <li>
              Заголовок <code>X-Agent-API-Key</code> (<code>string</code>, обязательно) — ключ конкретного агента.
            </li>
            <li>
              <code>Content-Type: application/json</code> — тело запроса должно быть в JSON-формате.
            </li>
          </ul>
          <h3>Что отправляется в ответ (response)</h3>
          <ul>
            <li>
              <code>bot_id</code> (<code>number</code>) — внутренний идентификатор агента.
            </li>
            <li>
              <code>bot_username</code> (<code>string</code>) — username подключенного Telegram-бота (если задан).
            </li>
            <li>
              <code>answer</code> (<code>string</code>) — итоговый текст ответа пользователю.
            </li>
            <li>
              <code>sources</code> (<code>array</code>) — список источников из базы знаний, использованных в ответе.
            </li>
          </ul>
          <p>
            Рекомендуется сохранять связку <code>message</code> и <code>answer</code> в логах интеграции для анализа
            качества ответов и отладки.
          </p>
        </section>

        <section id="widget-connector">
          <h2>Виджет-коннектор</h2>
          <p>
            Виджет-коннектор позволяет быстро встроить чат на сайт без разработки собственного UI. Он собирает сообщение
            пользователя, отправляет его в <code>/api/agents/external/chat</code> и отображает ответ агента.
          </p>
          <ol>
            <li>Добавьте скрипт виджета на страницу сайта.</li>
            <li>Передайте <code>data-api-base</code>, <code>data-api-key</code> и опциональные настройки UI.</li>
            <li>Проверьте отправку сообщений и отображение поля <code>answer</code> в интерфейсе.</li>
          </ol>
          <pre>
            <code>{WIDGET_CONNECTOR_EXAMPLE}</code>
          </pre>
          <p>
            <strong>Исходящие сообщения</strong> — всплывающий пузырёк над кнопкой чата. Первое сообщение:{' '}
            <code>data-proactive-message</code> + <code>data-proactive-delay</code> (секунды, по умолчанию 3). Второе сообщение:{' '}
            <code>data-proactive-message-2</code> + <code>data-proactive-delay-2</code> (секунды после первого, по умолчанию 1). Оба необязательны.
          </p>
          <p>
            <strong>Темы оформления</strong> задаются атрибутом <code>data-theme</code>: <code>dark</code> (по умолчанию),{' '}
            <code>light</code>, <code>ocean</code>, <code>forest</code>, <code>sunset</code>, <code>darkmode</code>.
          </p>
          <p>
            <strong>История чата</strong> сохраняется в <code>localStorage</code> и восстанавливается при обновлении страницы автоматически.
          </p>
          <p>
            Для production не публикуйте ключ в открытом фронтенде: используйте серверный прокси или подписанные
            короткоживущие токены доступа.
          </p>
        </section>

        <section id="telegram-userbot-creds">
          <h2>api_id и api_hash для Telegram userbot</h2>
          <p>
            Для подключения Telegram userbot нужны <code>api_id</code> и <code>api_hash</code> приложения Telegram.
            Эти значения выдаются в личном кабинете разработчика Telegram.
          </p>
          <ol>
            <li>
              Перейдите на <code>my.telegram.org</code> и войдите по номеру телефона аккаунта, который будет работать как
              userbot.
            </li>
            <li>
              Откройте раздел <code>API development tools</code> и создайте приложение (название и short name).
            </li>
            <li>
              Скопируйте выданные <code>api_id</code> и <code>api_hash</code> и сохраните их в секретах backend.
            </li>
          </ol>
          <p>
            Не передавайте <code>api_hash</code> в клиентский код и не публикуйте в репозитории. Для каждого окружения
            (dev/stage/prod) используйте отдельное безопасное хранение секретов.
          </p>
        </section>

        <section id="api-errors">
          <h2>Коды ошибок и диагностика</h2>
          <ul>
            <li>
              <code>400 Bad Request</code> — невалидный JSON или отсутствует поле <code>message</code>.
            </li>
            <li>
              <code>401/403</code> — отсутствует или некорректный <code>X-Agent-API-Key</code>.
            </li>
            <li>
              <code>429</code> — превышен лимит запросов, добавьте ретраи с паузой.
            </li>
            <li>
              <code>5xx</code> — временная ошибка сервера, повторите запрос с экспоненциальной задержкой.
            </li>
          </ul>
          <p>
            Для диагностики сохраняйте <code>status code</code>, тело ответа и <code>request id</code> (если передается в
            заголовках) в логах интеграции.
          </p>
        </section>

        <section id="api-js-example">
          <h2>Пример подключения на JavaScript</h2>
          <pre>
            <code>{JS_EXAMPLE}</code>
          </pre>
        </section>

        <section id="api-python-example">
          <h2>Пример подключения на Python</h2>
          <pre>
            <code>{PYTHON_EXAMPLE}</code>
          </pre>
        </section>

        <section id="production-tips">
          <h2>Рекомендации для production</h2>
          <ul>
            <li>Храните API-ключи в секретах (env, vault), а не в клиентском коде.</li>
            <li>Добавьте rate-limit и логирование на вашем промежуточном backend.</li>
            <li>Настройте ретраи и timeout на внешних вызовах API.</li>
            <li>Отслеживайте ошибки 401/403/502 и строьте алерты по метрикам.</li>
          </ul>
        </section>
      </article>
    </div>
  );
};

const DocumentationPage = () => {
  return (
    <MainLayout>
      <DocumentationContent />
    </MainLayout>
  );
};

export default DocumentationPage;
