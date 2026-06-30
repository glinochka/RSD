import React, { useEffect, useMemo, useState } from 'react';
import MainLayout from '../components/Layout';
import '../styles/documentationPage.css';

const SECTIONS = [
  { id: 'quick-start', title: 'Быстрый старт' },
  { id: 'create-project', title: 'Создание проекта' },
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
  { id: 'api-projects', title: 'API проектов' },
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
    body: JSON.stringify({
      message,
      external_user_id: 'site-user-42',
      external_user_name: 'Иван'
    })
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
        json={
            "message": message,
            "external_user_id": "site-user-42",
            "external_user_name": "Иван",
        },
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
  -d '{"message":"Подскажите стоимость внедрения","external_user_id":"site-user-42","external_user_name":"Иван"}'`;

const WIDGET_CONNECTOR_EXAMPLE = `<script
  src="https://rsd-ai.ru/api/agents/external/widget.js"
  data-rsd-widget="1"
  data-api-base="https://rsd-ai.ru"
  data-api-key="agnt_xxxxxxxxxxxxxxxxxxxxxxxxx"

  data-position="bottom-right"
  data-title="Онлайн-консультант"
  data-greeting="Здравствуйте! Чем могу помочь?"
  data-placeholder="Напишите ваш вопрос..."
  data-open="false"
  data-user-id="crm-contact-42"
  data-user-name="Иван Петров"

  data-theme="dark"

  data-proactive-message="Добрый день! Чем могу помочь?"
  data-proactive-delay="3"
  data-proactive-message-2="Готов ответить на любые вопросы"
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

        <section id="create-project">
          <h2>Создание проекта</h2>
          <p>
            Проект — это контейнер для цифровизации вашего бизнеса. В рамках проекта вы создаете ИИ-агентов,
            управляете общей базой знаний, настраиваете сайт и отслеживаете все процессы в едином дашборде.
          </p>
          <h3>Создание через AI-мастера (рекомендуется)</h3>
          <ol>
            <li>Нажмите «Создать проект» на главной или в разделе «Проекты».</li>
            <li>Заполните краткий бриф: название бизнеса, отрасль, цели автоматизации, каналы коммуникации.</li>
            <li>AI сгенерирует рекомендуемую структуру: какие агенты нужны, какие документы загрузить, какой сайт создать.</li>
            <li>Просмотрите план и выберите, что создать: агентов, сайт, оба компонента.</li>
            <li>Проект создается автоматически со всеми выбранными компонентами.</li>
          </ol>
          <h3>Создание вручную</h3>
          <ol>
            <li>Перейдите в «Проекты» и нажмите «Создать проект вручную».</li>
            <li>Укажите название и выберите отрасль (для рекомендаций AI).</li>
            <li>После создания добавляйте агентов и сайт по отдельности.</li>
          </ol>
          <p>
            <strong>Совет:</strong> Используйте AI-мастер для быстрого старта — он подскажет лучшие практики
            для вашей отрасли и не даст забыть важные шаги (подключение CRM, загрузка прайс-листа и т.д.).
          </p>
        </section>

        <section id="create-agent">
          <h2>Создание агента</h2>
          <p>
            Агенты создаются в контексте проекта. Каждый агент привязан к проекту и имеет доступ
            к общей базе знаний проекта.
          </p>
          <h3>Создание через проект</h3>
          <ol>
            <li>Перейдите в проект и откройте раздел «Агенты».</li>
            <li>Нажмите «Добавить агента» и выберите шаблон: Консультант, Администратор, Менеджер продаж или Контент-завод.</li>
            <li>Выберите тип подключения. Для «ИИ МОП» — Telegram юзербот и/или WhatsApp юзербот, для «Контент-завода» — только YouTube.</li>
            <li>Заполните обязательные поля выбранного канала (например, bot token / userbot / CRM-параметры), затем задайте системный промпт.</li>
            <li>Сохраните агента — он автоматически привяжется к текущему проекту.</li>
          </ol>
          <h3>Создание вне проекта (legacy)</h3>
          <p>
            При создании агента без выбора проекта он автоматически привяжется к вашему дефолтному проекту.
            Это обеспечивает обратную совместимость со старыми закладками и интеграциями.
          </p>
          <p>
            Для внешнего endpoint чата и виджета поддерживаются шаблоны <code>qa</code> и <code>crm_admin</code>. Для остальных шаблонов используйте профильные каналы интеграции.
          </p>
          <p>
            <strong>Совет:</strong> в промпте фиксируйте роль агента, границы компетенции и правила эскалации к оператору. Это снижает количество неоднозначных ответов.
          </p>
        </section>

        <section id="knowledge-base">
          <h2>База знаний</h2>
          <h3>База знаний проекта (рекомендуется)</h3>
          <p>
            Загружайте документы в разделе «База знаний» проекта. Все документы проекта автоматически
            доступны всем агентам этого проекта — не нужно дублировать файлы для каждого агента.
          </p>
          <ol>
            <li>Откройте проект и перейдите в раздел «База знаний».</li>
            <li>Загрузите файлы (PDF, DOCX, TXT) или добавьте ссылки на документы.</li>
            <li>Дождитесь статуса «Готов» — документы проиндексированы и доступны агентам.</li>
            <li>При необходимости переиндексируйте или удалите устаревшие документы.</li>
          </ol>
          <h3>База знаний агента (legacy)</h3>
          <p>
            При создании агента внутри проекта он автоматически получает доступ к базе знаний проекта.
            Ручное управление документами в карточке агента больше не требуется.
          </p>
          <h3>Рекомендации</h3>
          <ul>
            <li>Поддерживайте документы в актуальном состоянии.</li>
            <li>Удаляйте устаревшие файлы, чтобы избежать противоречий.</li>
            <li>Загружайте прайс-листы, регламенты и FAQ на уровне проекта.</li>
            <li>AI-мастер при создании проекта подскажет, какие документы рекомендуется загрузить.</li>
          </ul>
        </section>

        <section id="scenarios">
          <h2>Сценарии использования</h2>
          <h3>1) Консультант на сайте через виджет</h3>
          <p>
            Используйте шаблон <code>qa</code> или <code>crm_admin</code>, вставьте script виджета и передавайте стабильный идентификатор
            пользователя (через <code>data-user-id</code> или авто-генерацию). Сценарий подходит для FAQ, поддержки и первичной квалификации.
          </p>
          <h3>2) Внешняя интеграция через backend API</h3>
          <p>
            Отправляйте запросы в <code>POST /api/agents/external/chat</code> от своего сервера: обязательны{' '}
            <code>X-Agent-API-Key</code>, <code>message</code> и <code>external_user_id</code> (или <code>chat_id</code>).
            Подходит для CRM/ERP, внутренних кабинетов и омниканальной маршрутизации.
          </p>
          <h3>3) Администратор с CRM-функциями</h3>
          <p>
            Шаблон <code>crm_admin</code> может работать как администратор салона/клиники: отвечать клиенту и выполнять
            разрешенные CRM-действия после настройки провайдера и прав.
          </p>
          <h3>4) ИИ МОП в мессенджерах</h3>
          <p>
            Для сценария outbound/inbound-продаж используйте шаблон <code>sales_manager</code> с каналом Telegram юзербот
            и/или WhatsApp юзербот. Этот режим не предназначен для внешнего endpoint чата и сайт-виджета.
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
          <p>
            Ключ можно скопировать или перевыпустить в карточке агента в разделе «Мои агенты».
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
            <strong>Body:</strong>{' '}
            <code>{'{ "message": "Ваш вопрос", "external_user_id": "site-user-42", "external_user_name": "Иван" }'}</code>
            <br />
            Поля <code>message</code> и <code>external_user_id</code> (или <code>chat_id</code>) обязательны.
          </p>
          <p>
            Endpoint доступен только для шаблонов <code>qa</code> и <code>crm_admin</code>.
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
              <code>message</code> (<code>string</code>, обязательно, 1..4000) — текст сообщения пользователя.
            </li>
            <li>
              <code>external_user_id</code> (<code>string</code>, обязательно, до 128) — ID пользователя/чата во внешней системе.
            </li>
            <li>
              <code>chat_id</code> (<code>string</code>, опционально, до 128) — алиас для <code>external_user_id</code>, если удобнее
              использовать терминологию вашей системы.
            </li>
            <li>
              <code>external_user_name</code> (<code>string</code>, опционально, до 128) — отображаемое имя пользователя для аналитики.
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
            <strong>Обязательные параметры:</strong> <code>data-rsd-widget="1"</code>, <code>data-api-base</code>, <code>data-api-key</code>.
          </p>
          <p>
            <strong>Параметры UI:</strong> <code>data-title</code>, <code>data-greeting</code>, <code>data-placeholder</code>,{' '}
            <code>data-position</code> (<code>bottom-right</code> по умолчанию, поддерживается <code>bottom-left</code>),{' '}
            <code>data-open</code> (<code>true/false</code>, открыть чат сразу).
          </p>
          <p>
            <strong>Контекст пользователя:</strong> <code>data-user-id</code> (если не передан, виджет генерирует локальный ID),{' '}
            <code>data-user-name</code> (опционально).
          </p>
          <p>
            <strong>Исходящие сообщения</strong> — всплывающий пузырёк над кнопкой чата. Первое сообщение:{' '}
            <code>data-proactive-message</code> + <code>data-proactive-delay</code> (секунды, по умолчанию 3). Второе сообщение:{' '}
            <code>data-proactive-message-2</code> + <code>data-proactive-delay-2</code> (секунды после первого, по умолчанию 1). Оба необязательны.
            Для совместимости также поддерживается legacy-параметр <code>data-proactive-delay-ms</code>.
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
              <code>401 Unauthorized</code> — отсутствует или некорректный <code>X-Agent-API-Key</code>.
            </li>
            <li>
              <code>403 Forbidden</code> — агент выключен или используется шаблон, для которого внешний чат недоступен.
            </li>
            <li>
              <code>422 Unprocessable Entity</code> — невалидное тело запроса, пустой <code>message</code> или не передан{' '}
              <code>external_user_id</code>/<code>chat_id</code>.
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

        <section id="api-projects">
          <h2>API проектов</h2>
          <p>
            API проектов позволяет управлять структурой цифровизации вашего бизнеса: создавать проекты,
            управлять агентами в их контексте, загружать общую базу знаний и отслеживать статистику.
          </p>

          <h3>Основные endpoints</h3>
          <ul>
            <li>
              <code>GET /api/projects</code> — список проектов пользователя.
            </li>
            <li>
              <code>POST /api/projects</code> — создание проекта.
            </li>
            <li>
              <code>GET /api/projects/{'{id}'}</code> — детали проекта.
            </li>
            <li>
              <code>PATCH /api/projects/{'{id}'}</code> — обновление проекта.
            </li>
            <li>
              <code>DELETE /api/projects/{'{id}'}</code> — архивация проекта.
            </li>
            <li>
              <code>GET /api/projects/{'{id}'}/dashboard</code> — дашборд проекта (статистика, чеклист).
            </li>
            <li>
              <code>GET /api/projects/{'{id}'}/agents</code> — агенты проекта.
            </li>
            <li>
              <code>GET /api/projects/{'{id}'}/documents</code> — документы базы знаний.
            </li>
            <li>
              <code>POST /api/projects/{'{id}'}/documents</code> — загрузка документа.
            </li>
          </ul>

          <h3>AI-мастер создания проекта</h3>
          <ul>
            <li>
              <code>POST /api/projects/ai/generate-plan</code> — генерация плана проекта на основе брифа.
            </li>
            <li>
              <code>POST /api/projects/ai/apply-plan</code> — применение плана (создание агентов и сайта).
            </li>
          </ul>

          <h3>Авторизация</h3>
          <p>
            Все запросы к API проектов требуют JWT токен в заголовке{' '}
            <code>Authorization: Bearer {'{token}'}</code>.
          </p>

          <h3>Пример: создание проекта</h3>
          <pre>
            <code>{`curl -X POST "https://rsd-ai.ru/api/projects" \\
  -H "Authorization: Bearer {jwt_token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Мой салон красоты",
    "industry": "beauty",
    "description": "Автоматизация записи клиентов"
  }'`}</code>
          </pre>

          <h3>Пример: загрузка документа в проект</h3>
          <pre>
            <code>{`curl -X POST "https://rsd-ai.ru/api/projects/123/documents" \\
  -H "Authorization: Bearer {jwt_token}" \\
  -F "file=@price.pdf"`}</code>
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
