import React from 'react';
import PropTypes from 'prop-types';
import { BLOCK_TYPE_META } from '../../utils/blockDefaults';

const DeleteBlockDialog = ({ block, onConfirm, onCancel }) => {
  if (!block) return null;
  const label = BLOCK_TYPE_META[block.type]?.label || block.type;

  return (
    <div className="wb-modal-overlay">
      <div className="wb-modal wb-modal--sm">
        <h2>Удалить блок?</h2>
        <p>
          Блок «{label}» будет удалён без возможности восстановления.
        </p>
        <div className="wb-modal__actions">
          <button type="button" className="wb-btn wb-btn--ghost" onClick={onCancel}>
            Отмена
          </button>
          <button type="button" className="wb-btn wb-btn--danger" onClick={onConfirm}>
            Удалить
          </button>
        </div>
      </div>
    </div>
  );
};

DeleteBlockDialog.propTypes = {
  block: PropTypes.object,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

export default DeleteBlockDialog;
