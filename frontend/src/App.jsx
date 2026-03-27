/**
 * Main App Component
 * Root component with routing and context providers
 */

import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import ErrorBoundary from './components/ErrorBoundary';
import NotificationContainer from './components/NotificationContainer';
import Loading from './components/Loading';
import { NAVIGATION_ROUTES } from './config/constants';

// Pages
import Main from './pages/Main';
import Auth from './pages/Auth';
import PriceList from './pages/PriceList';

// Lazy loaded pages
const AgentsPage = lazy(() => import('./pages/agentsPage'));
const CreateAgent = lazy(() => import('./pages/createAgent'));
const ManagementPortal = lazy(() => import('./pages/ManagementPortal'));

const App = () => {
  return (
    <ErrorBoundary>
      <Router>
        <AuthProvider>
          <NotificationProvider>
            <NotificationContainer />
            <Suspense fallback={<Loading />}>
              <Routes>
                {/* Public routes */}
                <Route path={NAVIGATION_ROUTES.HOME} element={<Main />} />
                <Route path={NAVIGATION_ROUTES.AUTH} element={<Auth />} />
                <Route path={NAVIGATION_ROUTES.PRICING} element={<PriceList />} />
                <Route
                  path={NAVIGATION_ROUTES.MANAGEMENT_PORTAL}
                  element={<ManagementPortal />}
                />

                {/* Protected routes */}
                <Route path={NAVIGATION_ROUTES.AGENTS} element={<AgentsPage />} />
                <Route path={NAVIGATION_ROUTES.CREATE_AGENT} element={<CreateAgent />} />
                <Route
                  path={`${NAVIGATION_ROUTES.CREATE_AGENT}/:id`}
                  element={<CreateAgent />}
                />

                {/* Catch-all - redirect to home */}
                <Route path="*" element={<Navigate to={NAVIGATION_ROUTES.HOME} replace />} />
              </Routes>
            </Suspense>
          </NotificationProvider>
        </AuthProvider>
      </Router>
    </ErrorBoundary>
  );
};

export default App;