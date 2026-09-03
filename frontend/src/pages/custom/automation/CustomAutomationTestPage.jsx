import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { useCustomAuth } from '../../../components/custom/useCustomAuth';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/projectCRMPage.css';

const targetLabel = (target) => {
  if (!target) {
    return 'ещё не создан';
  }
  const name = target.title || target.username || `#${target.id}`;
  return `${name} · ${target.join_status || 'pending'}`;
};

const statusTone = (result) => {
  if (!result) {
    return '';
  }
  if (result.status === 'waiting') {
    return 'test-lab-status--waiting';
  }
  if (result.ok || result.status === 'success') {
    return 'test-lab-status--success';
  }
  return 'test-lab-status--error';
};

const statusTitle = (result) => {
  if (!result) {
    return '';
  }
  if (result.status === 'waiting') {
    return 'Ждём';
  }
  if (result.ok || result.status === 'success') {
    return 'Успешно';
  }
  if (result.status === 'timeout') {
    return 'Таймаут';
  }
  return 'Ошибка';
};

const formatSeconds = (seconds) => {
  const left = Math.max(0, Number(seconds) || 0);
  const mins = Math.floor(left / 60);
  const secs = left % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
};

const TestLabStatus = ({ result }) => {
  if (!result) {
    return null;
  }
  return (
    <div className={`test-lab-status ${statusTone(result)}`}>
      <strong>{statusTitle(result)}</strong>
      <p>{result.detail}</p>
      {result.status === 'waiting' && result.seconds_left != null ? (
        <p className="form-hint">Осталось: {formatSeconds(result.seconds_left)}</p>
      ) : null}
      {result.post_id ? <p className="form-hint">Пост #{result.post_id}</p> : null}
    </div>
  );
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
  const [actionResults, setActionResults] = useState({});
  const pollRef = useRef(null);

  const setActionResult = (key, result) => {
    if (!result) {
      return;
    }
    setActionResults((prev) => ({ ...prev, [key]: result }));
  };

  const loadLab = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await customService.getTestLab(id);
      setLab(data);
      setChannelUsername(data.channel_username || '');
      setChatUsername(data.chat_username || '');
      if (data.watch) {
        setActionResult('channel', data.watch);
      }
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

  const stopWatchPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startWatchPoll = useCallback(() => {
    stopWatchPoll();
    pollRef.current = setInterval(async () => {
      try {
        const watch = await customService.getTestLabChannelActivity(id);
        setActionResult('channel', watch);
        if (watch.status !== 'waiting') {
          stopWatchPoll();
          await loadLab();
        }
      } catch (err) {
        stopWatchPoll();
        setError(err.message || 'Не удалось проверить ожидание поста');
      }
    }, 4000);
  }, [id, loadLab, stopWatchPoll]);

  useEffect(() => () => stopWatchPoll(), [stopWatchPoll]);

  useEffect(() => {
    const watch = actionResults.channel;
    if (watch?.status === 'waiting' && !pollRef.current) {
      startWatchPoll();
    }
  }, [actionResults.channel, startWatchPoll]);

  const runAction = async (key, fn) => {
    setBusy(key);
    setError(null);
    try {
      const result = await fn();
      setActionResult(key, result);
      await loadLab();
      return result;
    } catch (err) {
      setError(err.message || 'Ошибка теста');
      setActionResult(key, {
        ok: false,
        status: 'error',
        detail: err.message || 'Ошибка теста',
      });
      return null;
    } finally {
      setBusy('');
    }
  };

  if (!isAdmin) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(id)} replace />;
  }

  const handleJoin = async (e) => {
    e.preventDefault();
    await runAction('join', () => customService.joinTestLab(id, {
      channel_username: channelUsername,
      chat_username: chatUsername,
    }));
  };

  const handleChatShilling = () => runAction('chatShilling', () => customService.runTestLabShilling(id));

  const handleChannelNeuro = async () => {
    const result = await runAction(
      'channel',
      () => customService.startTestLabChannelActivity(id, 'neurocommenting'),
    );
    if (result?.status === 'waiting') {
      startWatchPoll();
    }
  };

  const handleChannelShilling = async () => {
    const result = await runAction(
      'channel',
      () => customService.startTestLabChannelActivity(id, 'shilling'),
    );
    if (result?.status === 'waiting') {
      startWatchPoll();
    }
  };

  const handleDmp = async (e) => {
    e.preventDefault();
    const phone = dmpPhone.trim();
    if (!phone) {
      setError('Введите номер, как будто он пришёл из DMP');
      return;
    }
    await runAction('dmp', () => customService.runTestLabDmp(id, phone));
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

      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <form onSubmit={handleJoin} className="settings-section">
        <h3 className="settings-section-title">Целевые канал и чат</h3>
        <p className="form-hint">
          Один канал и один чат. «Вступить» сохраняет ссылки и сразу вводит аккаунты.
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
            {busy === 'join' ? 'Вступаем...' : 'Вступить'}
          </button>
        </div>
        <TestLabStatus result={actionResults.join} />
      </form>

      <div className="settings-section">
        <h3 className="settings-section-title">Шиллинг в чате</h3>
        <p className="form-hint">
          Аккаунты с функцией «Шиллинг» пишут в целевом чате фиксированные вопрос и ответ из промптов.
        </p>
        <div className="settings-actions">
          <button type="button" className="btn btn-black" disabled={Boolean(busy)} onClick={handleChatShilling}>
            {busy === 'chatShilling' ? 'Шиллим...' : 'Активировать шиллинг'}
          </button>
        </div>
        <TestLabStatus result={actionResults.chatShilling} />
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Нейрокомментинг и шиллинг в комментариях</h3>
        <p className="form-hint">
          Аккаунты ждут новый пост в целевом канале до 5 минут. Как только пост вышел — сразу выполняется выбранная активность.
        </p>
        <div className="settings-actions">
          <button type="button" className="btn btn-black" disabled={Boolean(busy)} onClick={handleChannelNeuro}>
            {busy === 'channel' ? 'Запускаем...' : 'Активировать нейрокомментинг'}
          </button>
          <button type="button" className="btn btn-outline" disabled={Boolean(busy)} onClick={handleChannelShilling}>
            {busy === 'channel' ? 'Запускаем...' : 'Активировать шиллинг'}
          </button>
        </div>
        <TestLabStatus result={actionResults.channel} />
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
        <TestLabStatus result={actionResults.dmp} />
      </form>
    </div>
  );
};

export default CustomAutomationTestPage;
