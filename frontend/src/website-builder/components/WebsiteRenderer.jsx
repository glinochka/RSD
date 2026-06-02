/**
 * Website Renderer Component
 * Renders a complete website from schema with all blocks
 */
import React from 'react';
import PropTypes from 'prop-types';
import { Helmet } from 'react-helmet-async';
import { blockStylesToCss } from '../utils/styleUtils';
import { scopeCSS, generateScopedClass } from '../utils/security';

// Import all block components
import {
  HeroBlock,
  ServicesBlock,
  AboutBlock,
  ContactsBlock,
  CTABlock,
  FooterBlock,
  AgentWidgetBlock,
  BookingBlock,
} from './blocks';

// Map block types to components
const BLOCK_COMPONENT_MAP = {
  hero: HeroBlock,
  services: ServicesBlock,
  about: AboutBlock,
  contacts: ContactsBlock,
  cta: CTABlock,
  footer: FooterBlock,
  'agent-widget': AgentWidgetBlock,
  booking: BookingBlock,
  custom: HeroBlock, // Fallback
};

/**
 * Merge template styles with custom styles
 */
const mergeStyles = (templateStyles, customStyles) => {
  return {
    primaryColor: '#2563EB',
    secondaryColor: '#1E40AF',
    accentColor: '#3B82F6',
    backgroundColor: '#FFFFFF',
    textColor: '#1F2937',
    fontFamily: 'Inter, system-ui, sans-serif',
    darkMode: false,
    ...templateStyles,
    ...customStyles,
  };
};

/**
 * Website Renderer Component
 */
const WebsiteRenderer = ({
  schema,
  templateStyles = {},
  className = '',
  previewMode = false,
  editMode = false,
  selectedBlockId = null,
  onSelectBlock = null,
  onContentChange = null,
  placeholderVars = {},
}) => {
  const {
    id,
    slug,
    title,
    meta_description,
    og_title,
    og_description,
    og_image_url,
    favicon_url,
    status,
    styles = {},
    blocks = [],
  } = schema || {};

  // Merge all styles
  const mergedStyles = mergeStyles(templateStyles, styles);

  // Generate scope class for CSS isolation
  const scopeClass = id ? `site-${id}` : 'site-preview';
  
  // Scope CSS for isolation between websites
  const scopedGlobalCSS = id ? scopeCSS(`
    .website-renderer {
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    
    .website-renderer a {
      color: ${mergedStyles.accentColor};
      text-decoration: none;
      transition: color 0.2s ease;
    }
    
    .website-renderer a:hover {
      color: ${mergedStyles.primaryColor};
    }
    
    .website-renderer img {
      max-width: 100%;
      height: auto;
    }
    
    /* Smooth scroll */
    html {
      scroll-behavior: smooth;
    }
    
    /* Selection color */
    ::selection {
      background-color: ${mergedStyles.primaryColor}30;
      color: ${mergedStyles.textColor};
    }
  `, scopeClass) : '';

  // Utility to generate scoped class names for components
  const getScopedClass = (baseClass) => {
    if (!id) return baseClass;
    return generateScopedClass(id, baseClass);
  };

  // Sort blocks by order
  const sortedBlocks = [...blocks].sort((a, b) => (a.order || 0) - (b.order || 0));

  // Render a single block
  const renderBlock = (block, index) => {
    const BlockComponent = BLOCK_COMPONENT_MAP[block.type];

    if (!BlockComponent) {
      console.warn(`Unknown block type: ${block.type}`);
      return null;
    }

    const isSelected = editMode && selectedBlockId === block.id;
    const wrapperStyle = blockStylesToCss(block.styles || {});

    const blockWrapperId = block.type === 'booking' ? 'wb-booking-section' : undefined;

    const inner = (
      <div id={blockWrapperId}>
        <BlockComponent
          content={block.content}
          styles={mergedStyles}
          blockStyles={block.styles || {}}
          {...editProps}
          onContentChange={(patch) => onContentChange?.(block.id, patch)}
          placeholderVars={placeholderVars}
          editMode={editMode}
        />
      </div>
    );

    if (!editMode) {
      return (
        <div key={block.id ?? `${block.type}-${index}`} style={wrapperStyle}>
          {inner}
        </div>
      );
    }

    return (
      <div
        key={block.id ?? `${block.type}-${index}`}
        className={`wb-block-wrapper ${isSelected ? 'wb-block-wrapper--selected' : ''}`}
        style={wrapperStyle}
        onClick={(e) => {
          e.stopPropagation();
          onSelectBlock?.(block.id);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && onSelectBlock?.(block.id)}
      >
        {inner}
      </div>
    );
  };

  return (
    <>
      {/* SEO Meta Tags */}
      <Helmet>
        <title>{title || 'Мой сайт'}</title>
        <meta name="description" content={meta_description || ''} />

        {/* Open Graph */}
        <meta property="og:title" content={og_title || title || 'Мой сайт'} />
        <meta property="og:description" content={og_description || meta_description || ''} />
        {og_image_url && <meta property="og:image" content={og_image_url} />}
        <meta property="og:type" content="website" />
        <meta property="og:url" content={typeof window !== 'undefined' ? window.location.href : ''} />

        {/* Favicon */}
        {favicon_url && <link rel="icon" href={favicon_url} />}

        {/* Theme Color */}
        <meta name="theme-color" content={mergedStyles.primaryColor} />
      </Helmet>

      {/* Google Fonts */}
      {mergedStyles.fontFamily?.includes('Inter') && (
        <Helmet>
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <link
            href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
            rel="stylesheet"
          />
        </Helmet>
      )}

      {/* CSS Isolation Wrapper */}
      <div className={scopeClass} style={{ all: 'initial', display: 'contents' }}>
        {/* Website Container */}
        <div
          className={`website-renderer ${className} ${previewMode ? 'preview-mode' : ''}`}
          data-website-id={id}
          data-website-slug={slug}
          data-website-status={status}
          style={{
            fontFamily: mergedStyles.fontFamily,
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Main Content */}
          <main className="flex-grow">
            {sortedBlocks.map((block, index) => renderBlock(block, index))}
          </main>
        </div>

        {/* Scoped Global Styles for template */}
        {id && <style>{scopedGlobalCSS}</style>}
      </div>
    </>
  );
};

WebsiteRenderer.propTypes = {
  schema: PropTypes.shape({
    id: PropTypes.number,
    slug: PropTypes.string,
    title: PropTypes.string,
    meta_description: PropTypes.string,
    og_title: PropTypes.string,
    og_description: PropTypes.string,
    og_image_url: PropTypes.string,
    favicon_url: PropTypes.string,
    status: PropTypes.string,
    styles: PropTypes.object,
    blocks: PropTypes.arrayOf(
      PropTypes.shape({
        type: PropTypes.string.isRequired,
        order: PropTypes.number,
        content: PropTypes.object,
        styles: PropTypes.object,
      })
    ),
  }).isRequired,
  templateStyles: PropTypes.object,
  className: PropTypes.string,
  previewMode: PropTypes.bool,
  editMode: PropTypes.bool,
  selectedBlockId: PropTypes.number,
  onSelectBlock: PropTypes.func,
  onContentChange: PropTypes.func,
  placeholderVars: PropTypes.object,
};

export default WebsiteRenderer;
