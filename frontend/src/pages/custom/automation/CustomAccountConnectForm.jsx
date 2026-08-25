import React, { useEffect, useRef, useState } from 'react';
import CustomSelect from '../../../components/CustomSelect';
import customService from '../../../services/customService';

const CONNECT_CLASSES = [
  { value: 'one_day', label: 'Однодневный' },
  { value: 'mid', label: 'Средний' },
  { value: 'trusted', label: 'Доверенный' },
  { value: 'shilling', label: 'Шиллинг' },
];

const CustomAccountConnectForm = ({ automationId, onConnected }) => {
  const [mode, setMode] = useState('qr');
  const [assignClass, setAssignClass] = useState('one_day');
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const onConnectedRef = useRef(onConnected);
  onConnectedRef.current = onConnected;

  const [qrAuthToken, setQrAuthToken] = useState('');
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [qrNeeds2fa, setQrNeeds2fa] = useState(false);
  const [qrPassword, setQrPassword] = useState('');
  const [isStartingQr, setIsStartingQr] = useState(false);
  const [isVerifyingQr2fa, setIsVerifyingQr2fa] = useState(false);
  const [qrConnected, setQrConnected] = useState(false);
  const lastQrStatusRef = useRef('');

  const [phone, setPhone] = useState('');
  const [smsAuthToken, setSmsAuthToken] = useState('');
  const [smsCode, setSmsCode] = useState('');
  const [smsPassword, setSmsPassword] = useState('');
  const [smsNeeds2fa, setSmsNeeds2fa] = useState(false);
  const [isRequestingSms, setIsRequestingSms] = useState(false);
  const [isVerifyingSms, setIsVerifyingSms] = useState(false);

  const resetMessages = () => {
    setMessage(null);
    setError(null);
  };

  const handleConnected = async (account) => {
    const label = account?.phone_number || (account?.username ? `@${account.username}` : 'аккаунт');
    setMessage(`Добавлен ${label}`);
    setError(null);
    if (onConnectedRef.current) {
      await onConnectedRef.current();
    }
  };

  const handleQrStart = async () => {
    resetMessages();
    setIsStartingQr(true);
    setQrNeeds2fa(false);
    setQrConnected(false);
    lastQrStatusRef.current = '';
    try {
      const response = await customService.startAccountQr(automationId, assignClass);
      setQrAuthToken(response.auth_token || '');
      setQrDataUrl(response.qr_data_url || '');
      if (response.already_authorized && response.account) {
        setQrConnected(true);
        await handleConnected(response.account);
        return;
      }
      setMessage('Telegram → Настройки → Устройства → Подключить устройство');
    } catch (err) {
      setError(err.message || 'Не удалось начать QR-вход');
      setQrAuthToken('');
      setQrDataUrl('');
    } finally {
      setIsStartingQr(false);
    }
  };

  const handleQrVerify2fa = async () => {
    if (!qrAuthToken) {
      setError('Сначала покажите QR-код');
      return;
    }
    if (!qrPassword.trim()) {
      setError('Введите пароль 2FA');
      return;
    }
    resetMessages();
    setIsVerifyingQr2fa(true);
    try {
      const response = await customService.verifyAccountQr2fa(automationId, qrAuthToken, qrPassword.trim());
      setQrNeeds2fa(false);
      setQrConnected(true);
      await handleConnected(response.account);
    } catch (err) {
      setError(err.message || 'Не удалось подтвердить 2FA');
    } finally {
      setIsVerifyingQr2fa(false);
    }
  };

  useEffect(() => {
    if (mode !== 'qr') return undefined;
    if (!qrAuthToken || qrConnected) return undefined;

    let cancelled = false;
    const pollStatus = async () => {
      try {
        const response = await customService.accountQrStatus(automationId, qrAuthToken);
        if (cancelled) return;
        const nextStatus = String(response?.status || '').trim().toLowerCase();
        const prevStatus = lastQrStatusRef.current;
        if (nextStatus === 'need_2fa') {
          setQrNeeds2fa(true);
          if (prevStatus !== 'need_2fa') {
            setMessage('QR принят. Введите пароль 2FA.');
            setError(null);
          }
        } else if (nextStatus === 'success' && response?.account) {
          setQrNeeds2fa(false);
          setQrConnected(true);
          lastQrStatusRef.current = nextStatus;
          if (prevStatus !== 'success') {
            await handleConnected(response.account);
          }
          return;
        } else if (nextStatus === 'expired' || nextStatus === 'error') {
          if (prevStatus !== nextStatus) {
            setError(response?.error || 'QR-вход не удался. Покажите новый QR.');
          }
        }
        lastQrStatusRef.current = nextStatus;
      } catch {
        // polling noise is ok
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [mode, qrAuthToken, qrConnected, automationId]);

  const handleSmsRequest = async () => {
    if (!phone.trim()) {
      setError('Укажите номер телефона');
      return;
    }
    resetMessages();
    setIsRequestingSms(true);
    setSmsNeeds2fa(false);
    try {
      const response = await customService.requestAccountSms(automationId, phone.trim(), assignClass);
      setSmsAuthToken(response.auth_token || '');
      setMessage('Код отправлен в Telegram. Введите его ниже.');
    } catch (err) {
      setError(err.message || 'Не удалось отправить код');
      setSmsAuthToken('');
    } finally {
      setIsRequestingSms(false);
    }
  };

  const handleSmsVerify = async () => {
    if (!smsAuthToken) {
      setError('Сначала запросите код');
      return;
    }
    if (!smsCode.trim()) {
      setError('Введите код из Telegram');
      return;
    }
    resetMessages();
    setIsVerifyingSms(true);
    try {
      const response = await customService.verifyAccountSms(automationId, {
        authToken: smsAuthToken,
        code: smsCode.trim(),
        password: smsPassword.trim() || undefined,
      });
      setSmsNeeds2fa(false);
      await handleConnected(response.account);
    } catch (err) {
      if (err.status === 409 || /2FA/i.test(err.message || '')) {
        setSmsNeeds2fa(true);
        setError('Введите пароль 2FA и подтвердите ещё раз');
      } else {
        setError(err.message || 'Не удалось подтвердить код');
      }
    } finally {
      setIsVerifyingSms(false);
    }
  };

  return (
    <section className="settings-section">
      <h3 className="settings-section-title">Добавить аккаунт</h3>
      <p className="form-hint">Как у ИИ-агента: QR или код по SMS. 2FA — если включена на аккаунте.</p>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="form-group">
        <label htmlFor="connect-class">Класс</label>
        <CustomSelect
          id="connect-class"
          value={assignClass}
          options={CONNECT_CLASSES}
          onChange={(e) => setAssignClass(e.target.value)}
        />
      </div>

      <div className="account-connect-modes">
        <button
          type="button"
          className={`account-connect-mode ${mode === 'qr' ? 'active' : ''}`}
          onClick={() => setMode('qr')}
        >
          QR-код
        </button>
        <button
          type="button"
          className={`account-connect-mode ${mode === 'sms' ? 'active' : ''}`}
          onClick={() => setMode('sms')}
        >
          Код по SMS
        </button>
      </div>

      {mode === 'qr' ? (
        <>
          <div className="settings-actions">
            <button type="button" className="btn btn-black" onClick={handleQrStart} disabled={isStartingQr}>
              {isStartingQr ? 'Генерация...' : 'Показать QR-код'}
            </button>
          </div>
          {qrDataUrl ? (
            <>
              <div className="userbot-qr-wrap">
                <img src={qrDataUrl} alt="Telegram QR" className="userbot-qr-image" />
              </div>
              <div className="form-group">
                <label htmlFor="connect-qr-2fa">Пароль 2FA</label>
                <input
                  id="connect-qr-2fa"
                  type="password"
                  value={qrPassword}
                  onChange={(e) => setQrPassword(e.target.value)}
                  placeholder="Если на аккаунте включена защита"
                />
              </div>
              <div className="settings-actions">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={handleQrVerify2fa}
                  disabled={isVerifyingQr2fa || !qrNeeds2fa}
                >
                  {isVerifyingQr2fa ? 'Проверка...' : 'Подтвердить 2FA'}
                </button>
              </div>
            </>
          ) : null}
        </>
      ) : (
        <>
          <div className="form-group">
            <label htmlFor="connect-phone">Номер телефона</label>
            <input
              id="connect-phone"
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+79990001122"
            />
          </div>
          <div className="settings-actions">
            <button type="button" className="btn btn-black" onClick={handleSmsRequest} disabled={isRequestingSms}>
              {isRequestingSms ? 'Отправка...' : 'Запросить код'}
            </button>
          </div>
          {smsAuthToken ? (
            <>
              <div className="form-group">
                <label htmlFor="connect-sms-code">Код из Telegram</label>
                <input
                  id="connect-sms-code"
                  type="text"
                  value={smsCode}
                  onChange={(e) => setSmsCode(e.target.value)}
                  placeholder="12345"
                />
              </div>
              {smsNeeds2fa ? (
                <div className="form-group">
                  <label htmlFor="connect-sms-2fa">Пароль 2FA</label>
                  <input
                    id="connect-sms-2fa"
                    type="password"
                    value={smsPassword}
                    onChange={(e) => setSmsPassword(e.target.value)}
                    placeholder="Пароль двухфакторной защиты"
                  />
                </div>
              ) : null}
              <div className="settings-actions">
                <button type="button" className="btn btn-outline" onClick={handleSmsVerify} disabled={isVerifyingSms}>
                  {isVerifyingSms ? 'Проверка...' : 'Подтвердить'}
                </button>
              </div>
            </>
          ) : null}
        </>
      )}
    </section>
  );
};

export default CustomAccountConnectForm;
