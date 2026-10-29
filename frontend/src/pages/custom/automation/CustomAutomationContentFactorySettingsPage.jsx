import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import CustomSelect from '../../../components/CustomSelect';
import FeatureToggle from '../../../components/FeatureToggle';
import UbtUnsaved from '../../../components/custom/UbtUnsaved';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import {
  CF_ASPECTS,
  CF_FORMATS,
  CF_STYLES,
  CF_TONES,
  CF_MUSIC_MODES,
  CF_VIDEO_MODELS,
  toggleChip,
} from './contentFactoryLabels';
import '../../../styles/customAccountManager.css';
import '../../../styles/projectSettingsPage.css';
import '../../../styles/customSolutionNav.css';
import '../../../styles/customNeuro.css';
import '../../../styles/customContentFactory.css';

const EMPTY = {
  enabled: false,
  sandbox_mode: true,
  product_name: '',
  product_description: '',
  product_url: '',
  cta_text: '',
  audience: '',
  niche: '',
  content_formats: ['educational', 'storytelling'],
  visual_styles: ['realism'],
  language: 'ru',
  tone: 'expert_friendly',
  brand_voice: '',
  forbidden_topics: '',
  videos_per_day: 1,
  duration_min: 30,
  duration_max: 45,
  aspect_ratio: '9:16',
  posting_window_start: '09:00',
  posting_window_end: '21:00',
  timezone: 'Europe/Moscow',
  idea_model: 'deepseek-chat',
  script_model: 'deepseek-chat',
  video_model: 'kling',
  tts_model: '',
  carousel_share: 0,
  image_provider: 'chatgpt',
  image_model: 'gpt-image-2.5-flare',
  xai_api_key: '',
  openai_api_key: '',
  kling_api_key: '',
  grok_bot_name: 'Карусели завода',
  grok_bot_brief: '',
  xai_api_key: '',
  openai_api_key: '',
  kling_api_key: '',
  runway_api_key: '',
  luma_api_key: '',
  elevenlabs_api_key: '',
  warmup_days: 7,
  warmup_actions_per_day: 8,
  max_posts_per_account_per_day: 2,
  stagger_min_minutes: 25,
  uniqualize_enabled: true,
  unique_per_platform: true,
  hook_required: true,
  avoid_exact_hour: true,
  shadowban_pause_zero_views: true,
  shadowban_zero_views_threshold: 3,
};

