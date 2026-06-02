import React from 'react';
import PropTypes from 'prop-types';
import BlockIcon from './BlockIcon';
import { ADDABLE_BLOCK_TYPES, BLOCK_TYPE_META } from '../../utils/blockDefaults';

const AddBlockModal = ({ open, onClose, onSelect }) => {
  if (!open) return null;

  return (
    <div className="wb-modal-overlay" onClick={onClose}>
      <div className="wb-modal" onClick={(e) => e.stopPropagation()}>
        <div className="wb-modal__header">
          <h2>Добавить блок</h2>
          <button type="button" className="wb-btn-icon" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="wb-modal__grid">
          {ADDABLE_BLOCK_TYPES.map((type) => {
            const meta = BLOCK_TYPE_META[type];
            return (
              <button
                key={type}
                type="button"
                className="wb-block-type-card"
                onClick={() => {
                  onSelect(type);
                  onClose();
                }}
              >
                <BlockIcon type={meta.icon} className="w-8 h-8" />
                <strong>{meta.label}</strong>
                <span>{meta.description}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

AddBlockModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSelect: PropTypes.func.isRequired,
};

export default AddBlockModal;
