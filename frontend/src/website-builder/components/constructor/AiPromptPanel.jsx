import React, { useState, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import { Upload, X, Image as ImageIcon } from 'lucide-react';

const EXAMPLE_PROMPTS_BLOCK = [
  'Сделай заголовок крупнее',
  'Добавь иконки к услугам',
  'Сделай фон темнее',
  'Сделай текст более дружелюбным',
];

const EXAMPLE_PROMPTS_FULLPAGE = [
  'Сделай дизайн более современным',
  'Добавь секцию с отзывами клиентов',
  'Измени цветовую схему на синюю',
  'Сделай hero-секцию ярче и больше',
  'Добавь анимации при скролле',
  'Перепиши текст более продающим',
  'Добавь Яндекс Карту с адресом компании',
];

const AiPromptPanel = ({ selectedBlock, blocks, loading, onSubmit, feedback, onDismissFeedback }) => {
  const [prompt, setPrompt] = useState('');
  const [attachedImages, setAttachedImages] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const isFullpage = selectedBlock?.type === 'fullpage' ||
    blocks?.some((b) => b.type === 'fullpage');
  const fullpageBlock = blocks?.find((b) => b.type === 'fullpage');

  const targetBlock = isFullpage ? fullpageBlock : selectedBlock;
  const canSubmit = Boolean(targetBlock) && Boolean(prompt.trim()) && !loading;

  const handleImageUpload = useCallback((files) => {
    const imageFiles = Array.from(files).filter(file => file.type.startsWith('image/'));
    const newImages = imageFiles.map(file => ({
      file,
      id: `${file.name}-${Date.now()}`,
      preview: URL.createObjectURL(file),
      name: file.name,
    }));
    setAttachedImages(prev => [...prev, ...newImages].slice(0, 5)); // Max 5 images
  }, []);

  const handleRemoveImage = useCallback((id) => {
    setAttachedImages(prev => {
      const img = prev.find(i => i.id === id);
      if (img?.preview) URL.revokeObjectURL(img.preview);
      return prev.filter(i => i.id !== id);
    });
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    handleImageUpload(e.dataTransfer.files);
  }, [handleImageUpload]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit || !targetBlock) return;
    await onSubmit(targetBlock.id, prompt.trim(), attachedImages);
    setPrompt('');
    setAttachedImages([]);
  };

  const examples = isFullpage ? EXAMPLE_PROMPTS_FULLPAGE : EXAMPLE_PROMPTS_BLOCK;
  const hintText = isFullpage
    ? 'Опишите изменения для сайта — AI перепишет код'
    : selectedBlock
      ? 'Опишите изменения для выбранного блока'
      : 'Выберите блок слева';

  return (
    <div className="wb-ai-panel">
      <h3>{isFullpage ? 'AI-конструктор' : 'AI-ассистент'}</h3>
      <p className="wb-hint-text">{hintText}</p>
      
      {/* Image Upload Area */}
      <div 
        className={`wb-ai-upload-area ${isDragging ? 'wb-ai-upload-area--dragging' : ''} ${attachedImages.length > 0 ? 'wb-ai-upload-area--has-images' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="wb-ai-file-input"
          onChange={(e) => handleImageUpload(e.target.files)}
          disabled={!targetBlock || loading || attachedImages.length >= 5}
        />
        
        {attachedImages.length === 0 ? (
          <div className="wb-ai-upload-placeholder">
            <Upload className="wb-ai-upload-icon" />
            <span className="wb-ai-upload-text">
              Перетащите изображения или <span className="wb-ai-upload-link">выберите файл</span>
            </span>
            <span className="wb-ai-upload-hint">
              Макс. 5 изображений. Для замены заглушек, добавления фонов или Яндекс Карт
            </span>
          </div>
        ) : (
          <div className="wb-ai-images-grid">
            {attachedImages.map((img) => (
              <div key={img.id} className="wb-ai-image-thumb">
                <img src={img.preview} alt={img.name} />
                <button
                  type="button"
                  className="wb-ai-image-remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveImage(img.id);
                  }}
                  disabled={loading}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
            {attachedImages.length < 5 && (
              <div className="wb-ai-image-add">
                <ImageIcon className="w-5 h-5" />
                <span>+</span>
              </div>
            )}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          className="wb-ai-input"
          rows={3}
          placeholder={
            isFullpage
              ? attachedImages.length > 0 
                ? 'Опишите, что сделать с загруженными изображениями...'
                : 'Например: добавь секцию FAQ, измени палитру на тёплую...'
              : 'Например: сделай заголовок крупнее и добавь эмодзи'
          }
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={!targetBlock || loading}
        />
        <button
          type="submit"
          className="wb-btn wb-btn--primary wb-btn--full"
          disabled={!canSubmit}
        >
          {loading ? (
            <>
              <span className="wb-ai-spinner"></span>
              AI пишет код...
            </>
          ) : (
            <>Применить {attachedImages.length > 0 && `(${attachedImages.length} изобр.)`}</>
          )}
        </button>
      </form>
      
      <div className="wb-ai-examples">
        <span>Примеры:</span>
        {examples.map((ex) => (
          <button
            key={ex}
            type="button"
            className="wb-ai-example-chip"
            disabled={!targetBlock}
            onClick={() => setPrompt(ex)}
          >
            {ex}
          </button>
        ))}
      </div>

      {feedback && (
        <div className={`wb-ai-feedback wb-ai-feedback--${feedback.type}`}>
          <div className="wb-ai-feedback-content">
            {feedback.type === 'success' ? (
              <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
            <span>{feedback.message}</span>
          </div>
          {onDismissFeedback && (
            <button
              type="button"
              className="wb-ai-feedback-close"
              onClick={onDismissFeedback}
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      )}
    </div>
  );
};

AiPromptPanel.propTypes = {
  selectedBlock: PropTypes.object,
  blocks: PropTypes.array,
  loading: PropTypes.bool,
  onSubmit: PropTypes.func.isRequired,
  feedback: PropTypes.shape({
    type: PropTypes.oneOf(['success', 'error']),
    message: PropTypes.string,
  }),
  onDismissFeedback: PropTypes.func,
};

export default AiPromptPanel;