const CustomAutomationContentFactorySettingsPage = () => {
  const { id } = useParams();
  const [form, setForm] = useState(EMPTY);
  const [meta, setMeta] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [snapshot, setSnapshot] = useState('');
  const [botBusy, setBotBusy] = useState(false);
    openai_api_key: '',
    kling_api_key: '',
    runway_api_key: '',
    luma_api_key: '',
    elevenlabs_api_key: '',
    xai_api_key: '',
  });

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await customService.getContentFactorySettings(id);
      const next = { ...EMPTY, ...data, openai_api_key: '', kling_api_key: '', runway_api_key: '', luma_api_key: '', elevenlabs_api_key: '', xai_api_key: '' };
      setForm(next);
      setSnapshot(fingerprint(next));
      setMeta(data);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось загрузить настройки');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const setField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    const payload = { ...form };
    if (payload.enabled && !(payload.product_name || '').trim()) {
      setError('Укажите продукт, прежде чем включать завод');
      setIsSaving(false);
      return;
    }
    ['openai_api_key', 'kling_api_key', 'runway_api_key', 'luma_api_key', 'elevenlabs_api_key', 'xai_api_key'].forEach((key) => {
      if (!payload[key]) {
        delete payload[key];
      }
    });
    try {
      const data = await customService.updateContentFactorySettings(id, payload);
      setMeta(data);
      const next = {
        ...form,
        ...data,
        openai_api_key: '',
        kling_api_key: '',
        runway_api_key: '',
        luma_api_key: '',
        elevenlabs_api_key: '',
        xai_api_key: '',
      };
      setForm(next);
      setSnapshot(fingerprint(next));
      setSuccess('Настройки контент-завода сохранены');
    } catch (err) {
      setError(err.message || 'Не удалось сохранить');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="ubt-page"><p className="ubt-empty">Загрузка...</p></div>;
  }

  return (
    <div className="ubt-page">
      <div className="ubt-hero">
        <div>
          <h1>Настройки контент-завода</h1>
          <p>Бриф, частота, модели и антифрод. Сами ролики завод делает без ручных сценариев.</p>
        </div>
        <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_CONTENT_FACTORY(id)}>
          Результаты
        </Link>
      </div>
      {error ? <p className="crm-flash crm-flash--error">{error}</p> : null}
      {success ? <p className="crm-flash">{success}</p> : null}
      <UbtUnsaved dirty={Boolean(snapshot) && fingerprint(form) !== snapshot} />

      <form onSubmit={handleSave}>
        <div className="ubt-panel">
          <FeatureToggle
            title="Завод включён"
            description="Фоновый цикл: идея → сценарий с хуком → генерация → уникализация → пост."
            checked={Boolean(form.enabled)}
            onChange={(checked) => setField('enabled', checked)}
          />
          <FeatureToggle
            title="Песочница"
            description="Собираем и уникализируем ролики, но не публикуем в соцсети. Выключите, когда аккаунты прогреты."
            checked={Boolean(form.sandbox_mode)}
            onChange={(checked) => {
              if (!checked && !window.confirm('Выключаем песочницу: ролики поедут в соцсети, если завод включён и аккаунты прогреты. Продолжить?')) {
                return;
              }
              setField('sandbox_mode', checked);
            }}
          />
        </div>

        <div className="ubt-panel">
          <div className="ubt-panel-header">
            <div>
              <h2>Бриф</h2>
              <p>Это всё, что нужно от вас. Дальше завод крутит идеи сам.</p>
            </div>
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-product">Продукт / бренд</label>
              <input id="cf-product" value={form.product_name} onChange={(e) => setField('product_name', e.target.value)} required />
            </div>
            <div className="form-group">
              <label htmlFor="cf-niche">Ниша</label>
              <input id="cf-niche" value={form.niche} onChange={(e) => setField('niche', e.target.value)} placeholder="SaaS, фитнес, EdTech..." />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="cf-desc">Что продаём в конце воронки</label>
            <textarea id="cf-desc" value={form.product_description} onChange={(e) => setField('product_description', e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="cf-audience">Кого привлекаем</label>
            <textarea id="cf-audience" value={form.audience} onChange={(e) => setField('audience', e.target.value)} />
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-url">Ссылка / CTA URL</label>
              <input id="cf-url" value={form.product_url} onChange={(e) => setField('product_url', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-cta">Призыв в конце ролика</label>
              <input id="cf-cta" value={form.cta_text} onChange={(e) => setField('cta_text', e.target.value)} />
            </div>
          </div>
          <div className="form-group">
            <span>Формат роликов</span>
            <div className="cf-chips">
              {CF_FORMATS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`nc-chip${(form.content_formats || []).includes(item.id) ? ' is-on' : ''}`}
                  onClick={() => setField('content_formats', toggleChip(form.content_formats, item.id))}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="form-group">
            <span>Визуальный стиль</span>
            <div className="cf-chips">
              {CF_STYLES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`nc-chip${(form.visual_styles || []).includes(item.id) ? ' is-on' : ''}`}
                  onClick={() => setField('visual_styles', toggleChip(form.visual_styles, item.id))}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-tone">Тон</label>
              <CustomSelect id="cf-tone" value={form.tone} options={CF_TONES} onChange={(e) => setField('tone', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-lang">Язык</label>
              <input id="cf-lang" value={form.language} onChange={(e) => setField('language', e.target.value)} />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="cf-voice">Голос бренда</label>
            <textarea id="cf-voice" value={form.brand_voice} onChange={(e) => setField('brand_voice', e.target.value)} />
          </div>
          <div className="form-group">
            <label htmlFor="cf-forbid">Запретные темы</label>
            <textarea id="cf-forbid" value={form.forbidden_topics} onChange={(e) => setField('forbidden_topics', e.target.value)} placeholder="Гарантии дохода, фейковые отзывы..." />
          </div>
        </div>

        <div className="ubt-panel">
          <div className="ubt-panel-header">
            <div>
              <h2>Расписание и кадр</h2>
              <p>Kling отдаёт до 8 секунд на клип. Завод режет ролик на несколько кусков и склеивает до выбранной длительности.</p>
            </div>
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-vpd">Роликов в сутки</label>
              <input id="cf-vpd" type="number" min="0.2" max="8" step="0.5" value={form.videos_per_day} onChange={(e) => setField('videos_per_day', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-aspect">Кадр</label>
              <CustomSelect id="cf-aspect" value={form.aspect_ratio} options={CF_ASPECTS} onChange={(e) => setField('aspect_ratio', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-dmin">Длительность от, сек</label>
              <input id="cf-dmin" type="number" min="8" max="90" value={form.duration_min} onChange={(e) => setField('duration_min', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-dmax">Длительность до, сек</label>
              <input id="cf-dmax" type="number" min="8" max="120" value={form.duration_max} onChange={(e) => setField('duration_max', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-ws">Окно публикаций с</label>
              <input id="cf-ws" type="time" value={form.posting_window_start} onChange={(e) => setField('posting_window_start', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-we">Окно публикаций до</label>
              <input id="cf-we" type="time" value={form.posting_window_end} onChange={(e) => setField('posting_window_end', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-tz">Часовой пояс</label>
              <input id="cf-tz" value={form.timezone} onChange={(e) => setField('timezone', e.target.value)} />
            </div>
          </div>
        </div>

        <div className="ubt-panel">
          <div className="ubt-panel-header">
            <div>
              <h2>Модели и ключи</h2>
              <p>Без ключа видеозавода ролики собираются как раскадровка. Ключи не показываются обратно.</p>
            </div>
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-imodel">Модель идей / сценария</label>
              <input id="cf-imodel" value={form.script_model} onChange={(e) => setField('script_model', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-vmodel">Видеомодель</label>
              <CustomSelect id="cf-vmodel" value={form.video_model} options={CF_VIDEO_MODELS} onChange={(e) => setField('video_model', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-okey">OpenAI / совместимый ключ {meta.openai_api_key_set ? '(сохранён)' : ''}</label>
              <input id="cf-okey" type="password" value={form.openai_api_key} onChange={(e) => setField('openai_api_key', e.target.value)} autoComplete="off" placeholder="оставь пустым, чтобы не менять" />
            </div>
            <div className="form-group">
              <label htmlFor="cf-kkey">Kling {meta.kling_api_key_set ? '(сохранён)' : ''}</label>
              <input id="cf-kkey" type="password" value={form.kling_api_key} onChange={(e) => setField('kling_api_key', e.target.value)} autoComplete="off" />
            </div>
            <div className="form-group">
              <label htmlFor="cf-rkey">Runway {meta.runway_api_key_set ? '(сохранён)' : ''}</label>
              <input id="cf-rkey" type="password" value={form.runway_api_key} onChange={(e) => setField('runway_api_key', e.target.value)} autoComplete="off" />
            </div>
            <div className="form-group">
              <label htmlFor="cf-lkey">Luma {meta.luma_api_key_set ? '(сохранён)' : ''}</label>
              <input id="cf-lkey" type="password" value={form.luma_api_key} onChange={(e) => setField('luma_api_key', e.target.value)} autoComplete="off" />
            </div>
          </div>
          <div className="form-group" style={{ marginTop: 16 }}>
            <label htmlFor="cf-mix">Видео / фото-карусели: {100 - Number(form.carousel_share || 0)}% видео · {Number(form.carousel_share || 0)}% карусели</label>
            <input
              id="cf-mix"
            <label htmlFor="cf-mix">Фото-карусели {Number(form.carousel_share ?? 100)}% · обычное видео {100 - Number(form.carousel_share ?? 100)}%</label>
            <input
              id="cf-mix"
              type="range"
              min="0"
              max="100"
              value={form.carousel_share ?? 100}
              onChange={(e) => setField('carousel_share', Number(e.target.value))}
            />
            <p className="form-hint">
              Основной формат — фото-карусель. Instagram, TikTok и Pinterest публикуют кадры.
              YouTube Shorts и VK Клипы карусель не принимают: туда уходит тот же набор как вертикальное слайд-шоу.
            </p>
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-music">Музыка</label>
              <CustomSelect id="cf-music" value={form.music_mode || 'voice_bed'} options={CF_MUSIC_MODES} onChange={(e) => setField('music_mode', e.target.value)} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-mvol">Громкость подложки, %</label>
              <input id="cf-mvol" type="number" min="0" max="100" value={form.music_volume ?? 32} onChange={(e) => setField('music_volume', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-voice">Голос ElevenLabs</label>
              <input id="cf-voice" value={form.tts_voice || ''} onChange={(e) => setField('tts_voice', e.target.value)} placeholder="пусто — Rachel" />
            </div>
            <div className="form-group">
              <label htmlFor="cf-tts">Модель озвучки</label>
              <input id="cf-tts" value={form.tts_model || ''} onChange={(e) => setField('tts_model', e.target.value)} placeholder="eleven_multilingual_v2" />
            </div>
            <div className="form-group">
              <label htmlFor="cf-ekey">ElevenLabs {meta.elevenlabs_api_key_set ? '(сохранён)' : ''}</label>
              <input id="cf-ekey" type="password" value={form.elevenlabs_api_key || ''} onChange={(e) => setField('elevenlabs_api_key', e.target.value)} autoComplete="off" placeholder="для голоса за кадром" />
            </div>
          </div>
          <p className="form-hint">
            Дорожка кладётся на слайд-шоу и на склеенный ролик до уникализации.
            Фото-карусели Instagram, TikTok и Pinterest публикуются без нашего звука: у этих форматов музыка площадки.
            Без ключа ElevenLabs остаётся своя инструментальная подложка, не чужой трек.
          </p>
              <CustomSelect
                id="cf-imodel2"
                value={form.image_provider || 'chatgpt'}
                options={[
                  { value: 'chatgpt', label: 'ChatGPT' },
                  { value: 'grok', label: 'Grok' },
                ]}
                onChange={(e) => setField('image_provider', e.target.value)}
                  { value: 'grok', label: 'Grok Bot — пачка кадров' },
                ]}
                onChange={(e) => {
                  const value = e.target.value;
                  setForm((current) => ({
                    ...current,
                    image_provider: value,
                    image_model: value === 'grok' && !String(current.image_model || '').includes('grok')
                      ? 'grok-imagine-image-2.0'
                      : current.image_model,
                  }));
                }}
              <label htmlFor="cf-islug">Имя модели</label>
              <input id="cf-islug" value={form.image_model || ''} onChange={(e) => setField('image_model', e.target.value)} placeholder="gpt-image-2.5-flare или grok-imagine-image-2.0" />
            </div>
            <div className="form-group">
              <label htmlFor="cf-xkey">Grok / xAI {meta.xai_api_key_set ? '(сохранён)' : ''}</label>
              <input id="cf-xkey" type="password" value={form.xai_api_key} onChange={(e) => setField('xai_api_key', e.target.value)} autoComplete="off" placeholder="для каруселей Grok" />
            </div>
          </div>
        </div>

        <div className="ubt-panel">
          <div className="ubt-panel" style={{ marginTop: 16 }}>
            <div className="ubt-panel-header">
              <div>
                <h2>Бот каруселей Grok</h2>
                <p>
                  Один бот на завод{meta.grok_bot_id ? `, ${meta.grok_bot_id}` : ''}.
                  {meta.grok_bot_has_thread ? ' Он уже помнит прошлую карусель и в следующий раз возьмёт другую тему.' : ' Первый пост — это первое сообщение: стиль, компания, «выбери тему и сделай карусель».'}
                  Кадры он рисует сам, отдельный запрос на каждую картинку мы не шлём.
                </p>
              </div>
            </div>
            <div className="cf-form-grid">
              <div className="form-group">
                <label htmlFor="cf-bot-name">Имя бота</label>
                <input id="cf-bot-name" value={form.grok_bot_name || ''} onChange={(e) => setField('grok_bot_name', e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="cf-bot-brief">Постоянный бриф</label>
              <textarea
                id="cf-bot-brief"
                rows={4}
                value={form.grok_bot_brief || ''}
                onChange={(e) => setField('grok_bot_brief', e.target.value)}
                placeholder="Сюда стиль и дизайн компании. Пусто — живая вертикальная карусель без текста на кадрах."
              />
            </div>
            <p className="form-hint">
              Как в ручном тесте: одно сообщение боту, он сам выбирает тематику и сценарий и возвращает 6–7 кадров в порядке свайпа.
              Следующий пост — «сделай новую карусель с другой темой», тот же бот. В модели картинок выберите Grok Bot.
            </p>
            <button
              type="button"
              className="btn btn-outline"
              disabled={botBusy}
              onClick={async () => {
                setBotBusy(true);
                setError(null);
                try {
                  const result = await customService.saveContentFactoryGrokBot(id, {
                    grok_bot_name: form.grok_bot_name,
                    grok_bot_brief: form.grok_bot_brief,
                    ...(form.xai_api_key ? { xai_api_key: form.xai_api_key } : {}),
                  });
                  setSuccess(result.detail || 'Бот сохранён');
                  setMeta((current) => ({ ...current, grok_bot_id: result.bot_id, grok_bot_name: result.grok_bot_name }));
                } catch (err) {
                  setError(err.message || 'Не удалось сохранить бота');
                } finally {
                  setBotBusy(false);
                }
              }}
            >
              {botBusy ? 'Проверяем Grok...' : 'Сохранить бота и проверить ключ'}
            </button>
          </div>
          <div className="ubt-panel-header">
            <div>
              <h2>Антифрод и прогрев</h2>
              <p>Холодный пост с нового аккаунта — быстрый теневой бан. Завод этого не делает.</p>
            </div>
          </div>
          <div className="cf-form-grid">
            <div className="form-group">
              <label htmlFor="cf-wd">Дней прогрева</label>
              <input id="cf-wd" type="number" min="1" max="30" value={form.warmup_days} onChange={(e) => setField('warmup_days', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-wa">Действий прогрева в день</label>
              <input id="cf-wa" type="number" min="2" max="20" value={form.warmup_actions_per_day} onChange={(e) => setField('warmup_actions_per_day', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-mpd">Макс. постов с аккаунта в день</label>
              <input id="cf-mpd" type="number" min="1" max="8" value={form.max_posts_per_account_per_day} onChange={(e) => setField('max_posts_per_account_per_day', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-stagger">Пауза между постами, мин</label>
              <input id="cf-stagger" type="number" min="5" max="240" value={form.stagger_min_minutes} onChange={(e) => setField('stagger_min_minutes', Number(e.target.value))} />
            </div>
            <div className="form-group">
              <label htmlFor="cf-zero">Пауза после N постов с 0 просмотров</label>
              <input id="cf-zero" type="number" min="2" max="10" value={form.shadowban_zero_views_threshold} onChange={(e) => setField('shadowban_zero_views_threshold', Number(e.target.value))} />
            </div>
          </div>
          <FeatureToggle
            title="Уникализация перед постом"
            description="Скорость, кроп, цвет, сдвиг кадра и отдельный caption на каждую площадку."
            checked={Boolean(form.uniqualize_enabled)}
            onChange={(checked) => setField('uniqualize_enabled', checked)}
          />
          <FeatureToggle
            title="Отдельный вариант на каждую сеть"
            description="Один и тот же файл на YouTube и TikTok — палево. Завод делает разные отпечатки."
            checked={Boolean(form.unique_per_platform)}
            onChange={(checked) => setField('unique_per_platform', checked)}
          />
          <FeatureToggle
            title="Хук обязателен"
            description="Первые секунды — стоп-кадр, вопрос или цифра. Без хука ролик не едет в пост."
            checked={Boolean(form.hook_required)}
            onChange={(checked) => setField('hook_required', checked)}
          />
          <FeatureToggle
            title="Не постить ровно в :00"
            description="Площадки палят сетки, которые выкладываются минута в минуту."
            checked={Boolean(form.avoid_exact_hour)}
            onChange={(checked) => setField('avoid_exact_hour', checked)}
          />
          <FeatureToggle
            title="Пауза при нулевых просмотрах"
            description="Если несколько роликов подряд без просмотров — аккаунт уходит в риск теневого бана."
            checked={Boolean(form.shadowban_pause_zero_views)}
            onChange={(checked) => setField('shadowban_pause_zero_views', checked)}
          />
        </div>

        <div className="settings-actions">
          <button type="submit" className="btn btn-black" disabled={isSaving}>
            {isSaving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default CustomAutomationContentFactorySettingsPage;
