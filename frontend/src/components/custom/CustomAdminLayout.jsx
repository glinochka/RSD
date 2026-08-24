import React from 'react';
import { Outlet, Link, Navigate } from 'react-router-dom';
import { useCustomAuth } from './useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';

const CustomAdminLayout = () => {
  const { isAuthenticated, isAdmin, logout } = useCustomAuth();

  if (!isAuthenticated || !isAdmin) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="font-semibold text-lg">/custom Admin</div>
        <nav className="flex items-center gap-4">
          <Link to={NAVIGATION_ROUTES.CUSTOM_ADMIN_DASHBOARD} className="text-sm hover:underline">
            Dashboard
          </Link>
          <Link to={NAVIGATION_ROUTES.CUSTOM_ADMIN_AUTOMATIONS} className="text-sm hover:underline">
            Automations
          </Link>
          <button onClick={logout} className="text-sm text-red-600 hover:underline">
            Logout
          </button>
        </nav>
      </header>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
};

export default CustomAdminLayout;
