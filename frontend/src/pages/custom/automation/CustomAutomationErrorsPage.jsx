import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import '../../../styles/projectCRMPage.css';
import '../../../styles/projectSettingsPage.css';

const ACTION_FILTERS = [
  { value: '', label: 'Все блоки' },
  { value: 'join_chat', label: 'Вступление' },
  { value: 'neurocommenting', label: 'Нейрокомментинг' },
  { value: 'shilling_chat', label: 'Шиллинг в чате' },
  { value: 'shilling_post', label: 'Шиллинг в комментариях' },
  { value: 'dm', label: 'Перехват заявок' },
  { value: 'dmp_outreach', label: 'DMP.one' },
  { value: 'lead_warmup', label: 'Прогрев лида' },
  { value: 'inbound_dm', label: 'Входящее ЛС' },
  { value: 'discussion', label: 'Цифровой след' },
];

const PAGE_SIZE = 50;

function formatDate(value) {
  if (!value) {
    return '';
  }
  return new Date(value).toLocaleString('ru-RU');
}

const CustomAutomationErrorsPage = () => {
  const { id } = useParams();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actionType, setActionType] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadErrors = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await customService.getAutomationErrors(id, {
        actionType: actionType || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setItems(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить ошибки');
    } finally {
      setIsLoading(false);
    }
  }, [id, actionType, offset]);

  useEffect(() => {
    loadErrors();
  }, [loadErrors]);

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h2>Баги и ошибки</h2>
        <p className="settings-subtitle">Один блок — одна ошибка: что делали, что пошло не так, технический контекст.</p>
      </div>

      <div className="activity-filters">
        <div className="form-group">
          <label htmlFor="error-filter">Блок</label>
          <CustomSelect
            id="error-filter"
            value={actionType}
            options={ACTION_FILTERS}
            onChange={(e) => {
              setOffset(0);
              setActionType(e.target.value);
            }}
          />
        </div>
      </div>

      {error ? <p className="form-hint form-hint--error">{error}</p> : null}

      {isLoading ? (
        <div className="crm-empty-list"><p>Загрузка...</p></div>
      ) : items.length === 0 ? (
        <div className="crm-empty-list">
          <p>Ошибок пока нет</p>
          <span>Здесь появятся сбои вступления, отправки сообщений и других действий.</span>
        </div>
      ) : (
        <div className="crm-list">
          {items.map((item) => (
            <div key={item.id} className="crm-item">
              <div className="crm-item-header">
                <h5 className="crm-item-title">{item.action_label}</h5>
                <span className="crm-status crm-status--cancelled">{item.result}</span>
              </div>
              <p className="crm-item-subtitle">
                {formatDate(item.created_at)}
                {item.account ? ` · ${item.account}` : ''}
                {item.chat_title ? ` · ${item.chat_title}` : ''}
              </p>
              {item.error_message ? (
                <p className="crm-item-subtitle form-hint--error">{item.error_message}</p>
              ) : null}
              <div className="crm-item-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                >
                  {expandedId === item.id ? 'Скрыть' : 'Подробнее'}
                </button>
              </div>
              {expandedId === item.id ? (
                <pre className="management-log-pre" style={{ marginTop: '0.75rem', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(item.context || {}, null, 2)}
                </pre>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {total > PAGE_SIZE ? (
        <div className="settings-actions">
          <button
            type="button"
            className="btn btn-outline"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Назад
          </button>
          <button
            type="button"
            className="btn btn-outline"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Дальше
          </button>
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationErrorsPage;
