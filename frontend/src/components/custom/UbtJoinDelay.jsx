import Stepper from './UbtStepper';
import { JOIN_DELAY_PRESETS } from '../../pages/custom/automation/delayLimits';
import { matchesPreset } from '../../pages/custom/automation/customNav';

const toMin = (seconds, fallback) => Math.max(1, Math.round(Number(seconds || fallback) / 60) || Math.round(fallback / 60));

const UbtJoinDelay = ({ settings, onPatch }) => {
  const rec = JOIN_DELAY_PRESETS.rec;
  const loMin = toMin(settings?.join_delay_min, rec.join_delay_min);
  const hiMin = Math.max(loMin, toMin(settings?.join_delay_max, rec.join_delay_max));
  return (
    <div style={{ marginTop: 12 }}>
      <div className="nc-row">
        <span className="nc-muted">Задержка между вступлениями</span>
        <button type="button" className={`nc-chip ${matchesPreset(settings, JOIN_DELAY_PRESETS.min) ? 'is-on' : ''}`} onClick={() => onPatch(JOIN_DELAY_PRESETS.min)}>Мин</button>
        <button type="button" className={`nc-chip ${matchesPreset(settings, JOIN_DELAY_PRESETS.rec) ? 'is-on' : ''}`} onClick={() => onPatch(JOIN_DELAY_PRESETS.rec)}>Рек.</button>
        <button type="button" className={`nc-chip ${matchesPreset(settings, JOIN_DELAY_PRESETS.max) ? 'is-on' : ''}`} onClick={() => onPatch(JOIN_DELAY_PRESETS.max)}>Макс</button>
      </div>
      <div className="nc-row" style={{ marginTop: 8 }}>
        <Stepper
          value={loMin}
          min={1}
          max={90}
          onChange={(value) => onPatch({ join_delay_min: value * 60, join_delay_max: Math.max(value, hiMin) * 60 })}
        />
        <span className="nc-muted">до</span>
        <Stepper
          value={hiMin}
          min={loMin}
          max={90}
          onChange={(value) => onPatch({ join_delay_max: value * 60 })}
        />
        <span className="nc-muted">мин</span>
      </div>
      <p className="nc-muted" style={{ marginTop: 8 }}>
        Пауза между вступлениями одного аккаунта. В день 10–15 успешных входов, чёрные ящики в квоту не входят.
      </p>
    </div>
  );
};

export default UbtJoinDelay;
