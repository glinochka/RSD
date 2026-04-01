/**
 * Auth Page
 * Handles user login and registration.
 * Field names and validation match backend (router_users/schemas.py): name, password.
 */

import React, { useMemo, useState } from 'react';

/** Message for auth UI: apiClient sets error.message from FastAPI detail (normalized). */
function getAuthErrorMessage(error) {
  if (error?.message) return error.message;
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
  password: '',
  consentPersonal: false,
  consentTerms: false,
};

const Auth = () => {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [isLogin, setIsLogin] = useState(true);

  // Validation rules aligned with backend Pydantic: LoginUser (name 3-30), NewUser (name 3-32), password 6-30
  const authRules = useMemo(() => {
    const base = {
      name: {
        required: true,
        type: 'username',
        label: 'Имя пользователя',
        maxLength: isLogin ? VALIDATION.USERNAME_MAX_LENGTH_LOGIN : VALIDATION.USERNAME_MAX_LENGTH_REGISTER,
      },
      password: { required: true, type: 'password', label: 'Пароль' },
    };
    if (isLogin) return base;
    return {
      ...base,
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
  }, [isLogin]);

  const form = useForm(
    AUTH_FORM_INITIAL,
    async (values) => {
      try {
        if (isLogin) {
          await login(values.name, values.password);
          showSuccess(SUCCESS_MESSAGES.LOGIN_SUCCESS, 3000);
        } else {
          await register(values.name, values.password);
          showSuccess('Регистрация успешна!', 3000);
        }
        navigate(NAVIGATION_ROUTES.AGENTS);
      } catch (error) {
        showError(getAuthErrorMessage(error));
      }
    },
    authRules
  );

  const toggleAuthMode = () => {
    form.reset();
    setIsLogin(!isLogin);
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

              {/* Auth Form — fields match backend: name, password */}
              <form className="auth-form" onSubmit={form.handleSubmit}>
              <div className="form-group">
                <label htmlFor="name">Имя пользователя:</label>
                <input
                  id="name"
                  type="text"
                  name="name"
                  placeholder={isLogin ? 'Имя пользователя' : 'От 3 до 32 символов'}
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
                  disabled={form.isSubmitting}
                  className={form.errors.password ? 'error' : ''}
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                />
                {form.touched.password && form.errors.password && (
                  <span className="error-message">{form.errors.password}</span>
                )}
              </div>

              {!isLogin && (
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
                {form.isSubmitting ? 'Обработка...' : isLogin ? 'Войти' : 'Создать аккаунт'}
              </button>
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