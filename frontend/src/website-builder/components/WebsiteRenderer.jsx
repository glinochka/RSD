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

const REQUIRED_BLOCK_TYPES = ['hero', 'services', 'about', 'contacts', 'cta', 'footer'];

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
        headline: siteTitle,
        subheadline: 'Помогаем клиентам получить результат быстро и комфортно',
        ctaText: 'Получить консультацию',
        ctaLink: '#contacts',
      };
    case 'services':
      return {
        title: 'Наши услуги',
        items: [
          {
            name: 'Базовая услуга',
            description: 'Закрываем ключевую задачу и даем понятный план действий.',
            price: 'от 3 000 ₽',
            icon: 'star',
          },
          {
            name: 'Расширенное сопровождение',
            description: 'Подключаем эксперта и ведем вас до финального результата.',
            price: 'от 7 500 ₽',
            icon: 'check',
          },
          {
            name: 'Индивидуальное решение',
            description: 'Собираем формат под ваш бизнес, сроки и бюджет.',
            price: 'По запросу',
            icon: 'users',
          },
        ],
      };
    case 'about':
      return {
        title: 'О компании',
        text: `${siteTitle} работает на результат: прозрачные условия, понятные этапы и внимание к деталям на каждом шаге.`,
      };
    case 'contacts':
      return {
        title: 'Контакты',
        contactInfo: {
          phone: '+7 (999) 999-99-99',
          email: 'hello@example.com',
          address: 'Россия',
          workingHours: 'Пн-Пт: 09:00-18:00',
        },
        showForm: true,
        formTitle: 'Оставьте заявку',
      };
    case 'cta':
      return {
        title: 'Готовы обсудить ваш проект?',
        subtitle: 'Оставьте заявку, и мы свяжемся с вами в ближайшее время',
        buttonText: 'Оставить заявку',
        buttonLink: '#contacts',
      };
    case 'footer':
      return {
        companyName: siteTitle,
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
  const blocksForRender = sortedBlocks.length
    ? sortedBlocks
    : REQUIRED_BLOCK_TYPES.map((type, index) => ({
        id: `fallback-${type}-${index}`,
        type,
        order: index + 1,
        content: defaultContentByType(type, title || 'Ваш бизнес'),
        styles: {},
      }));

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
