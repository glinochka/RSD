import React, { useId } from 'react';
import '../styles/userbotSessionFile.css';

const UserbotSessionFileUpload = ({ disabled = false, isImporting = false, onFileSelect }) => {
  const inputId = useId();
  const isDisabled = disabled || isImporting;

  return (
    <div className="userbot-session-file-upload">
      <input
        id={inputId}
        type="file"
        accept=".zip,.session,.txt"
        className="userbot-session-file-upload__input"
        disabled={isDisabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFileSelect(file);
          event.target.value = '';
        }}
      />
      <label
        htmlFor={inputId}
        className={`userbot-session-file-upload__label${isDisabled ? ' is-disabled' : ''}`}
      >
        <svg
          className="userbot-session-file-upload__icon"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <path
            d="M12 15V5m0 0l-3.5 3.5M12 5l3.5 3.5M5 19h14"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="userbot-session-file-upload__title">
          {isImporting ? 'Импорт сессии…' : 'Выбрать файл сессии'}
        </span>
        <span className="userbot-session-file-upload__formats">.zip, .session или .txt</span>
      </label>
    </div>
  );
};

export default UserbotSessionFileUpload;
