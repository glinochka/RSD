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
      className="relative min-h-[60vh] md:min-h-[70vh] lg:min-h-[80vh] flex items-center justify-center py-12 md:py-16 lg:py-20"
      style={bgStyle}
    >
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
