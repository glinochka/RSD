const UbtJobControls = ({ job, busy, onPause, onResume, onCancel, onEdit }) => {
  if (!job) {
    return null;
  }
  return (
    <>
      {job.can_pause ? (
        <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={onPause}>Пауза</button>
      ) : null}
      {job.can_resume ? (
        <button type="button" className="acc-btn acc-btn--primary" disabled={busy} onClick={onResume}>Продолжить</button>
      ) : null}
      {job.can_edit && onEdit ? (
        <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={onEdit}>Изменить</button>
      ) : null}
      {job.can_cancel ? (
        <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={onCancel}>Остановить</button>
      ) : null}
    </>
  );
};

export default UbtJobControls;
