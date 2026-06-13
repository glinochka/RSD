/**
 * Website Builder Templates
 * Base templates configuration
 */

import { MODERN_BUSINESS_TEMPLATE } from './modern-business';
import { MINIMAL_PORTFOLIO_TEMPLATE } from './minimal-portfolio';
import { VIBRANT_SERVICE_TEMPLATE } from './vibrant-service';
import { ELEGANT_PROFESSIONAL_TEMPLATE } from './elegant-professional';

// Export all templates
export const TEMPLATES = {
  [MODERN_BUSINESS_TEMPLATE.id]: MODERN_BUSINESS_TEMPLATE,
  [MINIMAL_PORTFOLIO_TEMPLATE.id]: MINIMAL_PORTFOLIO_TEMPLATE,
  [VIBRANT_SERVICE_TEMPLATE.id]: VIBRANT_SERVICE_TEMPLATE,
  [ELEGANT_PROFESSIONAL_TEMPLATE.id]: ELEGANT_PROFESSIONAL_TEMPLATE,
};

// Export array for listing
export const TEMPLATES_LIST = [
  MODERN_BUSINESS_TEMPLATE,
  MINIMAL_PORTFOLIO_TEMPLATE,
  VIBRANT_SERVICE_TEMPLATE,
  ELEGANT_PROFESSIONAL_TEMPLATE,
];

// Export individual templates
export {
  MODERN_BUSINESS_TEMPLATE,
  MINIMAL_PORTFOLIO_TEMPLATE,
  VIBRANT_SERVICE_TEMPLATE,
  ELEGANT_PROFESSIONAL_TEMPLATE,
};

// Helper function to get template by ID
export function getTemplateById(id) {
  return TEMPLATES[id] || TEMPLATES['modern-business'];
}

// Helper function to merge template styles with custom styles
export function mergeStyles(templateStyles, customStyles) {
  return {
    ...templateStyles,
    ...customStyles,
  };
}

// Helper function to get default blocks for a template
export function getDefaultBlocks(templateId) {
  const template = getTemplateById(templateId);
  return template?.defaultBlocks?.blocks || [];
}
