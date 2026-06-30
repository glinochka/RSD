import React, { useEffect, useRef, useState } from 'react';
import '../styles/customSelect.css';

const CustomSelect = ({
  id,
  name,
  value,
  options,
  onChange,
  disabled = false,
  className = '',
  error = false,
  placeholder = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleOutsideClick = (event) => {
      if (!selectRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const selectedOption = options.find((option) => option.value === value);
  const displayLabel = selectedOption?.label || placeholder;
  const buttonClassName = [
    'custom-select-trigger',
    className,
    error ? 'error' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const handleSelectOption = (nextValue) => {
    const optionToSelect = options.find((option) => option.value === nextValue);
    if (optionToSelect?.disabled) {
      return;
    }
    onChange({
      target: {
        name,
        value: nextValue,
      },
    });
    setIsOpen(false);
  };

  return (
    <div className={`custom-select ${disabled ? 'disabled' : ''}`} ref={selectRef}>
      <button
        id={id}
        type="button"
        className={buttonClassName}
        onClick={() => setIsOpen((prev) => !prev)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span
          className={`custom-select-value ${
            !selectedOption && placeholder ? 'custom-select-value--placeholder' : ''
          }`}
        >
          {displayLabel}
        </span>
        <span className={`custom-select-arrow ${isOpen ? 'open' : ''}`} aria-hidden="true" />
      </button>
      {isOpen && !disabled && (
        <div className="custom-select-dropdown" role="listbox" aria-labelledby={id}>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`custom-select-option ${option.value === value ? 'selected' : ''} ${
                option.disabled ? 'disabled' : ''
              }`}
              onClick={() => handleSelectOption(option.value)}
              disabled={option.disabled}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default CustomSelect;
