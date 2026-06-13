/**
 * Main App Component
 * Root component with routing and context providers
 */

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { AuthProvider } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import ErrorBoundary from './components/ErrorBoundary';
import NotificationContainer from './components/NotificationContainer';
import { NAVIGATION_ROUTES } from './config/constants';
import DocumentHead from './components/DocumentHead';
import ReferralCapture from './components/ReferralCapture';

// Pages
import Main from './pages/Main';
import Auth from './pages/Auth';
import PriceList from './pages/PriceList';
import AgentsPage from './pages/agentsPage';
import AgentDetailedAnalyticsPage from './pages/AgentDetailedAnalyticsPage';
import CreateAgent from './pages/createAgent';
import ManagementPortal from './pages/ManagementPortal';
import DocumentationPage from './pages/DocumentationPage';
import PublicOfferPage from './pages/PublicOfferPage';
import UserAgreementPage from './pages/UserAgreementPage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import PartnerPage from './pages/PartnerPage';

// Website Builder Pages
import { PreviewPage, WebsitePublicPage, ConstructorPage } from './website-builder/pages';
const App = () => {
  return (
    <ErrorBoundary>
      <HelmetProvider>
        <Router>
          <DocumentHead />
          <ReferralCapture />
          <AuthProvider>
            <NotificationProvider>
              <NotificationContainer />
              <Routes>
                {/* Public routes */}
                <Route path={NAVIGATION_ROUTES.HOME} element={<Main />} />
                <Route path={NAVIGATION_ROUTES.AUTH} element={<Auth />} />
                <Route path={NAVIGATION_ROUTES.PRICING} element={<PriceList />} />
                <Route path={NAVIGATION_ROUTES.PARTNER} element={<PartnerPage />} />
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

                {/* Website Builder Routes */}
                <Route path="/preview/:websiteId" element={<PreviewPage />} />
                <Route path="/websites/:websiteId/edit" element={<ConstructorPage />} />
                <Route path="/w/:slug" element={<WebsitePublicPage />} />

                {/* Catch-all - redirect to home */}
                <Route path="*" element={<Navigate to={NAVIGATION_ROUTES.HOME} replace />} />
              </Routes>
            </NotificationProvider>
          </AuthProvider>
        </Router>
      </HelmetProvider>
    </ErrorBoundary>
  );
};

export default App;