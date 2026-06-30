/**
 * Solutions List Page (/projects)
 *
 * This is the primary hub for all user solutions: agents, websites, and projects.
 * It wraps AgentsPageContent (the full agent management component from agentsPage.jsx),
 * which has been extended to also show websites and projects in the left panel.
 *
 * The /agents route is archived — all management happens here.
 */

import MainLayout from '../../components/Layout';
import { AgentsPageContent } from '../agentsPage';

const ProjectsListPage = () => (
  <MainLayout>
    <AgentsPageContent />
  </MainLayout>
);

export default ProjectsListPage;
