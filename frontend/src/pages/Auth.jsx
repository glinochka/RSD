/**
 * Auth Page
 * Handles user login and registration.
 * Field names and validation match backend (router_users/schemas.py): name, password.
 */

import React, { useState } from 'react';

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
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import { useForm } from '../hooks/useForm';
import { NAVIGATION_ROUTES, SUCCESS_MESSAGES, VALIDATION } from '../config/constants';
import '../styles/auth.css';

const Auth = () => {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [isLogin, setIsLogin] = useState(true);

  // Validation rules aligned with backend Pydantic: LoginUser (name 3-30), NewUser (name 3-32), password 6-30
  const authRules = {
    name: {
      required: true,
      type: 'username',
      label: 'Имя пользователя',
      maxLength: isLogin ? VALIDATION.USERNAME_MAX_LENGTH_LOGIN : VALIDATION.USERNAME_MAX_LENGTH_REGISTER,
    },
    password: { required: true, type: 'password', label: 'Пароль' },
  };

  const form = useForm(
    { name: '', password: '' },
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

              <button
                type="submit"
                className="btn btn-continue"
                disabled={form.isSubmitting}
              >
                {form.isSubmitting ? 'Обработка...' : isLogin ? 'Войти' : 'Создать аккаунт'}
              </button>
            </form>

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

            <p className="terms">
              {isLogin ? (
                <>Продолжая, вы соглашаетесь с нашими Условиями предоставления услуг и
                Политикой конфиденциальности.</>
              ) : (
                <>Регистрируясь, вы принимаете наши Условия предоставления услуг и
                Политику конфиденциальности.</>
              )}
            </p>
          </div>

          <div className="auth-media-side">
            <div className="media-placeholder">МЕДИА</div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Auth;