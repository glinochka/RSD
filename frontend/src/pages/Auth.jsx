/**
 * Auth Page
 * Handles user login and registration
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import { useForm } from '../hooks/useForm';
import { NAVIGATION_ROUTES, SUCCESS_MESSAGES } from '../config/constants';
import '../styles/auth.css';

const Auth = () => {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const { showError, showSuccess } = useNotification();
  const [isLogin, setIsLogin] = useState(true);

  const authRules = {
    email: { required: true, type: 'email', label: 'Email' },
    password: { required: true, type: 'password', label: 'Пароль' },
    ...(isLogin ? {} : { name: { required: true, label: 'Имя' } }),
  };

  const form = useForm(
    { email: '', password: '', name: '' },
    async (values) => {
      try {
        if (isLogin) {
          await login(values.email, values.password);
          showSuccess(SUCCESS_MESSAGES.LOGIN_SUCCESS, 3000);
        } else {
          await register(values.email, values.password, values.name);
          showSuccess('Регистрация успешна!', 3000);
        }
        navigate(NAVIGATION_ROUTES.AGENTS);
      } catch (error) {
        const message = error.message || 'Ошибка входа. Проверьте учетные данные.';
        showError(message);
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

            {/* Auth Form */}
            <form className="auth-form" onSubmit={form.handleSubmit}>
              {!isLogin && (
                <div className="form-group">
                  <label htmlFor="name">Имя:</label>
                  <input
                    id="name"
                    type="text"
                    name="name"
                    placeholder="Ваше имя"
                    value={form.values.name}
                    onChange={form.handleChange}
                    onBlur={form.handleBlur}
                    disabled={form.isSubmitting}
                    className={form.errors.name ? 'error' : ''}
                  />
                  {form.touched.name && form.errors.name && (
                    <span className="error-message">{form.errors.name}</span>
                  )}
                </div>
              )}

              <div className="form-group">
                <label htmlFor="email">Электронная почта:</label>
                <input
                  id="email"
                  type="email"
                  name="email"
                  placeholder="example@email.com"
                  value={form.values.email}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  className={form.errors.email ? 'error' : ''}
                />
                {form.touched.email && form.errors.email && (
                  <span className="error-message">{form.errors.email}</span>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="password">Пароль:</label>
                <input
                  id="password"
                  type="password"
                  name="password"
                  placeholder="••••••••"
                  value={form.values.password}
                  onChange={form.handleChange}
                  onBlur={form.handleBlur}
                  disabled={form.isSubmitting}
                  className={form.errors.password ? 'error' : ''}
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