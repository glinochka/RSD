import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import FeatureToggle from '../../../components/FeatureToggle';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import { CF_STATUS, CF_VIDEO_FILTERS, formatWhen, money } from './contentFactoryLabels';
import '../../../styles/customAccountManager.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';
import '../../../styles/customContentFactory.css';

const CustomAutomationContentFactoryResultsPage = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [tokens, setTokens] = useState([]);
  const [videos, setVideos] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    const [overview, videoData, tokenData] = await Promise.all([
      customService.getContentFactory(id),
      customService.getContentFactoryVideos(id, { status: statusFilter || undefined, limit: 40 }),
      customService.getContentFactoryTokens(id),
    ]);
    setData(overview);
    setVideos(videoData.items || []);
    setTokens(tokenData.items || []);
  }, [id, statusFilter]);

  useEffect(() => {
    let mounted = true;
    loadAll()
      .then(() => {
        if (mounted) {
          setError(null);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Не удалось загрузить контент-завод');
        }
      });
    return () => {
      mounted = false;
    };
  }, [loadAll]);

  const inFlight = Number(data?.kpis?.in_flight || 0);
  useEffect(() => {
    if (inFlight <= 0) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      loadAll().catch(() => {});
    }, 15000);
    return () => window.clearInterval(timer);
  }, [inFlight, loadAll]);

  const settings = data?.settings || {};
  const kpis = data?.kpis || {};
  const readiness = data?.readiness || { items: [], can_generate: true };
  const nextSlot = data?.next_slot || {};

  const persistEnabled = async (enabled) => {
    if (enabled && !(data?.settings?.product_name || '').trim()) {
      setError('Сначала укажите продукт в настройках');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await customService.updateContentFactorySettings(id, { enabled });
      setMessage(enabled ? 'Завод включён — очередь пойдёт сама' : 'Завод на паузе');
      await loadAll();
    } catch (err) {
      setError(err.message || 'Не удалось сохранить');
    } finally {
      setBusy(false);
    }
  };

  const handleGenerate = async () => {
    if (data?.readiness && data.readiness.can_generate === false) {
      setError('Заполните бриф в настройках, затем генерируйте');
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const video = await customService.generateContentFactoryVideo(id);
      setMessage(`Ролик #${video.id}: ${CF_STATUS[video.status] || video.status}`);
      await loadAll();
      setOpenId(video.id);
    } catch (err) {
      setError(err.message || 'Не удалось сгенерировать');
    } finally {
      setBusy(false);
    }
  };

  const handleRetry = async (videoId) => {
    setBusy(true);
    setError(null);
    try {
      const video = await customService.retryContentFactoryVideo(id, videoId);
      setMessage(`Ролик #${video.id} снова в конвейере`);
      await loadAll();
      setOpenId(video.id);
    } catch (err) {
      setError(err.message || 'Не удалось повторить');
    } finally {
      setBusy(false);
    }
  };

  const handleSkip = async (videoId) => {
    setBusy(true);
    setError(null);
    try {
      await customService.skipContentFactoryVideo(id, videoId);
      setMessage('Ролик пропущен');
      await loadAll();
    } catch (err) {
      setError(err.message || 'Не удалось пропустить');
    } finally {
      setBusy(false);
    }
  };

  if (!data && !error) {
    return <div className="ubt-page"><p className="ubt-empty">Загрузка...</p></div>;
  }

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>ИИ Контент-завод</h1>
          <p>
            Идея, хук, уникализация и постинг идут сами. Вы задаёте бриф и площадки —
            {' '}
            <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY_SETTINGS(id)}>в настройках</Link>
            .
          </p>
        </div>
        <div className="cf-actions">
          <button type="button" className="acc-btn acc-btn--ghost" onClick={handleGenerate} disabled={busy}>
            Сгенерировать сейчас
          </button>
          <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY_ACCOUNTS(id)}>
            Аккаунты
          </Link>
        </div>
      </div>

      {message ? <p className="crm-flash">{message}</p> : null}
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}

      <div className="ubt-panel">
        <FeatureToggle
          title={settings.enabled ? 'Завод работает' : 'Завод выключен'}
          description={
            settings.sandbox_mode
              ? 'Песочница: ролики собираются и уникализируются, в соцсети не уходят.'
              : 'Боевой режим: публикация на прогретые аккаунты в окне и с лимитами.'
          }
          checked={Boolean(settings.enabled)}
          onChange={persistEnabled}
          disabled={busy}
        />
        {nextSlot.at ? (
          <p className="cf-muted">
            Следующий слот очереди: {formatWhen(nextSlot.at)}
            {nextSlot.in_window ? '' : ' · сейчас вне окна публикаций'}
            {nextSlot.sandbox_mode ? ' · песочница' : ''}
          </p>
        ) : null}
      </div>

      {(readiness.items || []).length ? (
        <div className="ubt-panel">
          <div className="ubt-panel-header">
            <div>
              <h2>Готовность</h2>
              <p>Чеклист перед автономным циклом.</p>
            </div>
          </div>
          <ul className="cf-readiness">
            {readiness.items.map((item) => (
              <li key={item.code} className={`cf-readiness__item cf-readiness__item--${item.level}`}>
                {item.text}
                {item.code === 'product' || item.code === 'audience' ? (
                  <>
                    {' '}
                    <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY_SETTINGS(id)}>Открыть настройки</Link>
                  </>
                ) : null}
                {item.code === 'accounts' ? (
                  <>
                    {' '}
                    <Link to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY_ACCOUNTS(id)}>Подключить</Link>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="ubt-kpi-grid">
        <div className="ubt-kpi"><strong>{kpis.posted ?? 0}</strong><span>Выложено</span></div>
        <div className="ubt-kpi"><strong>{kpis.in_flight ?? 0}</strong><span>В конвейере</span></div>
        <div className="ubt-kpi"><strong>{kpis.views ?? 0}</strong><span>Просмотры</span></div>
        <div className="ubt-kpi"><strong>{money(kpis.token_spend_usd)}</strong><span>Токены всего</span></div>
      </div>

      <div className="ubt-health-grid">
        <div className="ubt-kpi ubt-kpi--soft"><strong>{kpis.likes ?? 0}</strong><span>Лайки</span></div>
        <div className="ubt-kpi ubt-kpi--soft"><strong>{money(kpis.token_spend_month_usd)}</strong><span>Токены за месяц</span></div>
        <div className={`ubt-kpi ubt-kpi--soft${kpis.accounts_warming ? ' ubt-kpi--warn' : ''}`}>
          <strong>{kpis.accounts_warming ?? 0}</strong>
          <span>На прогреве</span>
        </div>
        <div className={`ubt-kpi ubt-kpi--soft${kpis.accounts_risk ? ' ubt-kpi--danger' : ' ubt-kpi--ok'}`}>
          <strong>{kpis.accounts_risk ?? 0}</strong>
          <span>Риск теневого бана</span>
        </div>
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <div>
            <h2>Ролики</h2>
            <p>Хук, раскадровка, уникализация и ссылки после публикации.</p>
          </div>
        </div>
        <div className="cf-chips">
          {CF_VIDEO_FILTERS.map((item) => (
            <button
              key={item.id || 'all'}
              type="button"
              className={`nc-chip${statusFilter === item.id ? ' is-on' : ''}`}
              onClick={() => setStatusFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {videos.length === 0 ? (
          <p className="ubt-empty">Пока пусто. Заполните бриф и нажмите «Сгенерировать сейчас».</p>
        ) : (
          <div className="cf-video-list">
            {videos.map((video) => {
              const open = openId === video.id;
              return (
                <div
                  key={video.id}
                  className="cf-video-card"
                  onClick={() => setOpenId(open ? null : video.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      setOpenId(open ? null : video.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="ubt-panel-header">
                    <div>
                      <h3>{video.hook || video.idea || `Ролик #${video.id}`}</h3>
                      <p>
                        {(video.extra?.media_kind === 'carousel' ? 'Карусель' : 'Видео')}
                        {video.extra?.soundtrack?.mode ? ` · звук: ${video.extra.soundtrack.mode}` : ''}
                        {' · '}{video.content_format} · {video.visual_style} · {video.duration_seconds}с · {video.aspect_ratio}
                      </p>
                    </div>
                    <span className={`cf-tag${video.status === 'failed' ? ' cf-tag--danger' : ['posted', 'sandbox'].includes(video.status) ? ' cf-tag--ok' : ''}`}>
                      {CF_STATUS[video.status] || video.status}
                    </span>
                  </div>
                  <div className="cf-meta">
                    <span>{formatWhen(video.created_at)}</span>
                    <span>{money(video.token_cost_usd)}</span>
                    <span>{video.views || 0} просмотров</span>
                    {(video.extra?.clip_plan || []).length ? (
                      <span>
                        Клипы {video.extra.clips_done || 0}/{video.extra.clip_plan.length}
                        {video.extra.stitched ? ' · склеено' : ''}
                      </span>
                    ) : null}
                    {(video.posts || []).map((post) => (
                      <span key={post.id}>{post.platform}: {CF_STATUS[post.status] || post.status}</span>
                    ))}
                  </div>
                  {open ? (
                    <div onClick={(event) => event.stopPropagation()}>
                      <p className="cf-muted">Сценарий</p>
                      <pre className="cf-script">{video.script || '—'}</pre>
                      {(video.storyboard || []).length ? (
                        <div>
                          <p className="cf-muted">Раскадровка</p>
                          {video.storyboard.map((scene, index) => (
                            <div className="cf-scene" key={`${video.id}-s-${index}`}>
                              <strong>{scene.duration ? `${scene.t ?? 0}–${(scene.t || 0) + scene.duration}с` : `${scene.t ?? index}с`}</strong>
                              <div>
                                <div>{scene.visual}</div>
                                <div className="cf-muted">{scene.voiceover}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {video.extra?.note ? <p className="cf-muted">{video.extra.note}</p> : null}
                      {(video.extra?.clip_plan || []).length ? (
                        <>
                          <div className="cf-bar" title={`Клипы ${video.extra.clips_done || 0}/${video.extra.clip_plan.length}`}>
                            <span style={{ width: `${Math.round(((video.extra.clips_done || 0) / video.extra.clip_plan.length) * 100)}%` }} />
                          </div>
                          <div className="cf-meta">
                            {video.extra.clip_plan.map((clip, index) => (
                              <span key={`${video.id}-clip-${index}`}>
                                {index + 1}/{video.extra.clip_plan.length}: {clip.status === 'rendered' ? 'готов' : clip.status === 'rendering' ? 'рендер' : clip.status || 'ждёт'} ({clip.duration}с)
                              </span>
                            ))}
                          </div>
                        </>
                      ) : null}
                      {video.preview ? <p className="cf-muted">Это раскадровка, не готовый файл.</p> : null}
                      {video.video_url ? (
                        <div className="cf-player">
                          <video src={video.video_url} poster={video.thumbnail_url || undefined} controls playsInline />
                          <p>
                            <a href={video.video_url} target="_blank" rel="noreferrer">Открыть файл</a>
                          </p>
                        </div>
                      ) : null}
                      {(video.posts || []).map((post) => (
                        <p key={`p-${post.id}`} className="cf-muted">
                          {post.platform}: {post.status === 'sandbox'
                            ? 'песочница — в сеть не публиковали'
                            : post.posted_url ? (
                              <a href={post.posted_url} target="_blank" rel="noreferrer">{post.posted_url}</a>
                            ) : (post.hold_reason || CF_STATUS[post.status] || post.status)}
                          {` · ${post.views} views / ${post.likes} likes`}
                        </p>
                      ))}
                      {video.last_error ? <p className="form-hint form-hint--error">{video.last_error}</p> : null}
                      {video.extra?.hold_reason && !video.last_error ? (
                        <p className="cf-muted">{video.extra.hold_reason}</p>
                      ) : null}
                      {['failed', 'skipped'].includes(video.status) ? (
                        <div className="cf-actions">
                          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => handleRetry(video.id)}>
                            Повторить
                          </button>
                        </div>
                      ) : null}
                      {['queued', 'ready', 'failed', 'rendering', 'posting'].includes(video.status) ? (
                        <div className="cf-actions">
                          <button type="button" className="acc-btn acc-btn--ghost" disabled={busy} onClick={() => handleSkip(video.id)}>
                            Пропустить
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="ubt-panel">
        <div className="ubt-panel-header">
          <h2>Расход токенов</h2>
        </div>
        {tokens.length === 0 ? (
          <p className="ubt-empty">Пока нет списаний.</p>
        ) : (
          <table className="ubt-table">
            <thead>
              <tr>
                <th>Когда</th>
                <th>Операция</th>
                <th>Модель</th>
                <th>Токены</th>
                <th>Стоимость</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((row) => (
                <tr key={row.id}>
                  <td>{formatWhen(row.created_at)}</td>
                  <td>{row.operation}</td>
                  <td>{row.model || row.provider}</td>
                  <td>{(row.prompt_tokens || 0) + (row.completion_tokens || 0)}</td>
                  <td>{money(row.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default CustomAutomationContentFactoryResultsPage;
