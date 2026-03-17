/**
 * Navbar Component
 * Main navigation header with auth state handling
 */

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/navbar.css';

const Navbar = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
      navigate(NAVIGATION_ROUTES.HOME);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  return (
    <header className="header">
      <Link className="logo" to={NAVIGATION_ROUTES.HOME}>
        RSD
      </Link>

      <nav className={`nav ${isMenuOpen ? 'nav-open' : ''}`}>
        <Link to={NAVIGATION_ROUTES.AGENTS}>Мои агенты</Link>
        <Link to={NAVIGATION_ROUTES.CREATE_AGENT}>Создать агента</Link>
        <Link to={NAVIGATION_ROUTES.PRICING}>Цены</Link>
      </nav>

      <div className="navbar-actions">
        {isAuthenticated ? (
          <div className="user-menu">
            <span className="user-name">{user?.name || user?.email}</span>
            <button className="btn btn-outline btn-logout" onClick={handleLogout}>
              Выход
            </button>
          </div>
        ) : (
          <Link className="btn btn-black btn-auth" to={NAVIGATION_ROUTES.AUTH}>
            Вход
          </Link>
        )}
      </div>

      <button
        className="menu-toggle"
        onClick={toggleMenu}
        aria-label="Toggle menu"
        aria-expanded={isMenuOpen}
      >
        <span></span>
        <span></span>
        <span></span>
      </button>
    </header>
  );
};

export default Navbar;