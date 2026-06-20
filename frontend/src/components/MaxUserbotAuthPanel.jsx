import React, { useEffect, useRef, useState } from 'react';
import agentService from '../services/agentService';
import UserbotSessionFileUpload from './UserbotSessionFileUpload';
import '../styles/userbotSessionFile.css';

const MaxUserbotAuthPanel = ({
  disabled = false,
  onSessionReady,
  onClear,
  onError,
  onSuccess,
}) => {
  const [authMode, setAuthMode] = useState('qr');
  const [authToken, setAuthToken] = useState('');
  const [qrAuthToken, setQrAuthToken] = useState('');
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [qrNeeds2fa, setQrNeeds2fa] = useState(false);
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [verifiedLabel, setVerifiedLabel] = useState('');
  const [isStartingQr, setIsStartingQr] = useState(false);
  const [isVerifyingQr2fa, setIsVerifyingQr2fa] = useState(false);
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [isVerifyingCode, setIsVerifyingCode] = useState(false);
  const [isImportingSession, setIsImportingSession] = useState(false);
  const lastQrStatusRef = useRef('');

  const resetAuth = () => {
    setAuthToken('');
    setQrAuthToken('');
    setQrDataUrl('');
    setQrNeeds2fa(false);
    setCode('');
    setPassword('');
    setVerifiedLabel('');
    lastQrStatusRef.current = '';
    onClear?.();
  };

  const switchAuthMode = (mode) => {
    setAuthMode(mode);
    resetAuth();
  };

  const applyVerified = (response) => {
    const payload = response?.session_payload || '';
    if (!payload) return;
    const label = response?.display_name
      || response?.phone_number
      || (response?.max_account_id ? `id: ${response.max_account_id}` : 'успешно');
    setVerifiedLabel(label);
    onSessionReady?.({
      session_payload: payload,
      max_account_id: response?.max_account_id,
      display_name: response?.display_name,
      phone_number: response?.phone_number,
      label,
    });
  };

  const handleQrStart = async () => {
    setIsStartingQr(true);
    try {
      const response = await agentService.startMaxUserbotQr({});
      setQrAuthToken(response?.auth_token || '');
      setQrDataUrl(response?.qr_data_url || '');
      setQrNeeds2fa(false);
      setVerifiedLabel('');
      lastQrStatusRef.current = '';
      onClear?.();
      onSuccess?.('Отсканируйте QR в приложении MAX');
    } catch (error) {
      onError?.(error?.message || 'Не удалось начать QR-вход MAX');
    } finally {
      setIsStartingQr(false);
    }
  };

  const handleQrVerify2fa = async () => {
    if (!qrAuthToken) {
      onError?.('Сначала начните QR-вход');
      return;
    }
    if (!password.trim()) {
      onError?.('Введите пароль 2FA');
      return;
    }
    setIsVerifyingQr2fa(true);
    try {
      const response = await agentService.verifyMaxUserbotQr2fa({
        auth_token: qrAuthToken,
        password: password.trim(),
      });
      applyVerified(response);
      setQrNeeds2fa(false);
      onSuccess?.('2FA подтверждена');
    } catch (error) {
      onError?.(error?.message || 'Не удалось подтвердить 2FA');
    } finally {
      setIsVerifyingQr2fa(false);
    }
  };

  const handleRequestCode = async () => {
    if (!phone.trim()) {
      onError?.('Введите номер телефона');
      return;
    }
    setIsSendingCode(true);
    try {
      const response = await agentService.requestMaxUserbotCode({
        phone_number: phone.trim(),
      });
      setAuthToken(response?.auth_token || '');
      setCode('');
      setPassword('');
      setVerifiedLabel('');
      onClear?.();
      onSuccess?.('Код подтверждения отправлен в MAX');
    } catch (error) {
      onError?.(error?.message || 'Не удалось отправить код MAX');
    } finally {
      setIsSendingCode(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!authToken) {
      onError?.('Сначала отправьте код подтверждения');
      return;
    }
    if (!code.trim()) {
      onError?.('Введите код из MAX');
      return;
    }
    setIsVerifyingCode(true);
    try {
      const response = await agentService.verifyMaxUserbotCode({
        auth_token: authToken,
        code: code.trim(),
        password: password.trim() || undefined,
      });
      if (response?.status === 'need_2fa') {
        setQrNeeds2fa(true);
        onSuccess?.('Введите пароль 2FA и подтвердите код снова');
        return;
      }
      applyVerified(response);
      onSuccess?.('Код подтверждён, можно подключать MAX userbot');
    } catch (error) {
      onError?.(error?.message || 'Не удалось подтвердить код');
    } finally {
      setIsVerifyingCode(false);
    }
  };

  const handleImportSession = async (file) => {
    if (!file) return;
    setIsImportingSession(true);
    try {
      const response = await agentService.importMaxUserbotSession({ session_file: file });
      applyVerified(response);
      onSuccess?.('Сессия MAX импортирована');
    } catch (error) {
      onError?.(error?.message || 'Не удалось импортировать сессию');
    } finally {
      setIsImportingSession(false);
    }
  };

  useEffect(() => {
    if (authMode !== 'qr' || !qrAuthToken || verifiedLabel) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const response = await agentService.maxUserbotQrStatus({ auth_token: qrAuthToken });
        if (cancelled) return;
        const nextStatus = String(response?.status || '').trim().toLowerCase();
        const prevStatus = lastQrStatusRef.current;
        if (nextStatus === 'need_2fa') {
          setQrNeeds2fa(true);
        } else if (nextStatus === 'success' && response?.session_payload) {
          applyVerified(response);
          setQrNeeds2fa(false);
        } else if ((nextStatus === 'expired' || nextStatus === 'error') && prevStatus !== nextStatus) {
          onClear?.();
        }
        lastQrStatusRef.current = nextStatus;
      } catch {
        // ignore polling errors
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [authMode, qrAuthToken, verifiedLabel, onClear]);

  return (
    <div className="agent-management-block">
      <div className="connection-type-grid connection-type-grid--triple channels-tabs">
        <button
          type="button"
          className={`connection-type-card ${authMode === 'qr' ? 'active' : ''}`}
          onClick={() => switchAuthMode('qr')}
          disabled={disabled}
        >
          QR-код
        </button>
        <button
          type="button"
          className={`connection-type-card ${authMode === 'phone' ? 'active' : ''}`}
          onClick={() => switchAuthMode('phone')}
          disabled={disabled}
        >
          Код из SMS
        </button>
        <button
          type="button"
          className={`connection-type-card ${authMode === 'file' ? 'active' : ''}`}
          onClick={() => switchAuthMode('file')}
          disabled={disabled}
        >
          Файл сессии
        </button>
      </div>

      {authMode === 'qr' ? (
        <>
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleQrStart}
            disabled={disabled || isStartingQr}
          >
            {isStartingQr ? 'Генерация QR...' : 'Показать QR-код'}
          </button>
          {qrDataUrl ? (
            <div className="userbot-qr-wrap">
              <img src={qrDataUrl} alt="MAX QR" className="userbot-qr-image" />
            </div>
          ) : null}
          <input
            type="password"
            className="input-main"
            placeholder="Пароль 2FA (если включена)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={disabled}
          />
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleQrVerify2fa}
            disabled={disabled || isVerifyingQr2fa || !qrNeeds2fa}
          >
            {isVerifyingQr2fa ? 'Проверка...' : 'Подтвердить 2FA'}
          </button>
          <p className="help-text">
            Отсканируйте QR в приложении MAX (как при входе на новом устройстве).
          </p>
        </>
      ) : null}

      {authMode === 'phone' ? (
        <>
          <input
            type="text"
            className="input-main"
            placeholder="+79990001122"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            disabled={disabled}
          />
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleRequestCode}
            disabled={disabled || isSendingCode}
          >
            {isSendingCode ? 'Отправка...' : 'Отправить код'}
          </button>
          <input
            type="text"
            className="input-main"
            placeholder="Код из MAX"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            disabled={disabled}
          />
          <input
            type="password"
            className="input-main"
            placeholder="Пароль 2FA (если есть)"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={disabled}
          />
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleVerifyCode}
            disabled={disabled || isVerifyingCode}
          >
            {isVerifyingCode ? 'Проверка...' : 'Подтвердить код'}
          </button>
        </>
      ) : null}

      {authMode === 'file' ? (
        <>
          <UserbotSessionFileUpload
            disabled={disabled}
            isImporting={isImportingSession}
            onFileSelect={handleImportSession}
            accept=".json,.txt,.db"
            formatsHint=".json, .txt или session.db (PyMax)"
          />
          <p className="help-text">
            Можно экспортировать JSON с полями token и device_id из web.max.ru (localStorage) или загрузить session.db PyMax.
          </p>
        </>
      ) : null}

      {verifiedLabel ? (
        <p className="help-text userbot-success">Готово: {verifiedLabel}</p>
      ) : null}
    </div>
  );
};

export default MaxUserbotAuthPanel;
