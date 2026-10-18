import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customSasha.css';

const CopyField = ({ id, label, value, hint }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    if (!value) {
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" value={value || ''} readOnly />
      {hint ? <span className="form-hint">{hint}</span> : null}
      <div className="settings-actions">
        <button type="button" className="btn btn-outline" onClick={handleCopy} disabled={!value}>
          {copied ? 'Скопировано' : 'Копировать'}
        </button>
      </div>
    </div>
  );
};

const SASHA_FORMATS = [
  { value: 'api', label: 'API (рекомендуется) — теги и дополнительные поля' },
  { value: 'dmp', label: 'DMP — формат dmp.one, сайт становится тегом' },
];

const CustomAutomationDmpConnectionPage = () => {
  const { id } = useParams();
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [isRotating, setIsRotating] = useState(false);
  const [isSavingSasha, setIsSavingSasha] = useState(false);
  const [isRotatingSasha, setIsRotatingSasha] = useState(false);
  const [sashaForm, setSashaForm] = useState({
    sasha_upload_url: '',
    sasha_upload_format: 'api',
    sasha_hmac_secret: '',
  });

  const loadSettings = useCallback(async () => {
    try {
      const data = await customService.getAutomationSettings(id);
      setSettings(data);
      setSashaForm({
        sasha_upload_url: data.sasha_upload_url || '',
        sasha_upload_format: data.sasha_upload_format || 'api',
        sasha_hmac_secret: '',
      });
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить подключение');
    }
  }, [id]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleRotate = async () => {
    if (!window.confirm('Выпустить новый секрет? Старый URL перестанет работать.')) {
      return;
    }
    setIsRotating(true);
    setMessage(null);
    try {
      await customService.rotateDmpWebhookSecret(id);
      setMessage('Секрет обновлён');
      await loadSettings();
    } catch (err) {
      setError(err.message || 'Не удалось обновить секрет');
    } finally {
      setIsRotating(false);
    }
  };

  const handleSaveSasha = async () => {
    setIsSavingSasha(true);
    setMessage(null);
    setError(null);
    try {
      const payload = {
        sasha_upload_url: sashaForm.sasha_upload_url,
        sasha_upload_format: sashaForm.sasha_upload_format,
        is_sasha_ai_enabled: true,
      };
      if (sashaForm.sasha_hmac_secret) {
        payload.sasha_hmac_secret = sashaForm.sasha_hmac_secret;
      }
      await customService.saveSashaConnection(id, payload);
      setMessage('Sasha AI сохранена');
      await loadSettings();
    } catch (err) {
      setError(err.message || 'Не удалось сохранить Sasha AI');
    } finally {
      setIsSavingSasha(false);
    }
  };

  const handleRotateSasha = async () => {
    if (!window.confirm('Выпустить новый входящий секрет Sasha AI? Старый URL перестанет принимать звонки.')) {
      return;
    }
    setIsRotatingSasha(true);
    setMessage(null);
    try {
      await customService.rotateSashaWebhookSecret(id);
      setMessage('Входящий секрет Sasha AI обновлён — замените URL в колл-листе');
      await loadSettings();
    } catch (err) {
      setError(err.message || 'Не удалось обновить секрет Sasha AI');
    } finally {
      setIsRotatingSasha(false);
    }
  };

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Подключение DMP</h1>
          <p>Сначала принимаем номера из DMP.one. Номер с телефоном уходит в Sasha AI, результат звонка возвращается сюда и в Telegram-бот.</p>
        </div>
      </div>
      {message ? <p className="form-hint">{message}</p> : null}
      {error ? <p className="form-hint">{error}</p> : null}
      <div className="ubt-panel">
        <h2>DMP.one</h2>
        <p className="form-hint">Приём номеров из DMP.one на наш сервис.</p>
        <CopyField
          id="dmp-webhook-url"
          label="Webhook URL"
          value={settings?.dmp_webhook_url || ''}
          hint="Вставьте в DMP One → Интеграция, формат JSON."
        />
        <CopyField
          id="dmp-webhook-secret"
          label="API / webhook-секрет"
          value={settings?.dmp_webhook_secret || ''}
          hint="Этот секрет подписывает входящие номера. Исходящий API-ключ DMP живёт в окружении сервера."
        />
        <div className="settings-actions">
          <button type="button" className="btn btn-outline" onClick={handleRotate} disabled={isRotating}>
            {isRotating ? '...' : 'Новый секрет'}
          </button>
        </div>
      </div>

      <div className="ubt-panel">
        <h2>Sasha AI</h2>
        <p className="form-hint">
          Сервис получает номера из DMP и передаёт их в колл-лист Саши. После звонка Саша возвращает диалог сюда, и договорённость уходит в Telegram-бот той же карточкой, что лиды из чатов.
        </p>
        <ol className="sasha-steps">
          <li>
            В Sasha AI откройте колл-лист и создайте интеграцию типа API или DMP.
            Скопируйте URL вида <code>/api/upload-contacts-integrations/webhook/…</code>
            {' '}
            (<a href="https://docs.trysasha.ru/api-ref/contact-transfer" target="_blank" rel="noreferrer">документация</a>).
          </li>
          <li>Вставьте этот URL ниже — новые номера из DMP уйдут в колл-лист автоматически.</li>
          <li>
            Создайте исходящий вебхук колл-листа на наш URL с типом <code>api</code> и событием <code>call_result</code>
            {' '}
            (<a href="https://docs.trysasha.ru/api-ref/webhooks/rest-api" target="_blank" rel="noreferrer">документация</a>).
          </li>
          <li>Секрет HMAC показывается в Саше один раз — вставьте его сюда, чтобы отсекать подделки.</li>
        </ol>
        <div className="form-group">
          <label htmlFor="sasha-upload-url">Webhook загрузки контактов</label>
          <input
            id="sasha-upload-url"
            type="text"
            placeholder="https://platform.trysasha.ru/api/upload-contacts-integrations/webhook/…"
            value={sashaForm.sasha_upload_url}
            onChange={(e) => setSashaForm((prev) => ({ ...prev, sasha_upload_url: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label htmlFor="sasha-format">Формат отправки</label>
          <CustomSelect
            id="sasha-format"
            value={sashaForm.sasha_upload_format}
            options={SASHA_FORMATS}
            onChange={(e) => setSashaForm((prev) => ({ ...prev, sasha_upload_format: e.target.value }))}
          />
        </div>
        <CopyField
          id="sasha-inbound-url"
          label="Наш webhook для результатов звонков"
          value={settings?.sasha_webhook_url || ''}
          hint="Этот адрес укажите в Sasha AI → вебхуки колл-листа, тип api, событие call_result."
        />
        <div className="form-group">
          <label htmlFor="sasha-hmac">HMAC-секрет из Sasha AI</label>
          <input
            id="sasha-hmac"
            type="password"
            autoComplete="off"
            placeholder={settings?.sasha_hmac_secret_set ? 'Секрет сохранён — вставьте новый, чтобы заменить' : 'Секрет из ответа при создании вебхука'}
            value={sashaForm.sasha_hmac_secret}
            onChange={(e) => setSashaForm((prev) => ({ ...prev, sasha_hmac_secret: e.target.value }))}
          />
        </div>
        <div className="settings-actions">
          <button type="button" className="btn btn-black" onClick={handleSaveSasha} disabled={isSavingSasha}>
            {isSavingSasha ? 'Сохранение...' : 'Сохранить Sasha AI'}
          </button>
          <button type="button" className="btn btn-outline" onClick={handleRotateSasha} disabled={isRotatingSasha}>
            {isRotatingSasha ? '...' : 'Новый входящий секрет'}
          </button>
          <Link className="btn btn-outline" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP_SASHA(id)}>К результатам прозвона</Link>
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationDmpConnectionPage;
