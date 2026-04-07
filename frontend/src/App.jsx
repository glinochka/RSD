/**
 * Main App Component
 * Root component with routing and context providers
 */

import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { AuthProvider } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import ErrorBoundary from './components/ErrorBoundary';
import NotificationContainer from './components/NotificationContainer';
import Loading from './components/Loading';
import { NAVIGATION_ROUTES } from './config/constants';
import DocumentHead from './components/DocumentHead';

// Pages
import Main from './pages/Main';
import Auth from './pages/Auth';
import PriceList from './pages/PriceList';

// Lazy loaded pages
const AgentsPage = lazy(() => import('./pages/agentsPage'));
const AgentDetailedAnalyticsPage = lazy(() => import('./pages/AgentDetailedAnalyticsPage'));
const CreateAgent = lazy(() => import('./pages/createAgent'));
const ManagementPortal = lazy(() => import('./pages/ManagementPortal'));
const DocumentationPage = lazy(() => import('./pages/DocumentationPage'));
const PublicOfferPage = lazy(() => import('./pages/PublicOfferPage'));
const UserAgreementPage = lazy(() => import('./pages/UserAgreementPage'));
const PrivacyPolicyPage = lazy(() => import('./pages/PrivacyPolicyPage'));

const App = () => {
  return (
    <ErrorBoundary>
      <HelmetProvider>
        <Router>
          <DocumentHead />
          <AuthProvider>
            <NotificationProvider>
              <NotificationContainer />
              <Suspense fallback={<Loading />}>
                <Routes>
                  {/* Public routes */}
                  <Route path={NAVIGATION_ROUTES.HOME} element={<Main />} />
                  <Route path={NAVIGATION_ROUTES.AUTH} element={<Auth />} />
                  <Route path={NAVIGATION_ROUTES.PRICING} element={<PriceList />} />
                  <Route path={NAVIGATION_ROUTES.DOCUMENTATION} element={<DocumentationPage />} />
                  <Route path={NAVIGATION_ROUTES.PUBLIC_OFFER} element={<PublicOfferPage />} />
                  <Route path={NAVIGATION_ROUTES.USER_AGREEMENT} element={<UserAgreementPage />} />
                  <Route path={NAVIGATION_ROUTES.PRIVACY_POLICY} element={<PrivacyPolicyPage />} />
                  <Route
                    path={NAVIGATION_ROUTES.MANAGEMENT_PORTAL}
                    element={<ManagementPortal />}
                  />

                  {/* Protected routes */}
                  <Route path={NAVIGATION_ROUTES.AGENTS} element={<AgentsPage />} />
                  <Route
                    path={NAVIGATION_ROUTES.AGENT_ANALYTICS(':id')}
                    element={<AgentDetailedAnalyticsPage />}
                  />
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
      </HelmetProvider>
    </ErrorBoundary>
  );
};

export default App;