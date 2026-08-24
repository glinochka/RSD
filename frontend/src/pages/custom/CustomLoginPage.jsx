import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCustomAuth } from '../../components/custom/useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';

const CustomLoginPage = () => {
  const navigate = useNavigate();
  const { login, isAuthenticated, isAdmin, automationId } = useCustomAuth();
  const [mode, setMode] = useState('admin'); // 'admin' | 'automation'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Redirect if already logged in
  if (isAuthenticated) {
    if (isAdmin) {
      navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_DASHBOARD, { replace: true });
      return null;
    }
    if (automationId) {
      navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(automationId), { replace: true });
      return null;
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const response = await login(username, password, mode);
      if (response.custom_admin) {
        navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN_DASHBOARD, { replace: true });
      } else if (response.custom_automation_id) {
        navigate(
          NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(response.custom_automation_id),
          { replace: true },
        );
      }
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-lg shadow p-8">
        <h1 className="text-xl font-semibold mb-6 text-center">Вход в кастомные агенты</h1>

        <div className="flex gap-2 mb-6">
          <button
            type="button"
            onClick={() => setMode('admin')}
            className={`flex-1 py-2 rounded text-sm font-medium ${
              mode === 'admin' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'
            }`}
          >
            Админ
          </button>
          <button
            type="button"
            onClick={() => setMode('automation')}
            className={`flex-1 py-2 rounded text-sm font-medium ${
              mode === 'automation' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'
            }`}
          >
            Клиент
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Логин</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full border rounded px-3 py-2"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Пароль</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded px-3 py-2"
              required
            />
          </div>

          {error && <div className="text-red-600 text-sm">{error}</div>}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 text-white rounded py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default CustomLoginPage;
