/**
 * Auth Page
 * Handles user login and registration.
 * Field names and validation match backend (router_users/schemas.py): name, password.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

/** Message for auth UI: apiClient sets error.message from FastAPI detail (normalized). */
function getAuthErrorMessage(error) {
  if (error?.message) {
    return error.message;
  }
  const data = error?.data ?? error?.originalError?.response?.data;
  if (data?.detail) {
    if (Array.isArray(data.detail)) {
      const first = data.detail[0];
      return first?.msg ?? (first?.loc && first.loc.join('. ')) ?? JSON.stringify(data.detail);
    }
    return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
  }
  return 'Ошибка входа. Проверьте учетные данные.';
}
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import { useForm } from '../hooks/useForm';
import { NAVIGATION_ROUTES, SUCCESS_MESSAGES, VALIDATION } from '../config/constants';
import { ENV_CONFIG } from '../config/environment';
import authService from '../services/authService';
import { reachYandexGoal, YM_GOALS } from '../utils/yandexMetrika';
import AgentChatShowcase from '../components/AgentChatShowcase';
import '../styles/auth.css';

/** Путь к иллюстрации справа; пока null — показывается запасной фон без растягивания */
const AUTH_MEDIA_IMAGE_SRC = null;

const AUTH_FORM_INITIAL = {
  name: '',
  email: '',
  password: '',
  verificationCode: '',
  resetCode: '',
  resetToken: '',
  newPassword: '',
  confirmNewPassword: '',
  consentPersonal: false,
  consentTerms: false,
};

const GOOGLE_IDENTITY_SCRIPT_URL = 'https://accounts.google.com/gsi/client';

const base64UrlEncode = (bytes) =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');

const generateNonce = () => {
  const bytes = new Uint8Array(24);
  window.crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
};

