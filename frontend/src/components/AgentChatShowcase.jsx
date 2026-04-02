/**
 * Demo чата: клиент и ИИ-администратор. Количество сообщений фиксировано,
 * список сообщений при загрузке прокручивается вниз к последнему ответу.
 */
import React, { useLayoutEffect, useRef } from 'react';
import '../styles/agentChatShowcase.css';

const PERKS = [
  'Ответ за минуту',
  'Опирается на ваши документы',
  'Круглосуточно',
  'В вашем фирменном тоне',
];

const CHAT_BY_VARIANT = {
  main: [
    {
      side: 'client',
      author: 'Клиент',
      text: 'Добрый вечер! Заказ №4821, доставка до ПВЗ «Северная» — можно ли перенести доставку на завтра и какая будет стоимость?',
      time: '18:40',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Добрый вечер! Перенос на завтра для заказа №4821 уже возможен и без доплаты: посылка еще на складе и не ушла в маршрут. Поставил дату на завтра, слот 10:00-14:00. Если нужен другой ПВЗ, пришлите адрес или номер отделения - сразу подберу по вашему регламенту доставки.',
      time: '18:41',
    },
    {
      side: 'client',
      author: 'Клиент',
      text: 'Отлично, подтверждаю. Нужно ли что-то дополнительно с моей стороны?',
      time: '18:41',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Ничего дополнительно не требуется. За 30 минут до доставки отправлю статус и контакт курьера в этот чат.',
      time: '18:42',
    },
    {
      side: 'client',
      author: 'Клиент',
      text: 'Супер, спасибо!',
      time: '18:42',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Рад помочь. Если захотите поменять слот или адрес ПВЗ, напишите сюда в любое время.',
      time: '18:42',
    },
  ],
  auth: [
    {
      side: 'client',
      author: 'Клиент',
      text: 'Добрый вечер! Заказ №4821, доставка до ПВЗ «Северная» — можно ли перенести доставку на завтра и какая будет стоимость?',
      time: '18:40',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Добрый вечер! Перенос на завтра для заказа №4821 уже возможен и без доплаты: посылка еще на складе и не ушла в маршрут. Поставил дату на завтра, слот 10:00-14:00.',
      time: '18:41',
    },
    {
      side: 'client',
      author: 'Клиент',
      text: 'Отлично, оставляем этот слот. И можно коротко сообщить, как получить заказ в ПВЗ?',
      time: '18:41',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Конечно: паспорт или код из СМС, хранение 5 дней, продление еще на 3 дня через чат. Если заберет другой человек, оформлю доверенность по шаблону вашей компании.',
      time: '18:42',
    },
    {
      side: 'client',
      author: 'Клиент',
      text: 'Понял, спасибо. Подтвердите тогда доставку на завтра 10:00-14:00.',
      time: '18:42',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Подтвердил. Статус уже обновлен в CRM и Telegram, напомню вам утром автоматически.',
      time: '18:43',
    },
    {
      side: 'client',
      author: 'Клиент',
      text: 'Отлично, этого достаточно.',
      time: '18:43',
    },
    {
      side: 'agent',
      author: 'ИИ-администратор',
      text: 'Принято. Я на связи 24/7, если появятся вопросы по заказу.',
      time: '18:43',
    },
  ],
};

/**
 * @param {{ tone?: 'light' | 'glass', variant?: 'main' | 'auth', className?: string }} props
 */
function AgentChatShowcase({ tone = 'light', variant = 'main', className = '' }) {
  const messagesRef = useRef(null);
  const allMessages = CHAT_BY_VARIANT[variant] ?? CHAT_BY_VARIANT.main;
  const rootClass =
    tone === 'glass'
      ? 'agent-chat-showcase agent-chat-showcase--glass'
      : 'agent-chat-showcase agent-chat-showcase--light';

  useLayoutEffect(() => {
    const scroller = messagesRef.current;
    if (!scroller) return;

    const scrollToBottom = () => {
      scroller.scrollTop = scroller.scrollHeight;
    };

    scrollToBottom();
    requestAnimationFrame(scrollToBottom);
  }, [variant]);

  return (
    <section
      className={`${rootClass} ${className}`.trim()}
      aria-label="Пример диалога: клиент и ИИ-администратор бизнеса"
    >
      <header className="agent-chat-showcase__header">
        <div className="agent-chat-showcase__title-row">
          <span className="agent-chat-showcase__title">Клиент ID: 133</span>
        </div>
        <span className="agent-chat-showcase__status">в сети</span>
      </header>

      <div className="agent-chat-showcase__thread">
        <div className="agent-chat-showcase__messages" ref={messagesRef}>
          {allMessages.map((message, index) => (
            <article key={`${message.side}-${message.time}-${index}`} className={`agent-chat-showcase__msg agent-chat-showcase__msg--${message.side}`}>
              <div className="agent-chat-showcase__msg-top">
                <span className="agent-chat-showcase__author">{message.author}</span>
                <span className="agent-chat-showcase__time">{message.time}</span>
              </div>
              <p>{message.text}</p>
            </article>
          ))}
        </div>
        <div className="agent-chat-showcase__thread-perks" aria-label="Преимущества агента">
          <ul className="agent-chat-showcase__perks">
            {PERKS.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export default AgentChatShowcase;
