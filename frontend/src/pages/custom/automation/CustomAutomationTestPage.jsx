import React, { useCallback, useEffect, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

const formatResult = (value) => {
  if (value == null) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const targetLabel = (target) => {
  if (!target) {
    return 'ещё не создан';
  }
  const name = target.title || target.username || `#${target.id}`;
  return `${name} · ${target.join_status || 'pending'}`;
};

const CustomAutomationTestPage = () => {
  const { id } = useParams();
  const { isAdmin } = useCustomAuth();
  const [lab, setLab] = useState(null);
  const [channelUsername, setChannelUsername] = useState('');
  const [chatUsername, setChatUsername] = useState('');
  const [dmpPhone, setDmpPhone] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  const loadLab = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await customService.getTestLab(id);
      setLab(data);
      setChannelUsername(data.channel_username || '');
      setChatUsername(data.chat_username || '');
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить тест');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (isAdmin) {
      loadLab();
    }
  }, [isAdmin, loadLab]);

  const runAction = async (name, fn, successText) => {
    setBusy(name);
    setError(null);
    setMessage(null);
    try {
      const result = await fn();
      setLastResult(result);
      if (successText) {
        setMessage(successText);
      }
      await loadLab();
      return result;
    } catch (err) {
      setError(err.message || 'Ошибка теста');
      return null;
    } finally {
      setBusy('');
    }
  };

  if (!isAdmin) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(id)} replace />;
  }

  const handleSaveAndJoin = async (e) => {
    e.preventDefault();
    await runAction(
      'save',
      async () => {
        await customService.updateTestLab(id, {
          channel_username: channelUsername,
          chat_username: chatUsername,
        });
        return customService.joinTestLab(id);
      },
      'Цели сохранены, аккаунты вступают без пауз.',
    );
  };

  const handleJoin = () => runAction('join', () => customService.joinTestLab(id), 'Аккаунты вступают в целевые канал и чат.');
  const handleShilling = () => runAction(
    'shilling',
    () => customService.runTestLabShilling(id),
    'Шиллинг запущен в целевом чате (аккаунты с функцией шиллинга).',
  );
  const handleNeuro = () => runAction(
    'neuro',
    () => customService.runTestLabNeurocommenting(id),
    'Проверка постов: нейрокомментинг без задержек.',
  );
  const handleDmp = async (e) => {
    e.preventDefault();
    const phone = dmpPhone.trim();
    if (!phone) {
      setError('Введите номер, как будто он пришёл из DMP');
      return;
    }
    await runAction(
      'dmp',
      () => customService.runTestLabDmp(id, phone),
      'Искусственный DMP: ищем аккаунт с этим номером и пишем от DMP-аккаунта.',
    );
  };

  if (isLoading && !lab) {
    return (
      <div className="project-settings-page">
        <p className="form-hint">Загрузка теста...</p>
      </div>
    );
  }

  return (
    <div className="project-settings-page">
      <div className="settings-header">
        <div>
          <h1 className="settings-title">Тест</h1>
          <p className="settings-subtitle">
            Демо без пауз и лимитов. Клиенту этот раздел не виден.
          </p>
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <form onSubmit={handleSaveAndJoin} className="settings-section">
        <h3 className="settings-section-title">Целевые канал и чат</h3>
        <p className="form-hint">
          Один канал и один чат. После сохранения аккаунты входят и ждут.
          Пост в канал → нейрокомментинг. Шиллинг — отдельной кнопкой в чате.
        </p>
        <div className="form-group">
          <label htmlFor="test-channel">Канал</label>
          <input
            id="test-channel"
            type="text"
            value={channelUsername}
            onChange={(e) => setChannelUsername(e.target.value)}
            placeholder="@channel"
          />
          <span className="form-hint">{targetLabel(lab?.channel)}</span>
        </div>
        <div className="form-group">
          <label htmlFor="test-chat">Чат</label>
          <input
            id="test-chat"
            type="text"
            value={chatUsername}
            onChange={(e) => setChatUsername(e.target.value)}
            placeholder="@chat"
          />
          <span className="form-hint">{targetLabel(lab?.chat)}</span>
        </div>
        <div className="settings-actions">
          <button type="submit" className="btn btn-black" disabled={Boolean(busy)}>
            {busy === 'save' ? 'Вступаем...' : 'Сохранить и вступить'}
          </button>
          <button type="button" className="btn btn-outline" disabled={Boolean(busy)} onClick={handleJoin}>
            {busy === 'join' ? 'Вступаем...' : 'Только вступить'}
          </button>
        </div>
      </form>

      <div className="settings-section">
        <h3 className="settings-section-title">Шиллинг</h3>
        <p className="form-hint">
          Аккаунты с функцией шиллинга пишут в целевом чате фиксированные вопрос и ответ из промптов.
        </p>
        <div className="settings-actions">
          <button type="button" className="btn btn-black" disabled={Boolean(busy)} onClick={handleShilling}>
            {busy === 'shilling' ? 'Шиллим...' : 'Активировать шиллинг'}
          </button>
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Нейрокомментинг</h3>
        <p className="form-hint">
          Опубликуйте пост в целевом канале. Планировщик подхватит его сам; кнопка ниже проверяет сразу.
        </p>
        <div className="settings-actions">
          <button type="button" className="btn btn-outline" disabled={Boolean(busy)} onClick={handleNeuro}>
            {busy === 'neuro' ? 'Проверяем...' : 'Проверить посты'}
          </button>
        </div>
      </div>

      <form onSubmit={handleDmp} className="settings-section">
        <h3 className="settings-section-title">Искусственный DMP</h3>
        <p className="form-hint">
          Введите номер: система ищет аккаунт с этим телефоном и сразу пишет ему от аккаунта с функцией DMP.
        </p>
        <div className="form-group">
          <label htmlFor="test-dmp-phone">Номер</label>
          <input
            id="test-dmp-phone"
            type="text"
            value={dmpPhone}
            onChange={(e) => setDmpPhone(e.target.value)}
            placeholder="+79990000000"
          />
        </div>
        <div className="settings-actions">
          <button type="submit" className="btn btn-black" disabled={Boolean(busy)}>
            {busy === 'dmp' ? 'Отписываем...' : 'Запустить DMP'}
          </button>
        </div>
      </form>

      {lastResult ? (
        <div className="settings-section">
          <h3 className="settings-section-title">Последний ответ</h3>
          <p className="crm-prompt-preview">{formatResult(lastResult)}</p>
        </div>
      ) : null}
    </div>
  );
};

export default CustomAutomationTestPage;
