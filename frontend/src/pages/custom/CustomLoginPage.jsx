import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCustomAuth } from '../../components/custom/useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';
import '../../styles/managementPortal.css';

const CustomLoginPage = () => {
  const navigate = useNavigate();
  const { login, isAuthenticated, isAdmin, automationId } = useCustomAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }
    if (isAdmin) {
      navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_DASHBOARD, { replace: true });
      return;
    }
    if (automationId) {
      navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(automationId), { replace: true });
    }
  }, [automationId, isAdmin, isAuthenticated, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password) {
      setError('Введите логин и пароль');
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await login(username.trim(), password);
      if (response.custom_admin) {
        navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_DASHBOARD, { replace: true });
      } else if (response.custom_automation_id) {
        navigate(
          NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(response.custom_automation_id),
          { replace: true },
        );
      }
    } catch (err) {
      setError(err.message || 'Неверный логин или пароль');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="management-page">
      <header className="management-header">
        <h1>Кастомные агенты</h1>
      </header>

      <main className="management-login-wrap">
        <div className="management-login-portal-shell">
          <div className="management-login-portal-header">
            <p className="management-login-portal-eyebrow">RSD Custom</p>
            <h2 className="management-login-portal-title">Вход в панель</h2>
            <p className="management-login-portal-subtitle">
              Один вход для администратора и клиента автоматизации
            </p>
          </div>

          <form className="management-login-card" onSubmit={handleSubmit}>
            <h2>Вход</h2>

            <label htmlFor="custom-login">Логин</label>
            <input
              id="custom-login"
              type="text"
              className="management-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              disabled={isSubmitting}
            />

            <label htmlFor="custom-password">Пароль</label>
            <input
              id="custom-password"
              type="password"
              className="management-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={isSubmitting}
            />

            {error && <div className="management-error">{error}</div>}

            <button type="submit" className="btn btn-black management-login-btn" disabled={isSubmitting}>
              {isSubmitting ? 'Проверка...' : 'Войти'}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};

export default CustomLoginPage;
