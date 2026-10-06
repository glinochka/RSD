import React, { useCallback, useEffect, useState } from 'react';
import CustomSelect from '../../../components/CustomSelect';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';

const DIRECTION_OPTIONS = [
  { value: 'outbound', label: 'Исходящий: мы вызываем URL' },
  { value: 'inbound', label: 'Входящий: нам шлют запрос' },
];

const EVENT_OPTIONS = [
  { value: 'lead.created', label: 'Новый лид' },
  { value: 'lead.qualified', label: 'Лид квалифицирован' },
  { value: 'lead.transferred', label: 'Лид передан' },
  { value: 'lead.lost', label: 'Лид потерян' },
];

const FIELD_OPTIONS = [
  { value: 'lead_id', label: 'lead_id' },
  { value: 'contact_value', label: 'contact_value' },
  { value: 'contact_type', label: 'contact_type' },
  { value: 'full_name', label: 'full_name' },
  { value: 'company', label: 'company' },
  { value: 'position', label: 'position' },
  { value: 'status', label: 'status' },
  { value: 'source', label: 'source' },
  { value: 'automation_id', label: 'automation_id' },
  { value: 'automation_name', label: 'automation_name' },
];

const emptyForm = () => ({
  id: null,
  name: '',
  enabled: true,
  direction: 'outbound',
  event: 'lead.transferred',
  url: '',
  secret_header: 'X-Webhook-Secret',
  secret: '',
  mappings: [{ source: 'contact_value', target: 'phone' }],
});

