/**
 * Navbar Component
 * Main navigation header with auth state handling
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useNotification } from '../context/useNotification';
import authService from '../services/authService';
import errorReportService from '../services/errorReportService';
import { NAVIGATION_ROUTES } from '../config/constants';
import { normalizeDetail } from '../utils/errorUtils';
import PaymentMethodsModal from './PaymentMethodsModal';
import CreateChoiceModal from './CreateChoiceModal';
import '../styles/navbar.css';

const PROFILE_DRAWER_CLOSE_MS = 380;
const ERROR_REPORT_CLOSE_MS = 300;

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
  const [isProfileClosing, setIsProfileClosing] = useState(false);
  const [isPaymentMethodsOpen, setIsPaymentMethodsOpen] = useState(false);
  const [isCreateChoiceOpen, setIsCreateChoiceOpen] = useState(false);
  const [isTelegramLinked, setIsTelegramLinked] = useState(!!user?.telegram_id);
  const [isTelegramFormOpen, setIsTelegramFormOpen] = useState(false);
  const [telegramUsernameInput, setTelegramUsernameInput] = useState('');
  const [telegramLinkCode, setTelegramLinkCode] = useState('');
  const [telegramLinkExpiresAt, setTelegramLinkExpiresAt] = useState('');
  const [telegramLinkRemainingSeconds, setTelegramLinkRemainingSeconds] = useState(0);
  const [isStartingTelegramLink, setIsStartingTelegramLink] = useState(false);
  const [isCheckingTelegramLink, setIsCheckingTelegramLink] = useState(false);
  const [isErrorReportOpen, setIsErrorReportOpen] = useState(false);
  const [isErrorReportClosing, setIsErrorReportClosing] = useState(false);
  const [errorReportText, setErrorReportText] = useState('');
  const [isSendingErrorReport, setIsSendingErrorReport] = useState(false);
  const profilePanelId = useId();
  const profilePanelRef = useRef(null);

  const displayName = user?.name || user?.email || 'Пользователь';

  const handleLogout = async () => {
    try {
      closeProfile({ immediate: true });
      await logout();
      navigate(NAVIGATION_ROUTES.HOME);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const toggleMenu = () => {
    if (!isMenuOpen) {
      closeProfile({ immediate: true });
    }
    setIsMenuOpen((open) => !open);
  };

  const closeMobileNav = () => {
    setIsMenuOpen(false);
  };

  const closeErrorReport = ({ immediate = false } = {}) => {
    if (!isErrorReportOpen) return;
    if (immediate) {
      setIsErrorReportClosing(false);
      setIsErrorReportOpen(false);
      setErrorReportText('');
      return;
    }
    if (isErrorReportClosing) return;
    setIsErrorReportClosing(true);
    window.setTimeout(() => {
      setIsErrorReportClosing(false);
      setIsErrorReportOpen(false);
      setErrorReportText('');
    }, ERROR_REPORT_CLOSE_MS);
  };

  const closeProfile = ({ immediate = false } = {}) => {
    if (!isProfileOpen && !isProfileClosing) return;
    closeErrorReport({ immediate: true });
    if (immediate) {
      setIsProfileClosing(false);
      setIsProfileOpen(false);
      return;
    }
    if (isProfileClosing) return;
    setIsProfileClosing(true);
    window.setTimeout(() => {
      setIsProfileClosing(false);
      setIsProfileOpen(false);
    }, PROFILE_DRAWER_CLOSE_MS);
  };

  const toggleProfile = () => {
    if (isProfileOpen) {
      closeProfile();
      return;
    }
    setIsMenuOpen(false);
    setIsProfileClosing(false);
    setIsProfileOpen(true);
  };

  useEffect(() => {
    if (!isProfileOpen) return undefined;

    const onKeyDown = (e) => {
      if (e.key !== 'Escape') return;
      if (isErrorReportOpen) {
        closeErrorReport();
        return;
      }
      closeProfile();
    };

    document.addEventListener('keydown', onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [isProfileOpen, isErrorReportOpen, isErrorReportClosing]);

  useEffect(() => {
    if (!isProfileOpen) return;
    const t = window.setTimeout(() => {
      profilePanelRef.current?.querySelector('.profile-drawer-close')?.focus();
    }, 0);
    return () => window.clearTimeout(t);
  }, [isProfileOpen]);

  const normalizeTelegramUsernameInput = (value) => {
    const compact = (value || '').replace(/\s+/g, '');
    if (!compact) return '';
    const withPrefix = compact.startsWith('@') ? compact : `@${compact}`;
    const sanitizedBody = withPrefix.slice(1).replace(/[^A-Za-z0-9_]/g, '').slice(0, 32);
    return `@${sanitizedBody}`;
  };

  const formatSeconds = (totalSeconds) => {
    const safe = Math.max(0, totalSeconds || 0);
    const minutes = Math.floor(safe / 60);
    const seconds = safe % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

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
          setIsTelegramFormOpen(false);
          setTelegramLinkCode('');
          setTelegramLinkExpiresAt('');
          setTelegramLinkRemainingSeconds(0);
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

  useEffect(() => {
    if (!telegramLinkExpiresAt) {
      setTelegramLinkRemainingSeconds(0);
      return undefined;
    }

    const updateRemaining = () => {
      const expiresAtMs = new Date(telegramLinkExpiresAt).getTime();
      const diffSeconds = Math.max(0, Math.ceil((expiresAtMs - Date.now()) / 1000));
      setTelegramLinkRemainingSeconds(diffSeconds);
      if (diffSeconds === 0) {
        setTelegramLinkCode('');
        setTelegramLinkExpiresAt('');
      }
    };

    updateRemaining();
    const timerId = window.setInterval(updateRemaining, 1000);
    return () => window.clearInterval(timerId);
  }, [telegramLinkExpiresAt]);

  const handleStartTelegramLink = async () => {
    const username = telegramUsernameInput.trim();
    if (!/^@[A-Za-z0-9_]{3,32}$/.test(username)) {
      showError('Введите Telegram username в формате @asd123');
      return;
    }
    try {
      setIsStartingTelegramLink(true);
      const result = await authService.startTelegramLink(username);
      setTelegramLinkCode(result?.code || '');
      setTelegramLinkExpiresAt(result?.expires_at || '');
      setTelegramLinkRemainingSeconds(Number(result?.expires_in_seconds || 0));
      setIsTelegramFormOpen(false);
      setTelegramUsernameInput('');
      showInfo('Код сгенерирован. Проверьте сообщение в мастер-боте и отправьте туда 6-значный код.', 5000);
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
        setIsTelegramFormOpen(false);
        setTelegramLinkCode('');
        setTelegramLinkExpiresAt('');
        setTelegramLinkRemainingSeconds(0);
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

  const handleSubmitErrorReport = async () => {
    const text = errorReportText.trim();
    if (text.length < 10) {
      showError('Опишите проблему не менее чем в 10 символах');
      return;
    }
    try {
      setIsSendingErrorReport(true);
      await errorReportService.submit(text);
      closeErrorReport({ immediate: true });
      showSuccess('Спасибо, мы получили ваше сообщение', 4000);
    } catch (error) {
      const msg =
        normalizeDetail(error?.response?.data?.detail) ||
        error?.message ||
        'Не удалось отправить сообщение';
      showError(msg);
    } finally {
      setIsSendingErrorReport(false);
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

        <nav
          className={`nav ${isMenuOpen ? 'nav-open' : ''}`}
          onClick={(e) => {
            if (e.target.closest('a')) closeMobileNav();
          }}
        >
          {isAuthenticated ? (
            <Link to={NAVIGATION_ROUTES.PROJECTS_LIST}>Решения</Link>
          ) : (
            <Link to={NAVIGATION_ROUTES.PROJECTS_LIST}>Мои агенты</Link>
          )}
          <button
            type="button"
            className="navbar-link-button"
            onClick={() => setIsCreateChoiceOpen(true)}
          >
            Новое решение
          </button>
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
            className={`profile-drawer-backdrop${isProfileClosing ? ' profile-drawer-backdrop--closing' : ''}`}
            onClick={() => closeProfile()}
            role="presentation"
            aria-hidden="true"
          />
          <aside
            ref={profilePanelRef}
            id={profilePanelId}
            className={`profile-drawer${isProfileClosing ? ' profile-drawer--closing' : ''}`}
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
                Управляйте ИИ-агентами и сайтами в разделе «Решения».
              </p>
              <div className="profile-telegram-link-box">
                <p className="profile-telegram-link-title">Связь с мастер-ботом</p>
                {isTelegramLinked ? (
                  <p className="profile-telegram-link-status success">Telegram уже привязан к аккаунту.</p>
                ) : (
                  <>
                    <p className="profile-telegram-link-status">
                      Нажмите «Связать TG», укажите username в формате <code>@username</code>, затем введите код в боте.
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
                            Код действителен: {formatSeconds(telegramLinkRemainingSeconds)}
                          </p>
                        )}
                      </div>
                    ) : (
                      <>
                        {!isTelegramFormOpen ? (
                          <button
                            type="button"
                            className="btn btn-outline profile-drawer-btn"
                            onClick={() => setIsTelegramFormOpen(true)}
                          >
                            Связать TG
                          </button>
                        ) : (
                          <div className="profile-telegram-link-form">
                            <input
                              type="text"
                              value={telegramUsernameInput}
                              onChange={(e) => setTelegramUsernameInput(normalizeTelegramUsernameInput(e.target.value))}
                              className="profile-telegram-link-input"
                              placeholder="@asd123"
                              autoComplete="off"
                            />
                            <div className="profile-telegram-link-actions">
                              <button
                                type="button"
                                className="btn btn-outline profile-drawer-btn"
                                onClick={handleStartTelegramLink}
                                disabled={isStartingTelegramLink}
                              >
                                {isStartingTelegramLink ? 'Отправка...' : 'Отправить код в бот'}
                              </button>
                              <button
                                type="button"
                                className="btn btn-outline profile-drawer-btn"
                                onClick={() => {
                                  setIsTelegramFormOpen(false);
                                  setTelegramUsernameInput('');
                                }}
                                disabled={isStartingTelegramLink}
                              >
                                Отмена
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
            </div>

            <div className="profile-drawer-footer">
              <button
                type="button"
                className="btn btn-outline profile-drawer-btn"
                onClick={() => {
                  setIsPaymentMethodsOpen(true);
                }}
              >
                Способы оплаты
              </button>
              <button
                type="button"
                className="btn btn-outline profile-drawer-btn"
                onClick={() => {
                  closeProfile();
                  navigate(NAVIGATION_ROUTES.PARTNER);
                }}
              >
                Партнёрам
              </button>
              <button
                type="button"
                className="btn btn-outline profile-drawer-btn"
                onClick={() => setIsErrorReportOpen(true)}
              >
                Сообщить об ошибке
              </button>
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

      {isAuthenticated && isErrorReportOpen && (
        <div
          className={`profile-error-report-overlay${isErrorReportClosing ? ' profile-error-report-overlay--closing' : ''}`}
          role="presentation"
          onClick={() => closeErrorReport()}
        >
          <div
            className={`profile-error-report-dialog${isErrorReportClosing ? ' profile-error-report-dialog--closing' : ''}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-error-report-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="profile-error-report-intro">
              <h3 id="profile-error-report-title" className="profile-error-report-title">
                Сообщить об ошибке
              </h3>
              <p className="profile-error-report-hint">
                Опишите, что пошло не так: страница, действия и ожидаемый результат. Минимум 10 символов.
              </p>
            </div>
            <textarea
              className="profile-error-report-textarea"
              value={errorReportText}
              onChange={(e) => setErrorReportText(e.target.value)}
              rows={6}
              maxLength={8000}
              placeholder="Например: на странице «Мои агенты» после нажатия…"
              disabled={isSendingErrorReport}
            />
            <div className="profile-error-report-actions">
              <button
                type="button"
                className="btn btn-black profile-drawer-btn"
                disabled={isSendingErrorReport || errorReportText.trim().length < 10}
                onClick={handleSubmitErrorReport}
              >
                {isSendingErrorReport ? 'Отправка...' : 'Отправить'}
              </button>
              <button
                type="button"
                className="btn btn-outline profile-drawer-btn"
                disabled={isSendingErrorReport}
                onClick={() => closeErrorReport()}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      <PaymentMethodsModal
        isOpen={isPaymentMethodsOpen}
        onClose={() => setIsPaymentMethodsOpen(false)}
      />

      <CreateChoiceModal
        isOpen={isCreateChoiceOpen}
        onClose={() => setIsCreateChoiceOpen(false)}
      />
    </>
  );
};

export default Navbar;