import React, { useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { resolvePlaceholders } from '../../utils/placeholders';

/**
 * Rich text inline editor with bold / italic / link toolbar.
 */
const EditableRichText = ({
  value = '',
  onChange,
  tag: Tag = 'div',
  className = '',
  style = {},
  placeholderVars = {},
}) => {
  const ref = useRef(null);
  const [focused, setFocused] = useState(false);
  const html = resolvePlaceholders(value, placeholderVars);

  const exec = (cmd, val = null) => {
    document.execCommand(cmd, false, val);
    ref.current?.focus();
  };

  const handleBlur = () => {
    setFocused(false);
    const htmlContent = ref.current?.innerHTML ?? '';
    if (htmlContent !== value) onChange?.(htmlContent);
  };

  const handleLink = () => {
    const url = window.prompt('URL ссылки:', 'https://');
    if (url) exec('createLink', url);
  };

  return (
    <div className="wb-rich-text-wrap">
      {focused && (
        <div className="wb-rich-toolbar" onMouseDown={(e) => e.preventDefault()}>
          <button type="button" onClick={() => exec('bold')} title="Жирный">
            <b>B</b>
          </button>
          <button type="button" onClick={() => exec('italic')} title="Курсив">
            <i>I</i>
          </button>
          <button type="button" onClick={handleLink} title="Ссылка">
            🔗
          </button>
        </div>
      )}
      <Tag
        ref={ref}
        className={`wb-editable-rich ${className}`}
        style={style}
        contentEditable
        suppressContentEditableWarning
        dangerouslySetInnerHTML={{ __html: html }}
        onFocus={() => setFocused(true)}
        onBlur={handleBlur}
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
};

EditableRichText.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func,
  tag: PropTypes.string,
  className: PropTypes.string,
  style: PropTypes.object,
  placeholderVars: PropTypes.object,
};

export default EditableRichText;
