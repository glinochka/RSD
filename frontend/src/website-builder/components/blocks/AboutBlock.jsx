/**
 * About Block Component
 * Company description with optional image
 */
import React from 'react';
import PropTypes from 'prop-types';
import { EditableText, EditableRichText } from '../editor';

const AboutBlock = ({
  content,
  styles = {},
  blockStyles = {},
  editMode = false,
  onContentChange,
  placeholderVars = {},
}) => {
  const {
    title = 'О нас',
    text = '',
    imageUrl = '',
    imagePosition = 'right', // 'left' or 'right'
  } = content || {};

  const {
    primaryColor = '#2563EB',
    backgroundColor = '#F9FAFB',
    textColor = '#1F2937',
    darkMode = false,
  } = styles;

  const containerBg = darkMode ? '#111827' : backgroundColor;
  const titleColor = darkMode ? '#FFFFFF' : textColor;
  const textSecondary = darkMode ? '#D1D5DB' : '#4B5563';

  const imageContent = imageUrl ? (
    <div className="relative">
      <img
        src={imageUrl}
        alt={title}
        className="w-full h-64 md:h-80 lg:h-96 object-cover rounded-xl md:rounded-2xl shadow-lg"
      />
      {/* Decorative element */}
      <div
        className="absolute -bottom-4 -right-4 w-full h-full rounded-xl md:rounded-2xl -z-10"
        style={{ backgroundColor: `${primaryColor}20` }}
      />
    </div>
  ) : null;

  const textContent = (
    <div className="flex flex-col justify-center">
      {editMode ? (
        <EditableText
          tag="h2"
          value={title}
          onChange={(v) => onContentChange?.({ title: v })}
          placeholderVars={placeholderVars}
          className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4 md:mb-6"
          style={{ color: titleColor }}
        />
      ) : (
        <h2
          className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4 md:mb-6"
          style={{ color: titleColor }}
        >
          {title}
        </h2>
      )}
      <div
        className="w-16 h-1 rounded-full mb-6"
        style={{ backgroundColor: primaryColor }}
      />
      {editMode ? (
        <EditableRichText
          value={text}
          onChange={(v) => onContentChange?.({ text: v })}
          placeholderVars={placeholderVars}
          className="text-base md:text-lg leading-relaxed"
          style={{ color: textSecondary }}
        />
      ) : (
        <div
          className="text-base md:text-lg leading-relaxed whitespace-pre-wrap"
          style={{ color: textSecondary }}
        >
          {text}
        </div>
      )}
    </div>
  );

  return (
    <section
      id="about"
      className="py-12 md:py-16 lg:py-20"
      style={{ backgroundColor: containerBg }}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div
          className={`grid grid-cols-1 ${imageUrl ? 'lg:grid-cols-2' : ''} gap-8 md:gap-12 items-center`}
        >
          {imageUrl && imagePosition === 'left' && (
            <div className="order-2 lg:order-1">{imageContent}</div>
          )}

          <div className={imageUrl ? (imagePosition === 'left' ? 'order-1 lg:order-2' : '') : ''}>
            {textContent}
          </div>

          {imageUrl && imagePosition === 'right' && (
            <div className="order-2">{imageContent}</div>
          )}
        </div>
      </div>
    </section>
  );
};

AboutBlock.propTypes = {
  content: PropTypes.shape({
    title: PropTypes.string,
    text: PropTypes.string,
    imageUrl: PropTypes.string,
    imagePosition: PropTypes.oneOf(['left', 'right']),
  }),
  styles: PropTypes.shape({
    primaryColor: PropTypes.string,
    backgroundColor: PropTypes.string,
    textColor: PropTypes.string,
    darkMode: PropTypes.bool,
  }),
  blockStyles: PropTypes.object,
};

export default AboutBlock;
