import Stepper from './UbtStepper';
import { DELAY_MAX_SECONDS, JOIN_DELAY_PRESETS } from '../../pages/custom/automation/delayLimits';
import { matchesPreset } from '../../pages/custom/automation/customNav';

const UbtJoinDelay = ({ settings, onPatch }) => {
  const lo = Number(settings?.join_delay_min ?? JOIN_DELAY_PRESETS.rec.join_delay_min);
  const hi = Number(settings?.join_delay_max ?? JOIN_DELAY_PRESETS.rec.join_delay_max);
  return (
    <div style={{ marginTop: 12 }}>
      <div className="nc-row">
        <span className="nc-muted">Задержка между вступлениями</span>
        <button type="button" className={`nc-chip ${matchesPreset(settings, JOIN_DELAY_PRESETS.min) ? 'is-on' : ''}`} onClick={() => onPatch(JOIN_DELAY_PRESETS.min)}>Мин</button>
        <button type="button" className={`nc-chip ${matchesPreset(settings, JOIN_DELAY_PRESETS.rec) ? 'is-on' : ''}`} onClick={() => onPatch(JOIN_DELAY_PRESETS.rec)}>Рек.</button>
        <button type="button" className={`nc-chip ${matchesPreset(settings, JOIN_DELAY_PRESETS.max) ? 'is-on' : ''}`} onClick={() => onPatch(JOIN_DELAY_PRESETS.max)}>Макс</button>
      </div>
      <div className="nc-row" style={{ marginTop: 8 }}>
        <Stepper value={lo} min={30} max={DELAY_MAX_SECONDS} onChange={(value) => onPatch({ join_delay_min: value, join_delay_max: Math.max(value, hi) })} />
        <span className="nc-muted">до</span>
        <Stepper value={Math.max(lo, hi)} min={lo} max={DELAY_MAX_SECONDS} onChange={(value) => onPatch({ join_delay_max: value })} />
        <span className="nc-muted">сек</span>
      </div>
      <p className="nc-muted" style={{ marginTop: 8 }}>Отдельная пауза между джойнами. На комментарии и ответы не влияет.</p>
    </div>
  );
};

export default UbtJoinDelay;
