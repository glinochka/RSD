import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import customService from '../../../services/customService';
import {
  ACTION_LABELS,
  ACTIVITY_FEED_FILTERS,
  ACTIVITY_FEED_SORT,
  CHAT_TYPE_LABELS,
} from './activityLabels';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

const TYPE_STATUS = {
  neurocommenting: 'crm-status--confirmed',
  chat_monitoring: 'crm-status--pending',
  shilling: 'crm-status--completed',
  discussion: '',
  dmp: 'crm-status--cancelled',
};

const PAGE_SIZE = 20;

function formatDate(value) {
  if (!value) {
    return '';
  }
  return new Date(value).toLocaleString('ru-RU');
}

function chatTitle(item) {
  const title = item.chat?.title;
  if (title) {
    return title;
  }
  const kind = CHAT_TYPE_LABELS[item.chat?.chat_type] || 'Чат';
  return kind;
}

function Quote({ label, text }) {
  if (!text) {
    return null;
  }
  return (
    <div className="activity-quote">
      <span className="activity-quote-label">{label}</span>
      <p>{text}</p>
    </div>
  );
}

function Thread({ messages }) {
  if (!messages?.length) {
    return null;
  }
  return (
    <div className="crm-chat">
      {messages.map((msg, index) => (
        <div
          key={`${msg.sent_at || index}-${index}`}
          className={`crm-chat-row ${msg.direction === 'outgoing' ? 'crm-chat-row--out' : ''}`}
        >
          <div className="crm-chat-bubble">
            <div className="crm-chat-meta">
              {msg.author || (msg.direction === 'outgoing' ? 'Мы' : 'Лид')}
              {msg.sent_at ? ` · ${formatDate(msg.sent_at)}` : ''}
            </div>
            <div>{msg.text}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ActivityBody({ item, automationId }) {
  if (item.activity_type === 'neurocommenting') {
    return (
      <>
        <p className="crm-item-subtitle">
          {chatTitle(item)}
          {item.post_id ? ` · пост #${item.post_id}` : ''}
        </p>
        <Quote label="Пост" text={item.post_text} />
        <Quote label="Комментарий" text={item.comment} />
      </>
    );
  }
  if (item.activity_type === 'chat_monitoring') {
    return (
      <>
        <p className="crm-item-subtitle">
          {chatTitle(item)}
          {item.user_name ? ` · ${item.user_name}` : ''}
        </p>
        <Quote label="Сообщение в чате" text={item.user_message} />
        <Quote label="Ответ в ЛС" text={item.dm_reply} />
        <Thread messages={item.messages} />
        {item.lead_id ? (
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(automationId, item.lead_id)} className="btn btn-outline">
            Переписка
          </Link>
        ) : null}
      </>
    );
  }
  if (item.activity_type === 'shilling') {
    return (
      <>
        <p className="crm-item-subtitle">
          {chatTitle(item)}
          {item.shilling_kind === 'post' ? ' · под постом' : ' · в чате'}
        </p>
        <div className="activity-dialogue">
          <Quote label={item.setup_author || 'Первый'} text={item.setup} />
          <Quote label={item.reply_author || 'Второй'} text={item.reply} />
        </div>
      </>
    );
  }
  if (item.activity_type === 'discussion') {
    return (
      <>
        <p className="crm-item-subtitle">{chatTitle(item)}</p>
        <Quote label={item.user_name ? `Сообщение · ${item.user_name}` : 'Сообщение'} text={item.source_text} />
        <Quote label={item.reply_author ? `Ответ · ${item.reply_author}` : 'Ответ'} text={item.reply} />
      </>
    );
  }
  if (item.activity_type === 'dmp') {
    return (
      <>
        <p className="crm-item-subtitle">
          {[item.lead_name, item.lead_contact, item.lead_company].filter(Boolean).join(' · ') || 'Лид DMP'}
        </p>
        <Thread messages={item.messages} />
        {item.lead_id ? (
          <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEAD_CHAT(automationId, item.lead_id)} className="btn btn-outline">
            Переписка
          </Link>
        ) : null}
      </>
    );
  }
  return null;
}

const CustomAutomationActivityPage = () => {
  const { id } = useParams();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [activityType, setActivityType] = useState('');
  const [sort, setSort] = useState('newest');
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadFeed = useCallback(async (nextOffset) => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationActivity(id, {
        activityType: activityType || undefined,
        sort,
        limit: PAGE_SIZE,
        offset: nextOffset,
      });
      const nextItems = data.items || [];
      setItems((prev) => (nextOffset === 0 ? nextItems : [...prev, ...nextItems]));
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить активность');
    } finally {
      setIsLoading(false);
    }
  }, [id, activityType, sort]);

  useEffect(() => {
    setOffset(0);
    loadFeed(0);
  }, [loadFeed]);

  const handleLoadMore = () => {
    const nextOffset = offset + PAGE_SIZE;
    setOffset(nextOffset);
    loadFeed(nextOffset);
  };

  return (
    <div className="project-crm-page">
      <div className="crm-header">
        <div>
          <h1 className="crm-title">Активность</h1>
          <p className="crm-subtitle">Действия юзерботов в Telegram: один блок — одно событие.</p>
        </div>
        <div className="crm-stats">
          <div className="crm-stat">
            <span className="crm-stat-value">{total}</span>
            <span className="crm-stat-label">Всего</span>
          </div>
        </div>
      </div>

      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="settings-section activity-filters">
        <div className="form-group">
          <label htmlFor="activity-type">Тип</label>
          <CustomSelect
            id="activity-type"
            value={activityType}
            options={ACTIVITY_FEED_FILTERS}
            onChange={(e) => setActivityType(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="activity-sort">Сортировка</label>
          <CustomSelect
            id="activity-sort"
            value={sort}
            options={ACTIVITY_FEED_SORT}
            onChange={(e) => setSort(e.target.value)}
          />
        </div>
      </div>

      {isLoading && items.length === 0 ? (
        <div className="crm-empty-list"><p>Загрузка...</p></div>
      ) : items.length === 0 ? (
        <div className="crm-empty-list">
          <p>Пока нет активности</p>
          <span>Когда юзербот оставит комментарий, перехватит заявку или напишет в чат — блок появится здесь.</span>
        </div>
      ) : (
        <div className="crm-list">
          {items.map((item) => (
            <div key={item.id} className="crm-item">
              <div className="crm-item-header">
                <h5 className="crm-item-title">{ACTION_LABELS[item.activity_type] || item.activity_type}</h5>
                <span className={`crm-status ${TYPE_STATUS[item.activity_type] || ''}`}>
                  {formatDate(item.created_at)}
                </span>
              </div>
              <ActivityBody item={item} automationId={id} />
            </div>
          ))}
        </div>
      )}

      {items.length < total ? (
        <div className="settings-actions">
          <button type="button" className="btn btn-outline" onClick={handleLoadMore} disabled={isLoading}>
            {isLoading ? 'Загрузка...' : 'Ещё'}
          </button>
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationActivityPage;
