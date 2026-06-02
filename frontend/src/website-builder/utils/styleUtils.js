/**
 * Normalize website styles between API (snake_case) and renderer (camelCase).
 */

const SNAKE_TO_CAMEL = {
  primary_color: 'primaryColor',
  secondary_color: 'secondaryColor',
  background_color: 'backgroundColor',
  text_color: 'textColor',
  font_family: 'fontFamily',
  dark_mode: 'darkMode',
  accent_color: 'accentColor',
  border_radius: 'borderRadius',
};

const CAMEL_TO_SNAKE = Object.fromEntries(
  Object.entries(SNAKE_TO_CAMEL).map(([k, v]) => [v, k])
);

export function toRendererStyles(styles = {}) {
  if (!styles || typeof styles !== 'object') return {};
  const out = { ...styles };
  Object.entries(SNAKE_TO_CAMEL).forEach(([snake, camel]) => {
    if (out[snake] !== undefined && out[camel] === undefined) {
      out[camel] = out[snake];
    }
    delete out[snake];
  });
  return out;
}

export function toApiStyles(styles = {}) {
  if (!styles || typeof styles !== 'object') return {};
  const out = { ...styles };
  Object.entries(CAMEL_TO_SNAKE).forEach(([camel, snake]) => {
    if (out[camel] !== undefined) {
      out[snake] = out[camel];
      delete out[camel];
    }
  });
  return out;
}

const BORDER_RADIUS_MAP = {
  none: '0',
  medium: '0.5rem',
  round: '1rem',
};

export function borderRadiusPresetToCss(preset) {
  if (!preset) return undefined;
  return BORDER_RADIUS_MAP[preset] || preset;
}

export function blockStylesToCss(blockStyles = {}) {
  const css = {};
  if (blockStyles.padding != null) css.padding = `${blockStyles.padding}px`;
  if (blockStyles.margin != null) css.margin = `${blockStyles.margin}px`;
  if (blockStyles.textAlign) css.textAlign = blockStyles.textAlign;
  if (blockStyles.borderRadius) {
    css.borderRadius = borderRadiusPresetToCss(blockStyles.borderRadius);
  }
  return css;
}
