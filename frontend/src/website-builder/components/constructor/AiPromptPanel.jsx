import React, { useState } from 'react';
import PropTypes from 'prop-types';

const EXAMPLE_PROMPTS = [
  'Сделай заголовок крупнее',
  'Добавь иконки к услугам',
  'Сделай фон темнее',
  'Сделай текст более дружелюбным',
];

const AiPromptPanel = ({ selectedBlock, loading, onSubmit }) => {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!prompt.trim() || !selectedBlock) return;
    await onSubmit(selectedBlock.id, prompt.trim());
    setPrompt('');
  };

  return (
    <div className="wb-ai-panel">
      <h3>AI-ассистент</h3>
      <p className="wb-hint-text">
        {selectedBlock
          ? 'Опишите изменения для выбранного блока'
          : 'Выберите блок слева'}
      </p>
      <form onSubmit={handleSubmit}>
        <textarea
          className="wb-ai-input"
          rows={3}
          placeholder="Например: сделай заголовок крупнее и добавь эмодзи"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={!selectedBlock || loading}
        />
        <button
          type="submit"
          className="wb-btn wb-btn--primary wb-btn--full"
          disabled={!selectedBlock || !prompt.trim() || loading}
        >
          {loading ? 'Применяем...' : 'Применить'}
        </button>
      </form>
      <div className="wb-ai-examples">
        <span>Примеры:</span>
        {EXAMPLE_PROMPTS.map((ex) => (
          <button
            key={ex}
            type="button"
            className="wb-ai-example-chip"
            disabled={!selectedBlock}
            onClick={() => setPrompt(ex)}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
};

AiPromptPanel.propTypes = {
  selectedBlock: PropTypes.object,
  loading: PropTypes.bool,
  onSubmit: PropTypes.func.isRequired,
};

export default AiPromptPanel;
