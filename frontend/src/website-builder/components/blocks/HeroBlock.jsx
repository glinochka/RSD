/**
 * Hero Block Component
 * Large header section with headline, subheadline, and CTA button
 */
import React from 'react';
import PropTypes from 'prop-types';
import { EditableText } from '../editor';

const HeroBlock = ({
  content,
  styles = {},
  blockStyles = {},
  editMode = false,
  onContentChange,
  placeholderVars = {},
}) => {
  const {
    headline = 'Добро пожаловать',
    subheadline = '',
    ctaText = 'Узнать больше',
    ctaLink = '#contacts',
    backgroundImageUrl = '',
    navLinks = [],
  } = content || {};

  const {
    primaryColor = '#2563EB',
    secondaryColor = '#1E40AF',
    backgroundColor = '#FFFFFF',
    textColor = '#1F2937',
    darkMode = false,
  } = styles;

  const bgStyle = backgroundImageUrl
    ? { backgroundImage: `url(${backgroundImageUrl})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : { backgroundColor };

  const overlayStyle = backgroundImageUrl
    ? { backgroundColor: darkMode ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,255,0.8)' }
    : {};

  return (
    <section
      id="top"
      className="relative min-h-[60vh] md:min-h-[70vh] lg:min-h-[80vh] flex items-center justify-center py-12 md:py-16 lg:py-20"
      style={bgStyle}
    >
      {Array.isArray(navLinks) && navLinks.length > 0 && (
        <nav className="absolute top-0 left-0 right-0 z-20">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
            <div
              className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 rounded-xl px-3 py-2"
              style={{
                backgroundColor: darkMode ? 'rgba(15,23,42,0.68)' : 'rgba(255,255,255,0.82)',
                backdropFilter: 'blur(8px)',
                border: `1px solid ${darkMode ? 'rgba(148,163,184,0.25)' : 'rgba(203,213,225,0.95)'}`,
              }}
            >
              {navLinks.map((item, idx) => (
                <a
                  key={`${item.anchor}-${idx}`}
                  href={item.anchor}
                  className="px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors"
                  style={{
                    color: darkMode ? '#E2E8F0' : '#0F172A',
                  }}
                >
                  {item.label}
                </a>
              ))}
            </div>
          </div>
        </nav>
      )}

      {/* Overlay for background images */}
      {backgroundImageUrl && (
        <div className="absolute inset-0" style={overlayStyle} />
      )}

      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {editMode ? (
          <EditableText
            tag="h1"
            value={headline}
            onChange={(v) => onContentChange?.({ headline: v })}
            placeholderVars={placeholderVars}
            className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold mb-4 md:mb-6 leading-tight"
            style={{ color: backgroundImageUrl ? (darkMode ? '#FFFFFF' : textColor) : textColor }}
          />
        ) : (
          <h1
            className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold mb-4 md:mb-6 leading-tight"
            style={{ color: backgroundImageUrl ? (darkMode ? '#FFFFFF' : textColor) : textColor }}
          >
            {headline}
          </h1>
        )}

        {(subheadline || editMode) && (
          editMode ? (
            <EditableText
              tag="p"
              value={subheadline}
              onChange={(v) => onContentChange?.({ subheadline: v })}
              placeholderVars={placeholderVars}
              multiline
              className="text-lg sm:text-xl md:text-2xl mb-6 md:mb-8 max-w-2xl mx-auto leading-relaxed"
              style={{ color: backgroundImageUrl ? (darkMode ? '#E5E7EB' : textColor) : textColor }}
            />
          ) : (
            <p
              className="text-lg sm:text-xl md:text-2xl mb-6 md:mb-8 max-w-2xl mx-auto leading-relaxed"
              style={{ color: backgroundImageUrl ? (darkMode ? '#E5E7EB' : textColor) : textColor }}
            >
              {subheadline}
            </p>
          )
        )}

        {(ctaText || editMode) && (
          editMode ? (
            <span
              className="inline-block px-6 py-3 md:px-8 md:py-4 rounded-lg text-white font-semibold text-base md:text-lg"
              style={{ backgroundColor: primaryColor }}
            >
              <EditableText
                value={ctaText}
                onChange={(v) => onContentChange?.({ ctaText: v })}
                placeholderVars={placeholderVars}
              />
            </span>
          ) : (
          <a
            href={ctaLink}
            className="inline-block px-6 py-3 md:px-8 md:py-4 rounded-lg text-white font-semibold text-base md:text-lg transition-all duration-200 hover:opacity-90 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-2"
            style={{
              backgroundColor: primaryColor,
              boxShadow: `0 4px 14px 0 ${primaryColor}40`,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = secondaryColor;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = primaryColor;
            }}
          >
            {ctaText}
          </a>
          )
        )}
      </div>

      {/* Decorative gradient */}
      {!backgroundImageUrl && (
        <div
          className="absolute bottom-0 left-0 right-0 h-32 pointer-events-none"
          style={{
            background: `linear-gradient(to top, ${darkMode ? '#111827' : '#FFFFFF'}, transparent)`,
          }}
        />
      )}
    </section>
  );
};

HeroBlock.propTypes = {
  content: PropTypes.shape({
    headline: PropTypes.string,
    subheadline: PropTypes.string,
    ctaText: PropTypes.string,
    ctaLink: PropTypes.string,
    backgroundImageUrl: PropTypes.string,
    navLinks: PropTypes.arrayOf(
      PropTypes.shape({
        label: PropTypes.string,
        anchor: PropTypes.string,
      })
    ),
  }),
  styles: PropTypes.shape({
    primaryColor: PropTypes.string,
    secondaryColor: PropTypes.string,
    backgroundColor: PropTypes.string,
    textColor: PropTypes.string,
    darkMode: PropTypes.bool,
  }),
  blockStyles: PropTypes.object,
  editMode: PropTypes.bool,
  onContentChange: PropTypes.func,
  placeholderVars: PropTypes.object,
};

export default HeroBlock;
