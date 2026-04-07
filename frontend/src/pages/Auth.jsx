/**
 * Auth Page
 * Handles user login and registration.
 * Field names and validation match backend (router_users/schemas.py): name, password.
 */

import React, { useMemo, useState } from 'react';

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
import AgentChatShowcase from '../components/AgentChatShowcase';
import '../styles/auth.css';

/** Путь к иллюстрации справа; пока null — показывается запасной фон без растягивания */
const AUTH_MEDIA_IMAGE_SRC = null;

const AUTH_FORM_INITIAL = {
  name: '',
  email: '',
  password: '',
  verificationCode: '',
  consentPersonal: false,
  consentTerms: false,
};

const Auth = () => {
  const navigate = useNavigate();
  const { login, register, verifyRegistrationCode } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [isLogin, setIsLogin] = useState(true);
  const [isAwaitingEmailCode, setIsAwaitingEmailCode] = useState(false);

  // Validation rules aligned with backend Pydantic.
  const authRules = useMemo(() => {
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
  }, [isAwaitingEmailCode, isLogin]);

  const form = useForm(
    AUTH_FORM_INITIAL,
    async (values) => {
      try {
        if (isLogin) {
          await login(values.name, values.password);
          showSuccess(SUCCESS_MESSAGES.LOGIN_SUCCESS, 3000);
          navigate(NAVIGATION_ROUTES.AGENTS);
        } else {
          if (!isAwaitingEmailCode) {
            await register(values.email, values.password);
            setIsAwaitingEmailCode(true);
            showSuccess('Код подтверждения отправлен на email', 3500);
            return;
          }

          await verifyRegistrationCode(values.email, values.verificationCode);
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
    setIsLogin(!isLogin);
  };

  const resendEmailCode = async () => {
    try {
      await register(form.values.email, form.values.password);
      showSuccess('Новый код отправлен на email', 3000);
    } catch (error) {
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
              <h2>{isLogin ? 'Добро пожаловать' : 'Создать аккаунт'}</h2>
              <p className="auth-subtitle">
                {isLogin
                  ? 'Войдите в систему для получения доступа к платформе'
                  : isAwaitingEmailCode
                    ? 'Введите 6-значный код, отправленный на ваш email'
                    : 'Заполните форму для создания нового аккаунта'}
              </p>

              {/* Google Auth Button */}
              <button
                className="google-btn"
                type="button"
                disabled={form.isSubmitting}
              >
                Авторизация через Google
              </button>

              {/* Auth form */}
              <form className="auth-form" onSubmit={form.handleSubmit}>
              {isLogin && (
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

              {!isLogin && (
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
                    disabled={form.isSubmitting || isAwaitingEmailCode}
                    className={form.errors.email ? 'error' : ''}
                    autoComplete="email"
                  />
                  {form.touched.email && form.errors.email && (
                    <span className="error-message">{form.errors.email}</span>
                  )}
                </div>
              )}

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

              {!isLogin && isAwaitingEmailCode && (
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

              {!isLogin && !isAwaitingEmailCode && (
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
                  : isLogin
                    ? 'Войти'
                    : isAwaitingEmailCode
                      ? 'Подтвердить код'
                      : 'Создать аккаунт'}
              </button>
              {!isLogin && isAwaitingEmailCode && (
                <button
                  type="button"
                  className="btn btn-continue"
                  disabled={form.isSubmitting}
                  onClick={resendEmailCode}
                >
                  Отправить код повторно
                </button>
              )}
              </form>
            </div>

            <div className="auth-form-footer">
              {/* Toggle Auth Mode */}
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

              {isLogin && (
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