/**
 * Navbar Component
 * Main navigation header with auth state handling
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import authService from '../services/authService';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/navbar.css';

function ProfilePersonIcon({ className }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v1c0 .55.45 1 1 1h14c.55 0 1-.45 1-1v-1c0-2.66-5.33-4-8-4z"
        fill="currentColor"
      />
    </svg>
  );
}

const Navbar = () => {
  const { isAuthenticated, user, logout, setUser } = useAuth();
  const { showError, showInfo, showSuccess } = useNotification();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isTelegramLinked, setIsTelegramLinked] = useState(!!user?.telegram_id);
  const [telegramLinkCode, setTelegramLinkCode] = useState('');
  const [telegramLinkExpiresAt, setTelegramLinkExpiresAt] = useState('');
  const [isStartingTelegramLink, setIsStartingTelegramLink] = useState(false);
  const [isCheckingTelegramLink, setIsCheckingTelegramLink] = useState(false);
  const profilePanelId = useId();
  const profilePanelRef = useRef(null);

  const displayName = user?.name || user?.email || 'Пользователь';

  const handleLogout = async () => {
    try {
      setIsProfileOpen(false);
      await logout();
      navigate(NAVIGATION_ROUTES.HOME);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const closeProfile = () => setIsProfileOpen(false);

  const toggleProfile = () => {
    setIsMenuOpen(false);
    setIsProfileOpen((open) => !open);
  };

  useEffect(() => {
    if (!isProfileOpen) return undefined;

    const onKeyDown = (e) => {
      if (e.key === 'Escape') closeProfile();
    };

    document.addEventListener('keydown', onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [isProfileOpen]);

  useEffect(() => {
    if (!isProfileOpen) return;
    const t = window.setTimeout(() => {
      profilePanelRef.current?.querySelector('.profile-drawer-close')?.focus();
    }, 0);
    return () => window.clearTimeout(t);
  }, [isProfileOpen]);

  useEffect(() => {
    if (!isAuthenticated || !isProfileOpen) return;

    let cancelled = false;
    const loadCurrentUser = async () => {
      try {
        const me = await authService.getCurrentUser();
        if (cancelled) return;
        const linked = !!me?.telegram_id;
        setIsTelegramLinked(linked);
        setUser((prev) => ({ ...(prev || {}), name: me?.name ?? prev?.name, telegram_id: me?.telegram_id ?? null }));
        if (linked) {
          setTelegramLinkCode('');
          setTelegramLinkExpiresAt('');
        }
      } catch (error) {
        if (!cancelled) {
          showError(error?.message || 'Не удалось загрузить профиль');
        }
      }
    };

    loadCurrentUser();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, isProfileOpen, setUser, showError]);

  const handleStartTelegramLink = async () => {
    try {
      setIsStartingTelegramLink(true);
      const result = await authService.startTelegramLink();
      setTelegramLinkCode(result?.code || '');
      setTelegramLinkExpiresAt(result?.expires_at || '');
      showInfo('Код сгенерирован. Отправьте его в мастер-бот: /link <код>', 5000);
    } catch (error) {
      showError(error?.message || 'Не удалось сгенерировать код привязки');
    } finally {
      setIsStartingTelegramLink(false);
    }
  };

  const handleCheckTelegramLink = async () => {
    try {
      setIsCheckingTelegramLink(true);
      const me = await authService.getCurrentUser();
      const linked = !!me?.telegram_id;
      setIsTelegramLinked(linked);
      setUser((prev) => ({ ...(prev || {}), name: me?.name ?? prev?.name, telegram_id: me?.telegram_id ?? null }));
      if (linked) {
        setTelegramLinkCode('');
        setTelegramLinkExpiresAt('');
        showSuccess('Telegram успешно привязан', 3000);
      } else {
        showInfo('Привязка пока не завершена. После команды /link проверьте еще раз.', 4000);
      }
    } catch (error) {
      showError(error?.message || 'Не удалось проверить статус привязки');
    } finally {
      setIsCheckingTelegramLink(false);
    }
  };

  const handleCopyTelegramCode = async () => {
    if (!telegramLinkCode) return;
    try {
      await navigator.clipboard.writeText(telegramLinkCode);
      showSuccess('Код скопирован', 2500);
    } catch {
      showError('Не удалось скопировать код');
    }
  };

  return (
    <>
      <header className="header">
        <Link className="logo" to={NAVIGATION_ROUTES.HOME}>
          RSD
        </Link>

        <nav className={`nav ${isMenuOpen ? 'nav-open' : ''}`}>
          <Link to={NAVIGATION_ROUTES.AGENTS}>Мои агенты</Link>
          <Link to={NAVIGATION_ROUTES.CREATE_AGENT}>Создать агента</Link>
          <Link to={NAVIGATION_ROUTES.DOCUMENTATION}>Документация</Link>
          <Link to={NAVIGATION_ROUTES.PRICING}>Цены</Link>
        </nav>

        <div className="navbar-actions">
          {isAuthenticated ? (
            <button
              type="button"
              className={`profile-menu-trigger${isProfileOpen ? ' profile-menu-trigger--active' : ''}`}
              onClick={toggleProfile}
              aria-expanded={isProfileOpen}
              aria-controls={profilePanelId}
              aria-haspopup="dialog"
              aria-label="Меню профиля"
            >
              <ProfilePersonIcon className="profile-menu-trigger-icon" />
            </button>
          ) : (
            <Link className="btn btn-black btn-auth" to={NAVIGATION_ROUTES.AUTH}>
              Вход
            </Link>
          )}
          <button
            className="menu-toggle"
            type="button"
            onClick={toggleMenu}
            aria-label="Открыть меню"
            aria-expanded={isMenuOpen}
          >
            <span></span>
            <span></span>
            <span></span>
          </button>
        </div>
      </header>

      {isAuthenticated && isProfileOpen && (
        <>
          <div
            className="profile-drawer-backdrop"
            onClick={closeProfile}
            role="presentation"
            aria-hidden="true"
          />
          <aside
            ref={profilePanelRef}
            id={profilePanelId}
            className="profile-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-drawer-title"
          >
            <div className="profile-drawer-header">
              <h2 id="profile-drawer-title" className="profile-drawer-title">
                Профиль
              </h2>
              <button
                type="button"
                className="profile-drawer-close"
                onClick={closeProfile}
                aria-label="Свернуть меню профиля"
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>

            <div className="profile-drawer-body">
              <div className="profile-drawer-avatar" aria-hidden="true">
                <ProfilePersonIcon className="profile-drawer-avatar-icon" />
              </div>
              <p className="profile-drawer-label">Имя пользователя</p>
              <p className="profile-drawer-name" title={displayName}>
                {displayName}
              </p>
              <p className="profile-drawer-hint">
                Управляйте агентами через разделы «Мои агенты» и «Создать агента» в шапке сайта.
              </p>
              <div className="profile-telegram-link-box">
                <p className="profile-telegram-link-title">Связь с мастер-ботом</p>
                {isTelegramLinked ? (
                  <p className="profile-telegram-link-status success">Telegram уже привязан к аккаунту.</p>
                ) : (
                  <>
                    <p className="profile-telegram-link-status">
                      Чтобы привязать аккаунт, сгенерируйте код и отправьте его в мастер-боте: <code>/link &lt;код&gt;</code>
                    </p>
                    {telegramLinkCode ? (
                      <div className="profile-telegram-link-code-wrap">
                        <p className="profile-telegram-link-code">{telegramLinkCode}</p>
                        <div className="profile-telegram-link-actions">
                          <button
                            type="button"
                            className="btn btn-outline profile-drawer-btn"
                            onClick={handleCopyTelegramCode}
                          >
                            Скопировать код
                          </button>
                          <button
                            type="button"
                            className="btn btn-outline profile-drawer-btn"
                            onClick={handleCheckTelegramLink}
                            disabled={isCheckingTelegramLink}
                          >
                            {isCheckingTelegramLink ? 'Проверка...' : 'Проверить привязку'}
                          </button>
                        </div>
                        {telegramLinkExpiresAt && (
                          <p className="profile-telegram-link-expire">
                            Код действует до {new Date(telegramLinkExpiresAt).toLocaleString()}.
                          </p>
                        )}
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-outline profile-drawer-btn"
                        onClick={handleStartTelegramLink}
                        disabled={isStartingTelegramLink}
                      >
                        {isStartingTelegramLink ? 'Генерация...' : 'Связать TG'}
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>

            <div className="profile-drawer-footer">
              <button type="button" className="btn btn-black profile-drawer-btn" onClick={handleLogout}>
                Выйти
              </button>
              <button type="button" className="btn btn-outline profile-drawer-btn" onClick={closeProfile}>
                Свернуть
              </button>
            </div>
          </aside>
        </>
      )}
    </>
  );
};

export default Navbar;