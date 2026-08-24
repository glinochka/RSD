import React from 'react';
import { Link, Outlet, Navigate } from 'react-router-dom';
import { useCustomAuth } from './useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';
import customService from '../../services/customService';

const CustomClientLayout = () => {
  const { isAuthenticated, automationId, isAdmin, logout } = useCustomAuth();
  const [features, setFeatures] = React.useState({});

  React.useEffect(() => {
    let mounted = true;
    customService.getAutomationSettings(automationId).then((data) => {
      if (mounted) {
        setFeatures(data || {});
      }
    }).catch(() => {});
    return () => {
      mounted = false;
    };
  }, [automationId]);

  if (!isAuthenticated || isAdmin || !automationId) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="font-semibold text-lg">Automation #{automationId}</div>
        <nav className="flex items-center gap-4">
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DASHBOARD(automationId)}
            className="text-sm hover:underline"
          >
            Dashboard
          </Link>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_ACCOUNTS(automationId)}
            className="text-sm hover:underline"
          >
            Accounts
          </Link>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_SETTINGS(automationId)}
            className="text-sm hover:underline"
          >
            Settings
          </Link>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHATS(automationId)}
            className="text-sm hover:underline"
          >
            Chats
          </Link>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CHAT_DISCOVERY(automationId)}
            className="text-sm hover:underline"
          >
            Discovery
          </Link>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_LEADS(automationId)}
            className="text-sm hover:underline"
          >
            Leads
          </Link>
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_DMP(automationId)}
            className="text-sm hover:underline"
          >
            DMP.one
          </Link>
          {features?.is_amocrm_enabled && (
            <Link
              to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_AMOCRM(automationId)}
              className="text-sm hover:underline"
            >
              AmoCRM
            </Link>
          )}
          <Link
            to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPTS(automationId)}
            className="text-sm hover:underline"
          >
            Prompts
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

export default CustomClientLayout;
