/**
 * Website Builder
 * Public API exports
 */

// Components
export { default as WebsiteRenderer } from './components/WebsiteRenderer';
export { default as AgentWidget } from './components/AgentWidget';
export { default as QuickContactButtons } from './components/QuickContactButtons';
export { default as DeviceSwitcher } from './components/DeviceSwitcher';
export { WebsiteAgentProvider, useWebsiteAgent } from './context/WebsiteAgentContext';
export * from './components/blocks';

// Templates
export * from './templates';

// Hooks
export * from './hooks';

// Pages
export * from './pages';

// Styles (side-effect import)
import './styles';
