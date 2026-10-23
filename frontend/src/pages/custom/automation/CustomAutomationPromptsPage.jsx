import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import customService from '../../../services/customService';
import { NAVIGATION_ROUTES } from '../../../config/constants';
import CustomFileButton from '../../../components/custom/CustomFileButton';
import { parseShillingContent } from './activityLabels';
import '../../../styles/customNeuro.css';
import '../../../styles/customSolutionNav.css';

const EMPTY_BRIEF = {
  business: '',
  processes: '',
  funnel: '',
  product: '',
  terms: '',
  notes: '',
};

const previewOf = (prompt) => {
  if (!prompt) {
    return 'Навык ещё не собран';
  }
  if (prompt.prompt_type === 'shilling') {
    const pair = parseShillingContent(prompt.content);
    return `Вопрос: ${prompt.shilling_setup || pair.setup || '—'}`;
  }
  const text = String(prompt.content || '').replace(/\s+/g, ' ').trim();
  return text.length > 180 ? `${text.slice(0, 180)}…` : text;
};

const CustomAutomationPromptsPage = () => {
  const { id } = useParams();
  const [brief, setBrief] = useState(EMPTY_BRIEF);
  const [files, setFiles] = useState([]);
  const [knowledgeChars, setKnowledgeChars] = useState(0);
  const [generatedAt, setGeneratedAt] = useState(null);
  const [activities, setActivities] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [openKey, setOpenKey] = useState('');
  const [drafts, setDrafts] = useState({});
  const [complaints, setComplaints] = useState({});
  const [query, setQuery] = useState('');
  const [showArchive, setShowArchive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);

  const applyBrief = (payload) => {
    if (!payload) {
      return;
    }
    setBrief({
      business: payload.business || '',
      processes: payload.processes || '',
      funnel: payload.funnel || '',
      product: payload.product || '',
      terms: payload.terms || '',
      notes: payload.notes || '',
    });
    setFiles(payload.files || []);
    setKnowledgeChars(payload.knowledge_chars || 0);
    setGeneratedAt(payload.generated_at || null);
  };

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [base, list] = await Promise.all([
        customService.getSkillbase(id),
        customService.getPrompts(id),
      ]);
      applyBrief(base.brief);
      setActivities(base.activities || []);
      setPrompts(list.items || []);
      setError(null);
    } catch (err) {
      setError(err.message || 'Не удалось открыть скиллбейз');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const activeByType = useMemo(() => {
    const map = {};
    prompts.forEach((prompt) => {
      if (!prompt.is_active) {
        return;
      }
      const prev = map[prompt.prompt_type];
      if (!prev || prompt.version > prev.version) {
        map[prompt.prompt_type] = prompt;
      }
    });
    return map;
  }, [prompts]);

  const skills = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return activities.filter((item) => {
      if (!needle) {
        return true;
      }
      return `${item.title} ${item.where}`.toLowerCase().includes(needle);
    });
  }, [activities, query]);

  const setField = (key, value) => {
    setBrief((prev) => ({ ...prev, [key]: value }));
  };

  const saveBrief = async () => {
    const saved = await customService.saveSkillbase(id, brief);
    applyBrief(saved);
    return saved;
  };

  const run = async (key, action) => {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      await action();
    } catch (err) {
      setError(err.message || 'Не получилось');
    } finally {
      setBusy('');
    }
  };

  const openSkill = (item) => {
    setOpenKey((prev) => (prev === item.key ? '' : item.key));
    setDrafts((prev) => {
      if (prev[item.key]) {
        return prev;
      }
      if (item.storage === 'neuroblog') {
        return { ...prev, [item.key]: { content: item.module_text || '' } };
      }
      const prompt = activeByType[item.key];
      if (!prompt) {
        return prev;
      }
      if (prompt.prompt_type === 'shilling') {
        const pair = parseShillingContent(prompt.content);
        return {
          ...prev,
          [item.key]: {
            setup: prompt.shilling_setup || pair.setup || '',
            reply: prompt.shilling_reply || pair.reply || '',
          },
        };
      }
      return { ...prev, [item.key]: { content: prompt.content || '' } };
    });
  };

  return (
    <div className="nc-page">
      <div className="nc-card">
        <div className="nc-card-head">
          <div>
            <h2>Скиллбейз</h2>
            <p className="nc-intro">
              Один раз описываете бизнес, воронку и продукт. Модель собирает отдельный навык под каждую активность: комментарии, чаты, перехват, шиллинг, нейроблог. Текст можно поправить руками или сказать, что в активности не так.
            </p>
          </div>
        </div>
        {generatedAt ? <p className="nc-muted">Навыки собраны {generatedAt.replace('T', ' ').slice(0, 16)} UTC</p> : null}
      </div>

      {message ? <div className="nc-note">{message}</div> : null}
      {error ? <div className="nc-alert">{error}</div> : null}

      <div className="nc-card">
        <div className="nc-card-head"><h2>Основа проекта</h2></div>
        {isLoading ? <p className="nc-muted">Загрузка...</p> : (
          <>
            <div className="sb-grid">
              <label>
                Для какого бизнеса
                <textarea className="nc-area" rows={4} value={brief.business} onChange={(event) => setField('business', event.target.value)} placeholder="Кто клиент, чем компания зарабатывает, в каком рынке" />
              </label>
              <label>
                Конечный продукт
                <textarea className="nc-area" rows={4} value={brief.product} onChange={(event) => setField('product', event.target.value)} placeholder="Что продаём, какой результат получает человек" />
              </label>
              <label>
                Процессы
                <textarea className="nc-area" rows={4} value={brief.processes} onChange={(event) => setField('processes', event.target.value)} placeholder="Как идёт работа: заявка, созвон, счёт, запуск" />
              </label>
              <label>
                Воронка
                <textarea className="nc-area" rows={4} value={brief.funnel} onChange={(event) => setField('funnel', event.target.value)} placeholder="Откуда человек приходит и какой следующий шаг" />
              </label>
              <label>
                Условия и табу
                <textarea className="nc-area" rows={3} value={brief.terms} onChange={(event) => setField('terms', event.target.value)} placeholder="Цены, если их можно называть, запреты, чего обещать нельзя" />
              </label>
              <label>
                Заметки
                <textarea className="nc-area" rows={3} value={brief.notes} onChange={(event) => setField('notes', event.target.value)} placeholder="Тон, факты, типичные возражения" />
              </label>
            </div>
            <div className="nc-row">
              <CustomFileButton variant="ubt" accept=".txt,.md,.csv,.json,.html,.htm,.log,text/plain" busy={busy === 'file'} onFile={(file) => run('file', async () => {
                await saveBrief();
                const saved = await customService.uploadSkillbaseFile(id, file);
                applyBrief(saved);
                setMessage(`Файл ${file.name} добавлен в базу знаний`);
              })}>
                Добавить файл
              </CustomFileButton>
              <span className="nc-muted">
                {files.length ? `${files.length} файлов · ${knowledgeChars} знаков` : 'txt, md, csv, json, html'}
              </span>
            </div>
            {files.length ? (
              <div className="nc-list">
                {files.map((file) => (
                  <div key={file.name} className="nc-item">
                    <div>
                      <strong>{file.name}</strong>
                      <span>{file.chars} знаков</span>
                    </div>
                    <button type="button" className="acc-btn acc-btn--ghost" disabled={Boolean(busy)} onClick={() => run('file', async () => {
                      const saved = await customService.deleteSkillbaseFile(id, file.name);
                      applyBrief(saved);
                    })}>
                      Убрать
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="nc-row">
              <button type="button" className="acc-btn acc-btn--ghost" disabled={Boolean(busy)} onClick={() => run('save', async () => {
                await saveBrief();
                setMessage('Основа сохранена');
              })}>
                {busy === 'save' ? 'Сохраняем...' : 'Сохранить основу'}
              </button>
              <button type="button" className="acc-btn acc-btn--primary" disabled={Boolean(busy)} onClick={() => run('generate', async () => {
                await saveBrief();
                const result = await customService.generateSkillbase(id);
                applyBrief(result.brief);
                const list = await customService.getPrompts(id);
                setPrompts(list.items || []);
                const base = await customService.getSkillbase(id);
                setActivities(base.activities || []);
                setDrafts({});
                const problems = (result.errors || []).join(' ');
                setMessage(problems
                  ? `Обновлены: ${(result.updated || []).length}. ${problems}`
                  : `Собрано навыков: ${(result.updated || []).length}`);
              })}>
                {busy === 'generate' ? 'Собираем навыки...' : 'Собрать скиллбейз'}
              </button>
            </div>
          </>
        )}
      </div>

      <div className="nc-card">
        <div className="nc-card-head">
          <h2>Навыки</h2>
          <div className="nc-row">
            <input className="nc-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Найти активность" />
            <button type="button" className={`nc-chip ${showArchive ? 'is-on' : ''}`} onClick={() => setShowArchive((prev) => !prev)}>
              Прошлые версии
            </button>
          </div>
        </div>
        <div className="nc-list">
          {skills.map((item) => {
            const prompt = item.storage === 'neuroblog' ? null : activeByType[item.key];
            const archived = prompts.filter((row) => row.prompt_type === item.key && !row.is_active);
            const opened = openKey === item.key;
            const draft = drafts[item.key] || {};
            return (
              <div key={item.key} className="sb-skill">
                <button type="button" className={`nc-item ${opened ? 'is-on' : ''}`} onClick={() => openSkill(item)}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.where}</span>
                  </div>
                  <span>{prompt ? `v${prompt.version}` : item.storage === 'neuroblog' ? 'блог' : 'нет'}</span>
                </button>
                {opened ? (
                  <div className="sb-editor">
                    {!prompt && item.storage !== 'neuroblog' ? (
                      <p className="nc-muted">Навык появится после сборки скиллбейза.</p>
                    ) : item.storage === 'neuroblog' || prompt.prompt_type !== 'shilling' ? (
                      <textarea
                        className="nc-area"
                        rows={12}
                        value={draft.content || ''}
                        onChange={(event) => setDrafts((prev) => ({ ...prev, [item.key]: { ...draft, content: event.target.value } }))}
                      />
                    ) : (
                      <>
                        <label>
                          Вопрос
                          <textarea className="nc-area" rows={3} value={draft.setup || ''} onChange={(event) => setDrafts((prev) => ({ ...prev, [item.key]: { ...draft, setup: event.target.value } }))} />
                        </label>
                        <label>
                          Ответ
                          <textarea className="nc-area" rows={3} value={draft.reply || ''} onChange={(event) => setDrafts((prev) => ({ ...prev, [item.key]: { ...draft, reply: event.target.value } }))} />
                        </label>
                      </>
                    )}
                    {(item.variables || []).length ? (
                      <p className="nc-muted">Не удаляйте переменные: {item.variables.map((name) => `{${name}}`).join(', ')}</p>
                    ) : null}
                    <div className="nc-row">
                      <button type="button" className="acc-btn acc-btn--primary" disabled={Boolean(busy)} onClick={() => run(`save-${item.key}`, async () => {
                        if (item.storage === 'neuroblog') {
                          const saved = await customService.saveNeuroblogSkill(id, draft.content || '');
                          setActivities((prev) => prev.map((row) => (row.key === 'neuroblog' ? { ...row, module_text: saved.module_text } : row)));
                        } else if (prompt?.prompt_type === 'shilling') {
                          await customService.updatePrompt(id, prompt.id, { shilling_setup: draft.setup || '', shilling_reply: draft.reply || '' });
                          const list = await customService.getPrompts(id);
                          setPrompts(list.items || []);
                        } else if (prompt) {
                          await customService.updatePrompt(id, prompt.id, { content: draft.content || '' });
                          const list = await customService.getPrompts(id);
                          setPrompts(list.items || []);
                        }
                        setMessage(`${item.title}: сохранено`);
                      })}>
                        Сохранить правку
                      </button>
                      {prompt ? (
                        <Link className="acc-btn acc-btn--ghost" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPT_EDIT(id, prompt.id)}>Проверить на примере</Link>
                      ) : null}
                    </div>
                    <label>
                      Что не так в этой активности
                      <textarea
                        className="nc-area"
                        rows={3}
                        value={complaints[item.key] || ''}
                        onChange={(event) => setComplaints((prev) => ({ ...prev, [item.key]: event.target.value }))}
                        placeholder="Например: слишком продаёт в первом комментарии, называет цену, которой нет, звучит как бот"
                      />
                    </label>
                    <button type="button" className="acc-btn acc-btn--ghost" disabled={Boolean(busy)} onClick={() => run(`fix-${item.key}`, async () => {
                      if (item.storage === 'neuroblog') {
                        const saved = await customService.reviseNeuroblogSkill(id, complaints[item.key] || '');
                        setActivities((prev) => prev.map((row) => (row.key === 'neuroblog' ? { ...row, module_text: saved.module_text } : row)));
                        setDrafts((prev) => ({ ...prev, [item.key]: { content: saved.module_text || '' } }));
                      } else if (prompt) {
                        const saved = await customService.revisePrompt(id, prompt.id, complaints[item.key] || '');
                        const list = await customService.getPrompts(id);
                        setPrompts(list.items || []);
                        setDrafts((prev) => ({ ...prev, [item.key]: prompt.prompt_type === 'shilling'
                          ? { setup: saved.shilling_setup || '', reply: saved.shilling_reply || '' }
                          : { content: saved.content || '' } }));
                      }
                      setMessage(`${item.title}: модель внесла правку`);
                    })}>
                      {busy === `fix-${item.key}` ? 'Правим...' : 'Поправить моделью'}
                    </button>
                    {showArchive && archived.length ? (
                      <div className="nc-list">
                        {archived.slice(0, 6).map((row) => (
                          <Link key={row.id} className="nc-item" to={NAVIGATION_ROUTES.CUSTOM_AUTOMATION_PROMPT_EDIT(id, row.id)}>
                            <div>
                              <strong>Версия {row.version}</strong>
                              <span>{row.is_active ? 'активна' : 'архив'}</span>
                            </div>
                          </Link>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="sb-preview">{item.storage === 'neuroblog' ? (item.module_text || 'Памятка блогу ещё пустая') : previewOf(prompt)}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default CustomAutomationPromptsPage;
