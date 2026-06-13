import React, { useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { resolvePlaceholders } from '../../utils/placeholders';

/**
 * Inline plain-text editor (contenteditable).
 */
const EditableText = ({
  value = '',
  onChange,
  tag: Tag = 'span',
  className = '',
  style = {},
  placeholder = 'Нажмите для редактирования',
  placeholderVars = {},
  multiline = false,
}) => {
  const ref = useRef(null);
  const displayValue = resolvePlaceholders(value, placeholderVars);

  useEffect(() => {
    if (ref.current && ref.current.textContent !== displayValue) {
      ref.current.textContent = displayValue;
    }
  }, [displayValue]);

  const handleBlur = () => {
    const text = ref.current?.textContent?.trim() ?? '';
    if (text !== value) onChange?.(text);
  };

  const handleKeyDown = (e) => {
    if (!multiline && e.key === 'Enter') {
      e.preventDefault();
      ref.current?.blur();
    }
  };

  return (
    <Tag
      ref={ref}
      className={`wb-editable-text ${className}`}
      style={style}
      contentEditable
      suppressContentEditableWarning
      data-placeholder={placeholder}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      onClick={(e) => e.stopPropagation()}
    />
  );
};

EditableText.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func,
  tag: PropTypes.string,
  className: PropTypes.string,
  style: PropTypes.object,
  placeholder: PropTypes.string,
  placeholderVars: PropTypes.object,
  multiline: PropTypes.bool,
};

export default EditableText;
