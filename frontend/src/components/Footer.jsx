import React from 'react';
import { Link } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/footer.css';

const CURRENT_YEAR = new Date().getFullYear();

const Footer = () => {
  return (
    <footer className="site-footer" aria-label="Подвал сайта">
      <div className="site-footer__inner">
        <div className="site-footer__top">
          <section className="site-footer__section">
            <h2 className="site-footer__title">RSD</h2>
            <p className="site-footer__text">
              Платформа для запуска ИИ-агентов под поддержку, продажи и внутренние процессы.
            </p>
          </section>

          <section className="site-footer__section">
            <h2 className="site-footer__title">Контакты</h2>
            <ul className="site-footer__list">
              <li>
                Email:{' '}
                <a href="mailto:support@rsd.ai" className="site-footer__link">
                  support@rsd.ai
                </a>
              </li>
              <li>Режим обработки обращений: ежедневно, 09:00-21:00 (МСК)</li>
              <li>По вопросам ПДн и юридическим запросам: через email поддержки</li>
            </ul>
          </section>

          <section className="site-footer__section">
            <h2 className="site-footer__title">Юридическая информация</h2>
            <ul className="site-footer__list">
              <li>
                <Link to={NAVIGATION_ROUTES.PUBLIC_OFFER} className="site-footer__link">
                  Публичная оферта
                </Link>
              </li>
              <li>
                <Link to={NAVIGATION_ROUTES.USER_AGREEMENT} className="site-footer__link">
                  Пользовательское соглашение
                </Link>
              </li>
              <li>
                <Link to={NAVIGATION_ROUTES.PRIVACY_POLICY} className="site-footer__link">
                  Политика конфиденциальности (152-ФЗ)
                </Link>
              </li>
            </ul>
          </section>

          <section className="site-footer__section">
            <h2 className="site-footer__title">Информация</h2>
            <ul className="site-footer__list">
              <li>
                <Link to={NAVIGATION_ROUTES.DOCUMENTATION} className="site-footer__link">
                  Документация
                </Link>
              </li>
              <li>
                <Link to={NAVIGATION_ROUTES.PRICING} className="site-footer__link">
                  Тарифы
                </Link>
              </li>
              <li>Оператор сервиса: реквизиты предоставляются по запросу</li>
            </ul>
          </section>
        </div>

        <div className="site-footer__bottom">
          <p className="site-footer__copyright">
            © {CURRENT_YEAR} RSD. Все права защищены.
          </p>
          <p className="site-footer__disclaimer">
            Информация на сайте не является публичной офертой, кроме раздела с условиями оферты.
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
