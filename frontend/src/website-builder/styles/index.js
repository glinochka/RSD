/**
 * Website Builder Styles
 */

// Import global styles
import './website-builder.css';
import './constructor.css';
import './quick-contacts.css';
import './booking-block.css';

// Template-specific styles are applied via inline styles
export const STYLE_HELPERS = {
  // Convert hex to rgba
  hexToRgba: (hex, alpha = 1) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  },

  // Generate gradient from primary color
  generateGradient: (primaryColor, secondaryColor, angle = 135) => {
    return `linear-gradient(${angle}deg, ${primaryColor} 0%, ${secondaryColor} 100%)`;
  },

  // Lighten/darken color
  adjustColor: (hex, amount) => {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = Math.min(255, Math.max(0, (num >> 16) + amount));
    const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
    const b = Math.min(255, Math.max(0, (num & 0x00FF) + amount));
    return `#${(0x1000000 + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
  },

  // Get contrast color (black or white) for text on background
  getContrastColor: (hex) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? '#000000' : '#FFFFFF';
  },
};

export default STYLE_HELPERS;
