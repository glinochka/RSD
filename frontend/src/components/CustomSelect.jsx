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
  multiple = false,
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

  const selectedValues = multiple
    ? (Array.isArray(value) ? value : [])
    : value;
  const selectedOptions = multiple
    ? options.filter((option) => selectedValues.includes(option.value))
    : options.filter((option) => option.value === value);
  const selectedOption = selectedOptions[0];
  const displayLabel = multiple
    ? (selectedOptions.length ? selectedOptions.map((option) => option.label).join(', ') : placeholder)
    : (selectedOption?.label || placeholder);
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
    if (multiple) {
      const current = Array.isArray(value) ? [...value] : [];
      const next = current.includes(nextValue)
        ? current.filter((item) => item !== nextValue)
        : [...current, nextValue];
      onChange({
        target: {
          name,
          value: next,
        },
      });
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
            (multiple ? selectedOptions.length === 0 : !selectedOption) && placeholder
              ? 'custom-select-value--placeholder'
              : ''
          }`}
        >
          {displayLabel}
        </span>
        <span className={`custom-select-arrow ${isOpen ? 'open' : ''}`} aria-hidden="true" />
      </button>
      {isOpen && !disabled && (
        <div className="custom-select-dropdown" role="listbox" aria-labelledby={id}>
          {options.map((option) => {
            const isSelected = multiple
              ? selectedValues.includes(option.value)
              : option.value === value;
            return (
            <button
              key={option.value === '' || option.value == null ? `empty:${option.label}` : option.value}
              type="button"
              className={`custom-select-option ${isSelected ? 'selected' : ''} ${
                option.disabled ? 'disabled' : ''
              }`}
              onClick={() => handleSelectOption(option.value)}
              disabled={option.disabled}
            >
              {multiple ? (
                <span className={`custom-select-check ${isSelected ? 'checked' : ''}`} aria-hidden="true" />
              ) : null}
              {option.label}
            </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default CustomSelect;