const Auth = () => {
  const navigate = useNavigate();
  const { login, loginWithGoogle, register, verifyRegistrationCode } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [isLogin, setIsLogin] = useState(true);
  const [isAwaitingEmailCode, setIsAwaitingEmailCode] = useState(false);
  const [recoveryStep, setRecoveryStep] = useState(null);
  const [resendCooldownUntil, setResendCooldownUntil] = useState(null);
  const [, setResendTick] = useState(0);
  const isRecoveryMode = recoveryStep !== null;
  const isRegister = !isLogin && !isRecoveryMode;
  const googleScriptPromiseRef = useRef(null);

  const ensureGoogleIdentityScript = useCallback(() => {
    if (window.google?.accounts?.id) {
      return Promise.resolve();
    }
    if (googleScriptPromiseRef.current) {
      return googleScriptPromiseRef.current;
    }
    googleScriptPromiseRef.current = new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${GOOGLE_IDENTITY_SCRIPT_URL}"]`);
      if (existing) {
        existing.addEventListener('load', () => resolve(), { once: true });
        existing.addEventListener('error', () => reject(new Error('Failed to load Google Identity SDK')), { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = GOOGLE_IDENTITY_SCRIPT_URL;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load Google Identity SDK'));
      document.head.appendChild(script);
    });
    return googleScriptPromiseRef.current;
  }, []);

  useEffect(() => {
    if (!resendCooldownUntil || resendCooldownUntil <= Date.now()) {
      return undefined;
    }
    const id = setInterval(() => {
      setResendTick((x) => x + 1);
    }, 1000);
    return () => clearInterval(id);
  }, [resendCooldownUntil]);

  const resendSecondsLeft = resendCooldownUntil
    ? Math.max(0, Math.ceil((resendCooldownUntil - Date.now()) / 1000))
    : 0;

  // Validation rules aligned with backend Pydantic.
  const authRules = useMemo(() => {
    if (isRecoveryMode) {
      if (recoveryStep === 'request') {
        return {
          email: { required: true, type: 'email', label: 'Email' },
        };
      }
      if (recoveryStep === 'verify') {
        return {
          email: { required: true, type: 'email', label: 'Email' },
          resetCode: {
            required: true,
            label: 'Код восстановления',
            minLength: VALIDATION.EMAIL_CODE_LENGTH,
            maxLength: VALIDATION.EMAIL_CODE_LENGTH,
            pattern: /^\d{6}$/,
            message: 'Введите 6 цифр из письма',
          },
        };
      }
      return {
        email: { required: true, type: 'email', label: 'Email' },
        newPassword: { required: true, type: 'password', label: 'Новый пароль' },
        confirmNewPassword: { required: true, type: 'password', label: 'Подтверждение пароля' },
      };
    }

    const loginRules = {
      name: {
        required: true,
        type: 'username',
        label: 'Имя пользователя',
        maxLength: VALIDATION.USERNAME_MAX_LENGTH_LOGIN,
      },
      password: { required: true, type: 'password', label: 'Пароль' },
    };
    if (isLogin) {
      return loginRules;
    }
    if (isAwaitingEmailCode) {
      return {
        email: { required: true, type: 'email', label: 'Email' },
        password: { required: true, type: 'password', label: 'Пароль' },
        verificationCode: {
          required: true,
          label: 'Код подтверждения',
          minLength: VALIDATION.EMAIL_CODE_LENGTH,
          maxLength: VALIDATION.EMAIL_CODE_LENGTH,
          pattern: /^\d{6}$/,
          message: 'Введите 6 цифр из письма',
        },
      };
    }
    return {
      email: { required: true, type: 'email', label: 'Email' },
      password: { required: true, type: 'password', label: 'Пароль' },
      consentPersonal: {
        type: 'checkbox',
        required: true,
        label: 'Согласие на обработку персональных данных',
        message: 'Отметьте согласие на обработку персональных данных',
      },
      consentTerms: {
        type: 'checkbox',
        required: true,
        label: 'Принятие условий оферты и соглашения',
        message: 'Примите условия Публичной оферты и Пользовательского соглашения',
      },
    };
  }, [isAwaitingEmailCode, isLogin, isRecoveryMode, recoveryStep]);

  const form = useForm(
    AUTH_FORM_INITIAL,
    async (values) => {
      try {
        if (isRecoveryMode) {
          if (recoveryStep === 'request') {
            await authService.requestPasswordResetCode(values.email);
            setRecoveryStep('verify');
            showSuccess('Код восстановления отправлен на email', 3500);
            return;
          }

          if (recoveryStep === 'verify') {
            const verifyResult = await authService.verifyPasswordResetCode(values.email, values.resetCode);
            form.setFieldValue('resetToken', verifyResult.reset_token);
            setRecoveryStep('reset');
            showSuccess('Код подтвержден. Задайте новый пароль.', 3000);
            return;
          }

          if (values.newPassword !== values.confirmNewPassword) {
            showError('Пароли не совпадают');
            return;
          }
          if (!values.resetToken) {
            showError('Сессия восстановления не найдена. Повторите процесс.');
            setRecoveryStep('request');
            return;
          }
          await authService.confirmPasswordReset(values.email, values.resetToken, values.newPassword);
          showSuccess('Пароль успешно изменен. Теперь войдите в систему.', 3500);
          setRecoveryStep(null);
          setIsLogin(true);
          setIsAwaitingEmailCode(false);
          setResendCooldownUntil(null);
          form.reset();
          return;
        }

        if (isLogin) {
          await login(values.name, values.password);
          showSuccess(SUCCESS_MESSAGES.LOGIN_SUCCESS, 3000);
          navigate(NAVIGATION_ROUTES.AGENTS);
        } else {
          if (!isAwaitingEmailCode) {
            await register(values.email, values.password);
            setIsAwaitingEmailCode(true);
            setResendCooldownUntil(
              Date.now() + VALIDATION.EMAIL_RESEND_COOLDOWN_SECONDS * 1000
            );
            showSuccess('Код подтверждения отправлен на email', 3500);
            return;
          }

          await verifyRegistrationCode(values.email, values.verificationCode);
          reachYandexGoal(YM_GOALS.REGISTRATION_SUCCESS);
          showSuccess('Регистрация успешна!', 3000);
          navigate(NAVIGATION_ROUTES.AGENTS);
        }
      } catch (error) {
        showError(getAuthErrorMessage(error));
      }
    },
    authRules
  );

  const toggleAuthMode = () => {
    form.reset();
    setIsAwaitingEmailCode(false);
    setResendCooldownUntil(null);
    setRecoveryStep(null);
    setIsLogin(!isLogin);
  };

  const startPasswordRecovery = () => {
    form.reset();
    setRecoveryStep('request');
    setIsAwaitingEmailCode(false);
    setResendCooldownUntil(null);
  };

  const cancelPasswordRecovery = () => {
    form.reset();
    setRecoveryStep(null);
    setIsLogin(true);
    setIsAwaitingEmailCode(false);
    setResendCooldownUntil(null);
  };

  const resendEmailCode = async () => {
    try {
      await authService.resendRegistrationCode(form.values.email);
      setResendCooldownUntil(
        Date.now() + VALIDATION.EMAIL_RESEND_COOLDOWN_SECONDS * 1000
      );
      showSuccess('Новый код отправлен на email', 3000);
    } catch (error) {
      showError(getAuthErrorMessage(error));
    }
  };

  const handleGoogleSignIn = async () => {
    if (isRecoveryMode || isAwaitingEmailCode || form.isSubmitting) {
      return;
    }
    if (!ENV_CONFIG.APP.GOOGLE_CLIENT_ID) {
      showError('Google OAuth не настроен на клиенте (VITE_GOOGLE_CLIENT_ID)');
      return;
    }
    try {
      await ensureGoogleIdentityScript();
      if (!window.google?.accounts?.id) {
        throw new Error('Google Identity SDK not available');
      }
      
      const nonce = generateNonce();
      
      // Detect mobile
      const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
      
      // Initialize Google SDK
      window.google.accounts.id.initialize({
        client_id: ENV_CONFIG.APP.GOOGLE_CLIENT_ID,
        nonce,
        callback: async (response) => {
          if (response.credential) {
            try {
              // Decode the credential to see what we have (for debugging only)
              const parts = response.credential.split('.');
              if (parts.length === 3) {
                try {
                  const payload = JSON.parse(atob(parts[1]));
                  console.log('Google ID token payload:', {
                    email: payload.email,
                    email_verified: payload.email_verified,
                    nonce: payload.nonce,
                    hd: payload.hd,
                  });
                } catch (e) {
                  console.log('Could not decode token payload:', e.message);
                }
              }
              console.log('Google credential received, attempting login with nonce:', nonce);
              await loginWithGoogle(response.credential, nonce);
              showSuccess(SUCCESS_MESSAGES.LOGIN_SUCCESS, 3000);
              navigate(NAVIGATION_ROUTES.AGENTS);
            } catch (error) {
              console.error('Google login failed:', error);
              showError(getAuthErrorMessage(error));
            }
          }
        },
      });
      
      if (isMobile) {
        // For mobile: use one-tap (more reliable than popup on mobile)
        window.google.accounts.id.prompt((notification) => {
          // One-tap UI showed/was dismissed
        });
      } else {
        // For desktop: use renderButton and direct trigger
        const buttonContainer = document.createElement('div');
        buttonContainer.id = `gsi_button_${Date.now()}`;
        buttonContainer.style.display = 'none';
        document.body.appendChild(buttonContainer);
        
        window.google.accounts.id.renderButton(buttonContainer, {
          theme: 'outline',
          size: 'large',
        });
        
        // Click the button to open popup
        const button = buttonContainer.querySelector('div[role="button"]');
        if (button) {
          button.click();
        }
        
        // Cleanup after a delay
        setTimeout(() => {
          buttonContainer.remove();
        }, 5000);
      }
    } catch (error) {
      console.error('Google sign-in initialization error:', error);
      showError(getAuthErrorMessage(error));
    }
  };

  return (
    <div className="auth-page">
      <a className="auth-logo" href={NAVIGATION_ROUTES.HOME}>
        RSD
      </a>

      <main className="auth-container">
        <div className="auth-card">
          <div className="auth-form-side">
            <div className="auth-form-main">
              <h2>
                {isRecoveryMode
                  ? 'Восстановление пароля'
                  : isLogin
                    ? 'Добро пожаловать'
                    : 'Создать аккаунт'}
              </h2>
              <p className="auth-subtitle">
                {isRecoveryMode
                  ? recoveryStep === 'request'
                    ? 'Введите email, и мы отправим код восстановления'
                    : recoveryStep === 'verify'
                      ? 'Введите 6-значный код из письма'
                      : 'Введите и подтвердите новый пароль'
                  : isLogin
                    ? 'Войдите в систему для получения доступа к платформе'
                    : isAwaitingEmailCode
                      ? 'Введите 6-значный код, отправленный на ваш email'
                      : 'Заполните форму для создания нового аккаунта'}
              </p>

              {/* Google Auth Button */}
              <button
                className="google-btn"
                type="button"
                disabled={form.isSubmitting || isRecoveryMode || isAwaitingEmailCode}
                onClick={handleGoogleSignIn}
              >
                Авторизация через Google
              </button>

              {/* Auth form */}
              <form className="auth-form" onSubmit={form.handleSubmit}>
              {isLogin && !isRecoveryMode && (
                <div className="form-group">
                  <label htmlFor="name">Email или имя пользователя:</label>
                  <input
                    id="name"
                    type="text"
                    name="name"
                    placeholder="Email или имя пользователя"
                    value={form.values.name}
                    onChange={form.handleChange}
                    onBlur={form.handleBlur}
                    disabled={form.isSubmitting}
                    className={form.errors.name ? 'error' : ''}
                    autoComplete="username"
                  />
                  {form.touched.name && form.errors.name && (
                    <span className="error-message">{form.errors.name}</span>
                  )}
                </div>
              )}

              {(isRegister || isRecoveryMode) && (
                <div className="form-group">
                  <label htmlFor="email">Email:</label>
                  <input
                    id="email"
                    type="email"
                    name="email"
                    placeholder="example@mail.com"
                    value={form.values.email}
                    onChange={form.handleChange}
                    onBlur={form.handleBlur}
                    disabled={
                      form.isSubmitting
                      || (isRegister && isAwaitingEmailCode)
                      || (isRecoveryMode && recoveryStep !== 'request')
                    }
                    className={form.errors.email ? 'error' : ''}
                    autoComplete="email"
                  />
                  {form.touched.email && form.errors.email && (
                    <span className="error-message">{form.errors.email}</span>
                  )}
                </div>
              )}

              {!isRecoveryMode && (
              <div className="form-group">
                <label htmlFor="password">Пароль:</label>
                <input
                  id="password"
                  type="password"
                  name="password"
                  placeholder="От 6 до 30 символов"
                  value={form.values.password}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting || (!isLogin && isAwaitingEmailCode)}
                  className={form.errors.password ? 'error' : ''}
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                />
                {form.touched.password && form.errors.password && (
                  <span className="error-message">{form.errors.password}</span>
                )}
              </div>
              )}

              {isRegister && isAwaitingEmailCode && (
                <div className="form-group">
                  <label htmlFor="verificationCode">Код подтверждения:</label>
                  <input
                    id="verificationCode"
                    type="text"
                    name="verificationCode"
                    placeholder="6 цифр"
                    value={form.values.verificationCode}
                    onChange={form.handleChange}
                    onBlur={form.handleBlur}
                    disabled={form.isSubmitting}
                    className={form.errors.verificationCode ? 'error' : ''}
                    autoComplete="one-time-code"
                    inputMode="numeric"
                    maxLength={VALIDATION.EMAIL_CODE_LENGTH}
                  />
                  {form.touched.verificationCode && form.errors.verificationCode && (
                    <span className="error-message">{form.errors.verificationCode}</span>
                  )}
                </div>
              )}

              {isRecoveryMode && recoveryStep === 'verify' && (
                <div className="form-group">
                  <label htmlFor="resetCode">Код восстановления:</label>
                  <input
                    id="resetCode"
                    type="text"
                    name="resetCode"
                    placeholder="6 цифр"
                    value={form.values.resetCode}
                    onChange={form.handleChange}
                    onBlur={form.handleBlur}
                    disabled={form.isSubmitting}
                    className={form.errors.resetCode ? 'error' : ''}
                    autoComplete="one-time-code"
                    inputMode="numeric"
                    maxLength={VALIDATION.EMAIL_CODE_LENGTH}
                  />
                  {form.touched.resetCode && form.errors.resetCode && (
                    <span className="error-message">{form.errors.resetCode}</span>
                  )}
                </div>
              )}

              {isRecoveryMode && recoveryStep === 'reset' && (
                <>
                  <div className="form-group">
                    <label htmlFor="newPassword">Новый пароль:</label>
                    <input
                      id="newPassword"
                      type="password"
                      name="newPassword"
                      placeholder="От 6 до 30 символов"
                      value={form.values.newPassword}
                      onChange={form.handleChange}
                      onBlur={form.handleBlur}
                      disabled={form.isSubmitting}
                      className={form.errors.newPassword ? 'error' : ''}
                      autoComplete="new-password"
                    />
                    {form.touched.newPassword && form.errors.newPassword && (
                      <span className="error-message">{form.errors.newPassword}</span>
                    )}
                  </div>
                  <div className="form-group">
                    <label htmlFor="confirmNewPassword">Подтвердите пароль:</label>
                    <input
                      id="confirmNewPassword"
                      type="password"
                      name="confirmNewPassword"
                      placeholder="Повторите новый пароль"
                      value={form.values.confirmNewPassword}
                      onChange={form.handleChange}
                      onBlur={form.handleBlur}
                      disabled={form.isSubmitting}
                      className={form.errors.confirmNewPassword ? 'error' : ''}
                      autoComplete="new-password"
                    />
                    {form.touched.confirmNewPassword && form.errors.confirmNewPassword && (
                      <span className="error-message">{form.errors.confirmNewPassword}</span>
                    )}
                  </div>
                </>
              )}

              {isRegister && !isAwaitingEmailCode && (
                <div className="auth-consents" role="group" aria-label="Согласия при регистрации">
                  <div className="auth-consent-block">
                    <div className="auth-checkbox-row auth-checkbox-row--terms">
                      <input
                        id="consentPersonal"
                        type="checkbox"
                        name="consentPersonal"
                        checked={form.values.consentPersonal}
                        onChange={form.handleChange}
                        onBlur={form.handleBlur}
                        disabled={form.isSubmitting}
                        aria-invalid={!!form.errors.consentPersonal}
                        aria-describedby="consent-personal-text"
                      />
                      <p className="auth-consent-text" id="consent-personal-text">
                        <label htmlFor="consentPersonal" className="auth-consent-label-inline">
                          Я согласен на{' '}
                        </label>
                        <Link
                          className="auth-legal-link"
                          to={NAVIGATION_ROUTES.PRIVACY_POLICY}
                          onClick={(e) => e.stopPropagation()}
                        >
                          обработку персональных данных
                        </Link>
                      </p>
                    </div>
                    {form.errors.consentPersonal && (
                      <span className="error-message auth-consent-error">{form.errors.consentPersonal}</span>
                    )}
                  </div>

                  <div className="auth-consent-block">
                    <div className="auth-checkbox-row auth-checkbox-row--terms">
                      <input
                        id="consentTerms"
                        type="checkbox"
                        name="consentTerms"
                        checked={form.values.consentTerms}
                        onChange={form.handleChange}
                        onBlur={form.handleBlur}
                        disabled={form.isSubmitting}
                        aria-invalid={!!form.errors.consentTerms}
                        aria-describedby="consent-terms-text"
                      />
                      <p className="auth-consent-text" id="consent-terms-text">
                        <label htmlFor="consentTerms" className="auth-consent-label-inline">
                          Я принимаю условия{' '}
                        </label>
                        <Link
                          className="auth-legal-link"
                          to={NAVIGATION_ROUTES.PUBLIC_OFFER}
                          onClick={(e) => e.stopPropagation()}
                        >
                          Публичной оферты
                        </Link>
                        <span> и </span>
                        <Link
                          className="auth-legal-link"
                          to={NAVIGATION_ROUTES.USER_AGREEMENT}
                          onClick={(e) => e.stopPropagation()}
                        >
                          Пользовательского соглашения
                        </Link>
                      </p>
                    </div>
                    {form.errors.consentTerms && (
                      <span className="error-message auth-consent-error">{form.errors.consentTerms}</span>
                    )}
                  </div>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-continue"
                disabled={form.isSubmitting}
              >
                {form.isSubmitting
                  ? 'Обработка...'
                  : isRecoveryMode
                    ? recoveryStep === 'request'
                      ? 'Отправить код'
                      : recoveryStep === 'verify'
                        ? 'Проверить код'
                        : 'Сохранить новый пароль'
                    : isLogin
                      ? 'Войти'
                      : isAwaitingEmailCode
                        ? 'Подтвердить код'
                        : 'Создать аккаунт'}
              </button>
              {!isRecoveryMode && isRegister && isAwaitingEmailCode && (
                <button
                  type="button"
                  className="btn btn-continue"
                  disabled={form.isSubmitting || resendSecondsLeft > 0}
                  onClick={resendEmailCode}
                >
                  {resendSecondsLeft > 0
                    ? `Повторная отправка через ${resendSecondsLeft} с`
                    : 'Отправить код повторно'}
                </button>
              )}
              {!isRecoveryMode && isLogin && (
                <button
                  type="button"
                  className="toggle-btn"
                  onClick={startPasswordRecovery}
                  disabled={form.isSubmitting}
                >
                  Забыли пароль?
                </button>
              )}
              {isRecoveryMode && (
                <button
                  type="button"
                  className="toggle-btn"
                  onClick={cancelPasswordRecovery}
                  disabled={form.isSubmitting}
                >
                  Назад ко входу
                </button>
              )}
              </form>
            </div>

            <div className="auth-form-footer">
              {/* Toggle Auth Mode */}
              {!isRecoveryMode && (
              <div className="auth-toggle">
                <p>
                  {isLogin ? 'Нет аккаунта?' : 'Уже есть аккаунт?'}
                  <button
                    type="button"
                    className="toggle-btn"
                    onClick={toggleAuthMode}
                    disabled={form.isSubmitting}
                  >
                    {isLogin ? 'Создать' : 'Войти'}
                  </button>
                </p>
              </div>
              )}

              {isLogin && !isRecoveryMode && (
                <p className="terms">
                  Продолжая, вы подтверждаете ознакомление с{' '}
                  <Link className="auth-legal-link" to={NAVIGATION_ROUTES.PUBLIC_OFFER}>
                    Публичной офертой
                  </Link>
                  ,{' '}
                  <Link className="auth-legal-link" to={NAVIGATION_ROUTES.USER_AGREEMENT}>
                    Пользовательским соглашением
                  </Link>{' '}
                  и{' '}
                  <Link className="auth-legal-link" to={NAVIGATION_ROUTES.PRIVACY_POLICY}>
                    Политикой конфиденциальности
                  </Link>
                  .
                </p>
              )}
            </div>
          </div>

          <div className="auth-media-side">
            <div className="auth-media-frame">
              {AUTH_MEDIA_IMAGE_SRC ? (
                <img
                  className="auth-media-image"
                  src={AUTH_MEDIA_IMAGE_SRC}
                  alt=""
                  decoding="async"
                />
              ) : (
                <div className="auth-media-showcase-wrap">
                  <AgentChatShowcase tone="light" variant="auth" />
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Auth;