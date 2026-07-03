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
// AgentsPage is archived — the /agents route is no longer registered.
// All agent management is now at /projects (ProjectsListPage → AgentsPageContent).
// import AgentsPage from './pages/agentsPage';
import AgentDetailedAnalyticsPage from './pages/AgentDetailedAnalyticsPage';
import CreateAgent from './pages/createAgent';
import AgentCreateAiPage from './pages/AgentCreateAiPage';
import ManagementPortal from './pages/ManagementPortal';
import DocumentationPage from './pages/DocumentationPage';
import PublicOfferPage from './pages/PublicOfferPage';
import UserAgreementPage from './pages/UserAgreementPage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import PartnerPage from './pages/PartnerPage';
import ProjectsListPage from './pages/projects/ProjectsListPage';
import ProjectLayout from './components/projects/ProjectLayout';
import ProjectDashboardPage from './pages/projects/ProjectDashboardPage';
import ProjectAgentsPage from './pages/projects/ProjectAgentsPage';
import ProjectKnowledgePage from './pages/projects/ProjectKnowledgePage';
import ProjectCRMPage from './pages/projects/ProjectCRMPage';
import ProjectWebsitePage from './pages/projects/ProjectWebsitePage';
import ProjectSettingsPage from './pages/projects/ProjectSettingsPage';
import ProjectCreatePage from './pages/projects/ProjectCreatePage';
import ProjectContentPage from './pages/projects/ProjectContentPage';
import ProjectManagerPage from './pages/projects/ProjectManagerPage';
import ProjectIntegrationsPage from './pages/projects/ProjectIntegrationsPage';

// Website Builder Pages
import { PreviewPage, WebsitePublicPage, ConstructorPage, WebsiteCreatePage } from './website-builder/pages';
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

                {/* /agents is archived — redirect to /projects */}
                <Route path={NAVIGATION_ROUTES.AGENTS} element={<Navigate to={NAVIGATION_ROUTES.PROJECTS_LIST} replace />} />
                <Route path="/agents/:id" element={<Navigate to={NAVIGATION_ROUTES.PROJECTS_LIST} replace />} />
                <Route
                  path={NAVIGATION_ROUTES.AGENT_ANALYTICS(':id')}
                  element={<AgentDetailedAnalyticsPage />}
                />
                <Route path={NAVIGATION_ROUTES.CREATE_AGENT} element={<CreateAgent />} />
                <Route path={NAVIGATION_ROUTES.CREATE_AGENT_AI} element={<AgentCreateAiPage />} />
                <Route
                  path={`${NAVIGATION_ROUTES.CREATE_AGENT}/:id`}
                  element={<CreateAgent />}
                />

                {/* Projects (Portal) Routes - Stage 3 */}
                <Route path={NAVIGATION_ROUTES.PROJECTS_LIST} element={<ProjectsListPage />} />
                {/* Project Detail Routes with ProjectLayout - Stage 4 */}
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_DETAIL(':projectId')}`}
                  element={<ProjectLayout><ProjectDashboardPage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_AGENTS(':projectId')}`}
                  element={<ProjectLayout><ProjectAgentsPage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_KNOWLEDGE(':projectId')}`}
                  element={<ProjectLayout><ProjectKnowledgePage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_CRM(':projectId')}`}
                  element={<ProjectLayout><ProjectCRMPage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_WEBSITE(':projectId')}`}
                  element={<ProjectLayout><ProjectWebsitePage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_SETTINGS(':projectId')}`}
                  element={<ProjectLayout><ProjectSettingsPage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_CONTENT(':projectId')}`}
                  element={<ProjectLayout><ProjectContentPage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_MANAGER(':projectId')}`}
                  element={<ProjectLayout><ProjectManagerPage /></ProjectLayout>}
                />
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_INTEGRATIONS(':projectId')}`}
                  element={<ProjectLayout><ProjectIntegrationsPage /></ProjectLayout>}
                />
                {/* Project Create - Stage 5 */}
                <Route
                  path={`${NAVIGATION_ROUTES.PROJECT_CREATE}`}
                  element={<ProjectCreatePage />}
                />

                {/* Website Builder Routes */}
                <Route path="/preview/:websiteId" element={<PreviewPage />} />
                <Route path="/websites/:websiteId/edit" element={<ConstructorPage />} />
                <Route path="/websites/create" element={<WebsiteCreatePage />} />
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