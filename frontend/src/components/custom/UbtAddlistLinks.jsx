import React, { useEffect, useState } from 'react';
import customService from '../../services/customService';

const UbtAddlistLinks = ({ automationId, taskKey, emptyText }) => {
  const [items, setItems] = useState([]);
  const [copied, setCopied] = useState('');
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    customService.getTaskAddlists(automationId).then((data) => {
      if (cancelled) {
        return;
      }
      const rows = data.items || [];
      setItems(taskKey ? rows.filter((item) => item.task_key === taskKey) : rows);
      setLoaded(true);
    }).catch(() => {
      if (!cancelled) {
        setItems([]);
        setLoaded(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [automationId, taskKey]);

  if (!items.length) {
    if (!emptyText || !loaded) {
      return null;
    }
    return <p className="nc-muted">{emptyText}</p>;
  }

  return (
    <div className="nc-addlists">
      <div className="nc-muted">Собранные addlist-ссылки — можно скопировать и открыть папку в Telegram</div>
      {items.map((item) => (
        <div key={`${item.url}-${item.account_id}`} className="nc-addlist-row">
          <a href={item.url} target="_blank" rel="noreferrer">{item.url}</a>
          <span className="nc-muted">{item.chat_count} чатов{item.task_title ? ` · ${item.task_title}` : ''}</span>
          <button
            type="button"
            className="acc-btn acc-btn--ghost"
            onClick={() => navigator.clipboard.writeText(item.url).then(() => setCopied(item.url))}
          >
            {copied === item.url ? 'Скопировано' : 'Копировать'}
          </button>
        </div>
      ))}
    </div>
  );
};

export default UbtAddlistLinks;
