import React from 'react';
import PropTypes from 'prop-types';
import { BLOCK_TYPE_META } from '../../utils/blockDefaults';
import BlockIcon from './BlockIcon';

const FONT_OPTIONS = [
  { value: 'Inter, system-ui, sans-serif', label: 'Inter' },
  { value: 'Roboto, sans-serif', label: 'Roboto' },
  { value: '"Playfair Display", serif', label: 'Playfair Display' },
  { value: '"Open Sans", sans-serif', label: 'Open Sans' },
  { value: 'Georgia, serif', label: 'Georgia' },
];

const BlockSettingsPanel = ({
  selectedBlock,
  globalStyles,
  onGlobalStylesChange,
  onBlockStylesChange,
}) => {
  const blockStyles = selectedBlock?.styles || {};

  return (
    <aside className="wb-panel wb-panel--right">
      <div className="wb-panel__header">
        <h2>Настройки</h2>
      </div>

      <section className="wb-settings-section">
        <h3>Сайт</h3>
        <label className="wb-field">
          <span>Основной цвет</span>
          <input
            type="color"
            value={globalStyles.primaryColor || '#2563EB'}
            onChange={(e) => onGlobalStylesChange({ primaryColor: e.target.value })}
          />
        </label>
        <label className="wb-field wb-field--row">
          <span>Тёмная тема</span>
          <input
            type="checkbox"
            checked={!!globalStyles.darkMode}
            onChange={(e) => onGlobalStylesChange({ darkMode: e.target.checked })}
          />
        </label>
        <label className="wb-field">
          <span>Шрифт</span>
          <select
            value={globalStyles.fontFamily || FONT_OPTIONS[0].value}
            onChange={(e) => onGlobalStylesChange({ fontFamily: e.target.value })}
          >
            {FONT_OPTIONS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      {selectedBlock && (
        <section className="wb-settings-section">
          <h3 className="wb-settings-block-title">
            <BlockIcon type={BLOCK_TYPE_META[selectedBlock.type]?.icon || selectedBlock.type} />
            {BLOCK_TYPE_META[selectedBlock.type]?.label || selectedBlock.type}
          </h3>

          <label className="wb-field">
            <span>Отступ (padding): {blockStyles.padding ?? 0}px</span>
            <input
              type="range"
              min={0}
              max={120}
              step={4}
              value={blockStyles.padding ?? 0}
              onChange={(e) =>
                onBlockStylesChange(selectedBlock.id, { padding: Number(e.target.value) })
              }
            />
          </label>

          <label className="wb-field">
            <span>Внешний отступ (margin): {blockStyles.margin ?? 0}px</span>
            <input
              type="range"
              min={0}
              max={80}
              step={4}
              value={blockStyles.margin ?? 0}
              onChange={(e) =>
                onBlockStylesChange(selectedBlock.id, { margin: Number(e.target.value) })
              }
            />
          </label>

          <label className="wb-field">
            <span>Выравнивание</span>
            <div className="wb-align-buttons">
              {['left', 'center', 'right'].map((align) => (
                <button
                  key={align}
                  type="button"
                  className={blockStyles.textAlign === align ? 'active' : ''}
                  onClick={() => onBlockStylesChange(selectedBlock.id, { textAlign: align })}
                >
                  {align === 'left' ? '⬅' : align === 'center' ? '↔' : '➡'}
                </button>
              ))}
            </div>
          </label>

          <label className="wb-field">
            <span>Скругление углов</span>
            <select
              value={blockStyles.borderRadius || 'none'}
              onChange={(e) =>
                onBlockStylesChange(selectedBlock.id, { borderRadius: e.target.value })
              }
            >
              <option value="none">Без скругления</option>
              <option value="medium">Среднее</option>
              <option value="round">Круглое</option>
            </select>
          </label>
        </section>
      )}

      <section className="wb-settings-section wb-placeholders-hint">
        <h3>Плейсхолдеры</h3>
        <p className="wb-hint-text">
          В тексте можно использовать: <code>{'{{business_name}}'}</code>,{' '}
          <code>{'{{phone}}'}</code>, <code>{'{{email}}'}</code>
        </p>
      </section>
    </aside>
  );
};

BlockSettingsPanel.propTypes = {
  selectedBlock: PropTypes.object,
  globalStyles: PropTypes.object.isRequired,
  onGlobalStylesChange: PropTypes.func.isRequired,
  onBlockStylesChange: PropTypes.func.isRequired,
};

export default BlockSettingsPanel;