const CustomAutomationWebhookConstructor = ({ automationId, onError, onMessage }) => {
  const [routes, setRoutes] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const data = await customService.listIntegrationRoutes(automationId);
    setRoutes(data.items || []);
  }, [automationId]);

  useEffect(() => {
    load().catch((err) => onError(err.message || 'Не удалось загрузить маршруты'));
  }, [load, onError]);

  const patch = (partial) => setForm((prev) => ({ ...prev, ...partial }));

  const patchMapping = (index, partial) => {
    setForm((prev) => ({
      ...prev,
      mappings: prev.mappings.map((row, rowIndex) => (rowIndex === index ? { ...row, ...partial } : row)),
    }));
  };

  const handleEdit = (route) => {
    setForm({
      id: route.id,
      name: route.name,
      enabled: Boolean(route.enabled),
      direction: route.direction,
      event: route.event,
      url: route.url || '',
      secret_header: route.secret_header || 'X-Webhook-Secret',
      secret: route.secret || '',
      mappings: route.mappings?.length ? route.mappings : [{ source: 'contact_value', target: 'phone' }],
    });
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await customService.saveIntegrationRoute(automationId, {
        id: form.id || undefined,
        name: form.name,
        enabled: form.enabled,
        direction: form.direction,
        event: form.event,
        url: form.direction === 'outbound' ? form.url : undefined,
        secret_header: form.secret_header,
        secret: form.secret || undefined,
        mappings: form.mappings.filter((row) => row.source && row.target),
      });
      onMessage(form.id ? 'Маршрут обновлён' : 'Маршрут сохранён');
      setForm(emptyForm());
      await load();
    } catch (err) {
      onError(err.message || 'Не удалось сохранить маршрут');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (routeId) => {
    if (!window.confirm('Удалить маршрут?')) {
      return;
    }
    setBusy(true);
    try {
      await customService.deleteIntegrationRoute(automationId, routeId);
      onMessage('Маршрут удалён');
      if (form.id === routeId) {
        setForm(emptyForm());
      }
      await load();
    } catch (err) {
      onError(err.message || 'Не удалось удалить маршрут');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="int-form">
      <div>
        <h2>Конструктор интеграций</h2>
        <p className="form-hint">
          Для других инструментов: что отправляем, куда, по какому пути и с каким секретом.
          Исходящий маршрут бьёт в чужой URL. Входящий даёт URL, на который можно слать лиды к нам.
        </p>
      </div>

      {routes.length ? (
        <div className="int-routes">
          {routes.map((route) => (
            <div key={route.id} className="int-route">
              <div>
                <strong>{route.name}</strong>
                <span>
                  {route.direction === 'inbound' ? 'Входящий' : 'Исходящий'} · {route.event}
                  {route.enabled ? '' : ' · выкл'}
                </span>
              </div>
              <div className="int-route-actions">
                <button type="button" className="acc-btn acc-btn--ghost" onClick={() => handleEdit(route)}>Изменить</button>
                <button type="button" className="acc-btn acc-btn--ghost" onClick={() => handleDelete(route.id)} disabled={busy}>Удалить</button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="ubt-empty">Пока нет своих маршрутов — соберите первый ниже.</p>
      )}

      <form onSubmit={handleSave}>
        <div className="form-group">
          <label htmlFor="int-name">Название</label>
          <input id="int-name" value={form.name} onChange={(event) => patch({ name: event.target.value })} placeholder="Bitrix24, Slack, своя CRM..." required />
        </div>
        <FeatureToggle
          compact
          title={form.enabled ? 'Маршрут включён' : 'Маршрут выключен'}
          checked={form.enabled}
          onChange={(value) => patch({ enabled: value })}
        />
        <div className="form-group">
          <label>Направление</label>
          <CustomSelect
            value={form.direction}
            options={DIRECTION_OPTIONS}
            onChange={(event) => patch({ direction: event.target.value })}
          />
        </div>
        {form.direction === 'outbound' ? (
          <>
            <div className="form-group">
              <label>Событие</label>
              <CustomSelect
                value={form.event}
                options={EVENT_OPTIONS}
                onChange={(event) => patch({ event: event.target.value })}
              />
            </div>
            <div className="form-group">
              <label htmlFor="int-url">URL</label>
              <input id="int-url" value={form.url} onChange={(event) => patch({ url: event.target.value })} placeholder="https://example.com/hooks/leads" required />
            </div>
          </>
        ) : (
          <p className="form-hint">После сохранения появится входящий URL. Секрет можно передать в пути или заголовком.</p>
        )}
        <div className="form-group">
          <label htmlFor="int-header">Заголовок секрета</label>
          <input id="int-header" value={form.secret_header} onChange={(event) => patch({ secret_header: event.target.value })} />
        </div>
        <div className="form-group">
          <label htmlFor="int-secret">Секрет</label>
          <input id="int-secret" value={form.secret} onChange={(event) => patch({ secret: event.target.value })} placeholder="Оставьте пустым — сгенерируем" />
        </div>
        {form.direction === 'inbound' && form.id ? (
          <div className="form-group">
            <label htmlFor="int-inbound">Входящий URL</label>
            <input id="int-inbound" readOnly value={routes.find((item) => item.id === form.id)?.inbound_url || ''} />
          </div>
        ) : null}

        <h3>Соответствие полей</h3>
        <p className="form-hint">
          {form.direction === 'outbound'
            ? 'Слева наше поле, справа путь в JSON у них. Пустой список — отправим весь объект лида.'
            : 'Слева путь в их JSON, справа наше поле. Нужен хотя бы contact_value.'}
        </p>
        {form.mappings.map((row, index) => (
          <div key={`${row.source}-${index}`} className="int-map-row">
            {form.direction === 'outbound' ? (
              <div className="form-group">
                <label>Наше поле</label>
                <CustomSelect
                  value={row.source}
                  options={FIELD_OPTIONS}
                  onChange={(event) => patchMapping(index, { source: event.target.value })}
                />
              </div>
            ) : (
              <div className="form-group">
                <label>Путь у них</label>
                <input value={row.source} onChange={(event) => patchMapping(index, { source: event.target.value })} placeholder="phone или data.email" />
              </div>
            )}
            {form.direction === 'outbound' ? (
              <div className="form-group">
                <label>Путь у них</label>
                <input value={row.target} onChange={(event) => patchMapping(index, { target: event.target.value })} placeholder="phone или contact.email" />
              </div>
            ) : (
              <div className="form-group">
                <label>Наше поле</label>
                <CustomSelect
                  value={row.target}
                  options={FIELD_OPTIONS}
                  onChange={(event) => patchMapping(index, { target: event.target.value })}
                />
              </div>
            )}
            <button
              type="button"
              className="acc-btn acc-btn--ghost"
              onClick={() => setForm((prev) => ({ ...prev, mappings: prev.mappings.filter((_, rowIndex) => rowIndex !== index) }))}
            >
              Убрать
            </button>
          </div>
        ))}
        <div className="settings-actions">
          <button
            type="button"
            className="acc-btn acc-btn--ghost"
            onClick={() => setForm((prev) => ({
              ...prev,
              mappings: [...prev.mappings, { source: form.direction === 'outbound' ? 'full_name' : 'name', target: form.direction === 'outbound' ? 'name' : 'full_name' }],
            }))}
          >
            Добавить поле
          </button>
          <button type="submit" className="acc-btn acc-btn--primary" disabled={busy}>
            {busy ? 'Сохранение...' : form.id ? 'Обновить маршрут' : 'Сохранить маршрут'}
          </button>
          {form.id ? (
            <button type="button" className="acc-btn acc-btn--ghost" onClick={() => setForm(emptyForm())}>Новый</button>
          ) : null}
        </div>
      </form>
    </div>
  );
};

export default CustomAutomationWebhookConstructor;
