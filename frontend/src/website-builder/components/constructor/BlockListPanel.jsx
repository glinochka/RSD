import React from 'react';
import PropTypes from 'prop-types';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import BlockIcon from './BlockIcon';
import { BLOCK_TYPE_META } from '../../utils/blockDefaults';

function SortableBlockItem({ block, selected, onSelect, onDuplicate, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: block.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const meta = BLOCK_TYPE_META[block.type] || { label: block.type };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`wb-block-list-item ${selected ? 'wb-block-list-item--selected' : ''} ${isDragging ? 'wb-block-list-item--dragging' : ''}`}
      onClick={() => onSelect(block.id)}
    >
      <button type="button" className="wb-block-list-item__drag" {...attributes} {...listeners}>
        ⋮⋮
      </button>
      <BlockIcon type={meta.icon || block.type} className="w-5 h-5" />
      <span className="wb-block-list-item__label">{meta.label}</span>
      <div className="wb-block-list-item__actions">
        <button
          type="button"
          title="Дублировать"
          onClick={(e) => {
            e.stopPropagation();
            onDuplicate(block.id);
          }}
        >
          ⧉
        </button>
        <button
          type="button"
          title="Удалить"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(block.id);
          }}
        >
          ×
        </button>
      </div>
    </div>
  );
}

SortableBlockItem.propTypes = {
  block: PropTypes.object.isRequired,
  selected: PropTypes.bool,
  onSelect: PropTypes.func.isRequired,
  onDuplicate: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};

const BlockListPanel = ({
  blocks,
  selectedBlockId,
  onSelect,
  onReorder,
  onAddClick,
  onDuplicate,
  onDelete,
}) => {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = blocks.findIndex((b) => b.id === active.id);
    const newIndex = blocks.findIndex((b) => b.id === over.id);
    onReorder(arrayMove(blocks, oldIndex, newIndex));
  };

  return (
    <aside className="wb-panel wb-panel--left">
      <div className="wb-panel__header">
        <h2>Блоки</h2>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={blocks.map((b) => b.id)} strategy={verticalListSortingStrategy}>
          <div className="wb-block-list">
            {blocks.map((block) => (
              <SortableBlockItem
                key={block.id}
                block={block}
                selected={block.id === selectedBlockId}
                onSelect={onSelect}
                onDuplicate={onDuplicate}
                onDelete={onDelete}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <button type="button" className="wb-btn wb-btn--add-block" onClick={onAddClick}>
        + Добавить блок
      </button>
    </aside>
  );
};

BlockListPanel.propTypes = {
  blocks: PropTypes.array.isRequired,
  selectedBlockId: PropTypes.number,
  onSelect: PropTypes.func.isRequired,
  onReorder: PropTypes.func.isRequired,
  onAddClick: PropTypes.func.isRequired,
  onDuplicate: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
};

export default BlockListPanel;
