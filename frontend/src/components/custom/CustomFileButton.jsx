import React, { useId, useRef } from 'react';
import '../../styles/customFileButton.css';

const CustomFileButton = ({
  id,
  accept,
  disabled = false,
  busy = false,
  variant = 'outline',
  children,
  fileName,
  onFile,
  className = '',
}) => {
  const autoId = useId();
  const inputId = id || autoId;
  const inputRef = useRef(null);
  const isDisabled = Boolean(disabled || busy);
  const btnClass = variant === 'black' ? 'btn btn-black' : 'btn btn-outline';

  return (
    <span className={`custom-file-btn ${className}`.trim()}>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        disabled={isDisabled}
        className="custom-file-btn__input"
        onChange={(event) => {
          const file = event.target.files && event.target.files[0];
          if (file && onFile) {
            onFile(file);
          }
          event.target.value = '';
        }}
      />
      <button
        type="button"
        className={btnClass}
        disabled={isDisabled}
        onClick={() => inputRef.current && inputRef.current.click()}
      >
        {children}
      </button>
      {fileName ? <span className="form-hint custom-file-btn__name">{fileName}</span> : null}
    </span>
  );
};

export default CustomFileButton;
