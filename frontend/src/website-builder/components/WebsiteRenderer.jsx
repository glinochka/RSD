/**
 * Website Renderer Component
 * Renders a complete website from schema with all blocks.
 * Supports two modes:
 * - "fullpage": AI-generated HTML rendered in a sandboxed iframe
 * - Legacy block-based rendering via React components
 */
import React from 'react';
import PropTypes from 'prop-types';
import { Helmet } from 'react-helmet-async';
import { blockStylesToCss } from '../utils/styleUtils';
import { scopeCSS, generateScopedClass } from '../utils/security';
import FullpageRenderer from './FullpageRenderer';

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

const defaultContentByType = (type, siteTitle = 'Ваш бизнес') => {
  switch (type) {
    case 'hero':
      return {
        headline: siteTitle || '',
        subheadline: '',
        ctaText: '',
        ctaLink: '',
      };
    case 'services':
      return {
        title: '',
        items: [],
      };
    case 'about':
      return {
        title: '',
        text: '',
      };
    case 'contacts':
      return {
        title: '',
        contactInfo: {
          phone: '',
          email: '',
          address: '',
          workingHours: '',
        },
        showForm: true,
        formTitle: '',
      };
    case 'cta':
      return {
        title: '',
        subtitle: '',
        buttonText: '',
        buttonLink: '',
      };
    case 'footer':
      return {
        companyName: siteTitle || '',
        copyrightText: `© ${new Date().getFullYear()} Все права защищены`,
      };
    default:
      return {};
  }
};

const normalizeBlockContent = (type, rawContent = {}, siteTitle = 'Ваш бизнес') => {
  const content = rawContent || {};
  const base = defaultContentByType(type, siteTitle);

  if (type === 'hero') {
    const normalizedNav = Array.isArray(content.navLinks || content.nav_links)
      ? (content.navLinks || content.nav_links)
          .map((item) => ({
            label: item?.label || '',
            anchor: item?.anchor || '',
          }))
          .filter((item) => item.label && item.anchor)
      : [];

    return {
      ...base,
      ...content,
      headline: content.headline || content.title || base.headline,
      subheadline: content.subheadline || content.description || content.text || base.subheadline,
      ctaText: content.ctaText || content.cta_text || content.buttonText || content.button_text || base.ctaText,
      ctaLink: content.ctaLink || content.cta_link || content.buttonLink || content.button_link || base.ctaLink,
      backgroundImageUrl: content.backgroundImageUrl || content.background_image_url || content.imageUrl || content.image_url || '',
      navLinks: normalizedNav,
    };
  }

  if (type === 'services') {
    const items = Array.isArray(content.items) ? content.items : [];
    const normalizedItems = items
      .map((item, index) => ({
        id: item.id || `service-${index}`,
        name: item.name || item.title || `Услуга ${index + 1}`,
        description: item.description || '',
        price: item.price || '',
        icon: item.icon || 'check',
        imageUrl: item.imageUrl || item.image_url || '',
      }))
      .filter((item) => item.name);

    return {
      ...base,
      ...content,
      title: content.title || base.title,
      items: normalizedItems.length ? normalizedItems : base.items,
    };
  }

  if (type === 'about') {
    return {
      ...base,
      ...content,
      title: content.title || base.title,
      text: content.text || content.description || base.text,
      imageUrl: content.imageUrl || content.image_url || '',
      imagePosition: content.imagePosition || content.image_position || 'right',
    };
  }

  if (type === 'contacts') {
    const info = content.contactInfo || content.contact_info || {};
    return {
      ...base,
      ...content,
      title: content.title || base.title,
      showForm: content.showForm ?? content.show_form ?? base.showForm,
      formTitle: content.formTitle || content.form_title || base.formTitle,
      contactInfo: {
        ...base.contactInfo,
        ...info,
        workingHours: info.workingHours || info.working_hours || base.contactInfo.workingHours,
      },
    };
  }

  if (type === 'cta') {
    return {
      ...base,
      ...content,
      title: content.title || base.title,
      subtitle: content.subtitle || base.subtitle,
      buttonText: content.buttonText || content.button_text || base.buttonText,
      buttonLink: content.buttonLink || content.button_link || base.buttonLink,
    };
  }

  if (type === 'footer') {
    return {
      ...base,
      ...content,
      companyName: content.companyName || content.company_name || base.companyName,
      copyrightText: content.copyrightText || content.copyright_text || base.copyrightText,
      socialLinks: content.socialLinks || content.social_links || {},
      privacyPolicyUrl: content.privacyPolicyUrl || content.privacy_policy_url || '',
      termsUrl: content.termsUrl || content.terms_url || '',
    };
  }

  return { ...base, ...content };
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
    generation_status,
    styles = {},
    blocks = [],
  } = schema || {};

  // Detect fullpage rendering mode (AI-generated HTML sites)
  const isFullpage = styles?.rendering_mode === 'fullpage' ||
    blocks?.some((b) => b.type === 'fullpage');

  if (isFullpage) {
    const fullpageBlock = blocks?.find((b) => b.type === 'fullpage');
    const htmlContent = fullpageBlock?.content?.html || '';

    return (
      <>
        <Helmet>
          <title>{title || 'Мой сайт'}</title>
          <meta name="description" content={meta_description || ''} />
          <meta property="og:title" content={og_title || title || ''} />
          <meta property="og:description" content={og_description || meta_description || ''} />
          {og_image_url && <meta property="og:image" content={og_image_url} />}
          {favicon_url && <link rel="icon" href={favicon_url} />}
        </Helmet>
        <FullpageRenderer
          htmlContent={htmlContent}
          websiteId={id}
          title={title}
          editMode={editMode}
          previewMode={previewMode}
          className={className}
        />
      </>
    );
  }

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
  // Intentionally no auto-fallback blocks: if backend has no blocks yet, render nothing.
  // This prevents accidental display of generic template-like demo content.
  const blocksForRender = sortedBlocks;

  if (!blocksForRender.length) {
    const isGenerating = generation_status === 'queued' || generation_status === 'generating';
    const isFailed = generation_status === 'failed';
    const generationError = styles?._generation_error;
    return (
      <div className={`website-renderer ${className}`} data-website-id={id}>
        <main className="min-h-[50vh] flex items-center justify-center px-6">
          <div className={`text-center max-w-xl ${isFailed ? 'text-red-600' : 'text-gray-500'}`}>
            <h2 className={`text-xl font-semibold mb-2 ${isFailed ? 'text-red-700' : 'text-gray-700'}`}>
              {isGenerating ? 'Сайт генерируется' : isFailed ? 'Ошибка генерации сайта' : 'Сайт пока пустой'}
            </h2>
            <p className="text-sm">
              {isGenerating
                ? 'ИИ формирует индивидуальный контент по данным вашего бизнеса.'
                : isFailed
                  ? (generationError || 'Генерация не завершилась. Попробуйте снова с более подробным описанием бизнеса и брифом.')
                  : 'Добавьте контент или запустите генерацию сайта.'}
            </p>
          </div>
        </main>
      </div>
    );
  }

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
          content={normalizeBlockContent(block.type, block.content, title || 'Ваш бизнес')}
          styles={mergedStyles}
          blockStyles={block.styles || {}}
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
        data-block-id={block.id}
        data-block-type={block.type}
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

      {/* CSS isolation wrapper via selector scoping */}
      <div className={scopeClass} style={{ display: 'contents' }}>
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
            {blocksForRender.map((block, index) => renderBlock(block, index))}
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
