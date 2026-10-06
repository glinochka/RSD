import React from 'react';

const CHAT_HINT = 'Папка целиком становится пулом задачи. Дальше она делится между аккаунтами: addlist, вступление и работа.';
const USER_HINT = 'Папка из парсера юзеров. Её можно поставить целью ЛС-рассылки или масспрайминга.';

const UbtFolderPicker = ({ folders = [], selectedIds, onToggle, hint, emptyText, kind = 'chats', readOnly = false }) => {
  const selected = selectedIds instanceof Set ? selectedIds : new Set(selectedIds || []);
  const copy = hint || (kind === 'users' ? USER_HINT : CHAT_HINT);
  if (!folders.length) {
    return (
      <div className="nc-empty" role="status" style={{ marginTop: 12 }}>
        {emptyText || (kind === 'users'
          ? 'Папок юзеров нет — сначала выполните задачу в «Парсер юзеров».'
          : 'Папок нет — загрузите файл в «Чаты и каналы». Один файл становится одной папкой.')}
      </div>
    );
  }
  return (
    <div style={{ marginTop: 12 }}>
      <p className="nc-hint">{copy}</p>
      <div className="nc-list" style={{ marginTop: 8 }}>
        {folders.map((folder) => {
          const on = selected.has(folder.id);
          if (readOnly) {
            return (
              <div key={folder.id} className="nc-item">
                <div>
                  <strong>{folder.name}</strong>
                  <span>{folder.count ?? folder.chats_count ?? 0} шт.</span>
                </div>
              </div>
            );
          }
          return (
            <button key={folder.id} type="button" className={`nc-item ${on ? 'is-on' : ''}`} onClick={() => onToggle(folder.id)}>
              <div>
                <strong>{folder.name}</strong>
                <span>{folder.count ?? folder.chats_count ?? 0} шт.</span>
              </div>
              <span>{on ? 'цель' : 'выбрать'}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default UbtFolderPicker;
