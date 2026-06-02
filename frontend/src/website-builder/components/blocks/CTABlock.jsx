/**
 * CTA (Call-to-Action) Block Component
 * Prominent action section with title, subtitle, and button
 */
import React from 'react';
import PropTypes from 'prop-types';
import { EditableText } from '../editor';

const CTABlock = ({
  content,
  styles = {},
  blockStyles = {},
  editMode = false,
  onContentChange,
  placeholderVars = {},
}) => {
  const {
    title = 'Готовы начать?',
    subtitle = '',
    buttonText = 'Связаться с нами',
    buttonLink = '#contacts',
  } = content || {};

  const {
    primaryColor = '#2563EB',
    secondaryColor = '#1E40AF',
    backgroundColor = '#1F2937',
    textColor = '#FFFFFF',
    accentColor = '#3B82F6',
  } = styles;

  return (
    <section
      className="py-12 md:py-16 lg:py-20 relative overflow-hidden"
      style={{ backgroundColor }}
    >
      {/* Decorative background pattern */}
      <div className="absolute inset-0 opacity-10">
        <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" style={{ color: accentColor }} />
        </svg>
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {editMode ? (
          <EditableText
            tag="h2"
            value={title}
            onChange={(v) => onContentChange?.({ title: v })}
            placeholderVars={placeholderVars}
            className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold mb-4 md:mb-6"
            style={{ color: textColor }}
          />
        ) : (
          <h2
            className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold mb-4 md:mb-6"
            style={{ color: textColor }}
          >
            {title}
          </h2>
        )}

        {(subtitle || editMode) &&
          (editMode ? (
            <EditableText
              tag="p"
              value={subtitle}
              onChange={(v) => onContentChange?.({ subtitle: v })}
              placeholderVars={placeholderVars}
              multiline
              className="text-lg sm:text-xl md:text-2xl mb-6 md:mb-8 max-w-2xl mx-auto"
              style={{ color: textColor, opacity: 0.9 }}
            />
          ) : (
            <p
              className="text-lg sm:text-xl md:text-2xl mb-6 md:mb-8 max-w-2xl mx-auto"
              style={{ color: textColor, opacity: 0.9 }}
            >
              {subtitle}
            </p>
          ))}

        {editMode ? (
          <span
            className="inline-block px-8 py-3 md:px-10 md:py-4 rounded-lg text-lg md:text-xl font-semibold"
            style={{ backgroundColor: accentColor, color: '#FFFFFF' }}
          >
            <EditableText
              value={buttonText}
              onChange={(v) => onContentChange?.({ buttonText: v })}
              placeholderVars={placeholderVars}
            />
          </span>
        ) : (
        <a
          href={buttonLink}
          className="inline-block px-8 py-3 md:px-10 md:py-4 rounded-lg text-lg md:text-xl font-semibold transition-all duration-200 hover:opacity-90 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-offset-4"
          style={{
            backgroundColor: accentColor,
            color: '#FFFFFF',
            boxShadow: `0 4px 20px 0 ${accentColor}50`,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = primaryColor;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = accentColor;
          }}
        >
          {buttonText}
        </a>
        )}
      </div>

      {/* Decorative circles */}
      <div
        className="absolute -top-20 -left-20 w-64 h-64 rounded-full opacity-20"
        style={{ backgroundColor: primaryColor }}
      />
      <div
        className="absolute -bottom-20 -right-20 w-80 h-80 rounded-full opacity-20"
        style={{ backgroundColor: secondaryColor }}
      />
    </section>
  );
};

CTABlock.propTypes = {
  content: PropTypes.shape({
    title: PropTypes.string,
    subtitle: PropTypes.string,
    buttonText: PropTypes.string,
    buttonLink: PropTypes.string,
  }),
  styles: PropTypes.shape({
    primaryColor: PropTypes.string,
    secondaryColor: PropTypes.string,
    backgroundColor: PropTypes.string,
    textColor: PropTypes.string,
    accentColor: PropTypes.string,
  }),
  blockStyles: PropTypes.object,
};

export default CTABlock;
