import React, { useState } from 'react';
import PropTypes from 'prop-types';

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
];

const AiPromptPanel = ({ selectedBlock, blocks, loading, onSubmit }) => {
  const [prompt, setPrompt] = useState('');

  const isFullpage = selectedBlock?.type === 'fullpage' ||
    blocks?.some((b) => b.type === 'fullpage');
  const fullpageBlock = blocks?.find((b) => b.type === 'fullpage');

  const targetBlock = isFullpage ? fullpageBlock : selectedBlock;
  const canSubmit = Boolean(targetBlock) && Boolean(prompt.trim()) && !loading;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit || !targetBlock) return;
    await onSubmit(targetBlock.id, prompt.trim());
    setPrompt('');
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
      <form onSubmit={handleSubmit}>
        <textarea
          className="wb-ai-input"
          rows={3}
          placeholder={
            isFullpage
              ? 'Например: добавь секцию FAQ, измени палитру на тёплую...'
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
          {loading ? 'AI пишет код...' : 'Применить'}
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
    </div>
  );
};

AiPromptPanel.propTypes = {
  selectedBlock: PropTypes.object,
  blocks: PropTypes.array,
  loading: PropTypes.bool,
  onSubmit: PropTypes.func.isRequired,
};

export default AiPromptPanel;
