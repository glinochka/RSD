import React from 'react';

const UbtUnsaved = ({ dirty }) => {
  if (!dirty) {
    return null;
  }
  return (
    <p className="nc-note">
      Есть несохранённые изменения. Нажмите «Сохранить», иначе выбор аккаунтов, чатов и поля не применятся.
    </p>
  );
};

export default UbtUnsaved;
