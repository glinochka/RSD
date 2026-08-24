import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import '../../../styles/projectLayout.css';
import '../../../styles/projectSettingsPage.css';

const CustomNewSolutionPage = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    client_name: '',
    industry: '',
    description: '',
  });
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const created = await customService.createAutomation(form);
      navigate(NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(created.id));
    } catch (err) {
      setError(err.message || 'Не удалось создать решение');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="project-layout">
      <header className="project-topbar">
        <div className="project-topbar-left">
          <button
            type="button"
            className="project-topbar-back"
            onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN)}
          >
            Назад
          </button>
          <h1 className="project-topbar-title">Новое решение</h1>
        </div>
      </header>
      <main className="project-content">
        <div className="project-settings-page">
          <div className="settings-header">
            <div>
              <h2 className="settings-title">Новое решение</h2>
              <p className="settings-subtitle">Название и клиент. Модули включите в настройках после создания.</p>
            </div>
          </div>
          {error ? <p className="form-hint">{error}</p> : null}
          <form className="settings-form" onSubmit={handleSubmit}>
            <div className="settings-section">
              <div className="form-group">
                <label htmlFor="name">Название</label>
                <input id="name" name="name" type="text" value={form.name} onChange={handleChange} required />
              </div>
              <div className="form-group">
                <label htmlFor="client_name">Клиент</label>
                <input id="client_name" name="client_name" type="text" value={form.client_name} onChange={handleChange} />
              </div>
              <div className="form-group">
                <label htmlFor="industry">Индустрия</label>
                <input
                  id="industry"
                  name="industry"
                  type="text"
                  value={form.industry}
                  onChange={handleChange}
                  placeholder="seo_saas / fulfillment"
                />
              </div>
              <div className="form-group">
                <label htmlFor="description">Описание</label>
                <textarea id="description" name="description" value={form.description} onChange={handleChange} rows={4} />
              </div>
            </div>
            <div className="settings-actions">
              <button type="submit" className="btn btn-black" disabled={isSaving}>
                {isSaving ? 'Создание...' : 'Создать'}
              </button>
              <button type="button" className="btn btn-outline" onClick={() => navigate(NAVIGATION_ROUTES.CUSTOM_ADMIN)}>
                Отмена
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
};

export default CustomNewSolutionPage;
