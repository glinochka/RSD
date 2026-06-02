import React from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
const SAVE_LABELS = {
  saved: 'Сохранено',
  saving: 'Сохранение...',
  dirty: 'Есть изменения',
  error: 'Ошибка сохранения',
};

const ConstructorTopBar = ({
  title,
  status,
  saveStatus,
  onSave,
  onPreview,
  onPublish,
  onUnpublish,
}) => {
  const navigate = useNavigate();

  return (
    <header className="wb-constructor-topbar">
      <div className="wb-constructor-topbar__left">
        <button type="button" className="wb-btn-icon" onClick={() => navigate(-1)} title="Назад">
          ←
        </button>
        <div>
          <h1 className="wb-constructor-topbar__title">{title || 'Конструктор сайта'}</h1>
          <span className={`wb-save-status wb-save-status--${saveStatus}`}>
            {SAVE_LABELS[saveStatus] || saveStatus}
          </span>
        </div>
      </div>

      <div className="wb-constructor-topbar__actions">
        <button type="button" className="wb-btn wb-btn--ghost" onClick={onSave}>
          Сохранить
        </button>
        <button type="button" className="wb-btn wb-btn--ghost" onClick={onPreview}>
          Предпросмотр
        </button>
        {status === 'published' ? (
          <button type="button" className="wb-btn wb-btn--warning" onClick={onUnpublish}>
            Снять с публикации
          </button>
        ) : (
          <button type="button" className="wb-btn wb-btn--primary" onClick={onPublish}>
            Опубликовать
          </button>
        )}
      </div>
    </header>
  );
};

ConstructorTopBar.propTypes = {
  title: PropTypes.string,
  status: PropTypes.string,
  saveStatus: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  onPreview: PropTypes.func.isRequired,
  onPublish: PropTypes.func.isRequired,
  onUnpublish: PropTypes.func.isRequired,
};

export default ConstructorTopBar;
