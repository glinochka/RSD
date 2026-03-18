/**
 * Main Page
 * Landing page with features overview
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import MainLayout from '../components/Layout';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/main.css';

const FEATURES = [
  {
    id: 'simplicity',
    title: 'Простоты',
    items: [
      'Выберите роль агента',
      'Напишите промпт',
      'Загрузите файлы',
      'Получите ИИ-агента',
    ],
  },
  {
    id: 'security',
    title: 'Безопасности',
    description: 'Будьте спокойны благодаря надежному шифрованию и строгим стандартам соответствия.',
  },
  {
    id: 'bigdata',
    title: 'Больших данных',
    description: 'Наш уникальный алгоритм умеет сортировать и отбирать лишь релевантную информацию.',
  },
];

const Main = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const handleCreateAgent = () => {
    if (isAuthenticated) {
      navigate(NAVIGATION_ROUTES.CREATE_AGENT);
    } else {
      navigate(NAVIGATION_ROUTES.AUTH);
    }
  };

  return (
    <MainLayout>
      <div className="main-content">
        <section className="hero">
          <div className="hero-content">
            <h1>Ваш бизнес.</h1>
            <div className="highlight">Ваши знания.</div>
            <h2>Ваш сотрудник.</h2>
            <p className="description">
              RSD — это no-code платформа для создания агентов искусственного интеллекта для поддержки вашего бизнеса.
            </p>
            <button className="btn btn-black" onClick={handleCreateAgent}>
              Создать агента
            </button>
          </div>
          <div className="media-placeholder">МЕДИА</div>
        </section>

        <section className="features">
          <h3>Наша платформа разработана для:</h3>
          <div className="features-grid">
            {FEATURES.map((feature) => (
              <div key={feature.id} className="feature-card">
                <h4>{feature.title}</h4>
                {feature.items ? (
                  <ul>
                    {feature.items.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p>{feature.description}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </MainLayout>
  );
};

export default Main;