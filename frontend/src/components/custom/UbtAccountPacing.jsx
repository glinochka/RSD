import Stepper from './UbtStepper';
import { COMMENT_GAP_MAX_DEFAULT, COMMENT_GAP_MIN_DEFAULT } from '../../pages/custom/automation/delayLimits';

const toMin = (seconds, fallback) => Math.max(1, Math.round(Number(seconds || fallback) / 60) || Math.round(fallback / 60));

const UbtAccountPacing = ({
  settings,
  onPatch,
  noun = 'действий',
  capDefault = 15,
}) => {
  const cap = Number(settings?.max_per_account ?? capDefault) || capDefault;
  const loMin = toMin(settings?.comment_delay_min, COMMENT_GAP_MIN_DEFAULT);
  const hiMin = Math.max(loMin, toMin(settings?.comment_delay_max, COMMENT_GAP_MAX_DEFAULT));
  return (
    <div style={{ marginTop: 12 }}>
      <div className="nc-row">
        <span className="nc-muted">Максимум {noun} в день на аккаунт</span>
        <Stepper value={cap} min={1} max={200} onChange={(value) => onPatch({ max_per_account: value })} />
      </div>
      <div className="nc-row" style={{ marginTop: 10 }}>
        <span className="nc-muted">Пауза между {noun}</span>
        <Stepper
          value={loMin}
          min={1}
          max={90}
          onChange={(value) => onPatch({
            comment_delay_min: value * 60,
            comment_delay_max: Math.max(value * 60, hiMin * 60),
          })}
        />
        <span className="nc-muted">до</span>
        <Stepper
          value={hiMin}
          min={loMin}
          max={90}
          onChange={(value) => onPatch({ comment_delay_max: value * 60 })}
        />
        <span className="nc-muted">мин</span>
      </div>
      <p className="nc-muted" style={{ marginTop: 8 }}>
        После отправки аккаунт молчит это время, затем берёт следующее действие. По умолчанию 15 в день и 20–40 минут.
      </p>
    </div>
  );
};

export default UbtAccountPacing;
