/**
 * Main state management hook for the visual website constructor.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { toRendererStyles } from '../utils/styleUtils';
import { getDefaultBlockContent } from '../utils/blockDefaults';
import {
  fetchWebsiteDetail,
  updateWebsite,
  updateBlock,
  createBlock,
  deleteBlock,
  duplicateBlockApi,
  reorderBlocksApi,
  editBlockWithPromptApi,
  publishWebsite,
  unpublishWebsite,
  deleteWebsite,
} from '../utils/api';

const AUTOSAVE_MS = 5000;

export function useConstructor(websiteId) {
  const [website, setWebsite] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [globalStyles, setGlobalStyles] = useState({});
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveStatus, setSaveStatus] = useState('saved'); // saved | saving | dirty | error
  const [aiLoading, setAiLoading] = useState(false);

  const dirtyRef = useRef(false);
  const saveTimerRef = useRef(null);
  const blocksRef = useRef(blocks);
  const websiteRef = useRef(website);
  const globalStylesRef = useRef(globalStyles);

  blocksRef.current = blocks;
  websiteRef.current = website;
  globalStylesRef.current = globalStyles;

  const load = useCallback(async () => {
    if (!websiteId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchWebsiteDetail(websiteId);
      const sorted = [...(data.blocks || [])].sort((a, b) => a.order - b.order);
      setWebsite(data);
      setBlocks(sorted);
      setGlobalStyles(toRendererStyles(data.custom_styles || {}));
      if (sorted.length && !selectedBlockId) {
        setSelectedBlockId(sorted[0].id);
      }
      dirtyRef.current = false;
      setSaveStatus('saved');
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : detail?.message || 'Не удалось загрузить сайт');
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    load();
  }, [load]);

  const markDirty = useCallback(() => {
    dirtyRef.current = true;
    setSaveStatus('dirty');
  }, []);

  const persist = useCallback(async () => {
    if (!dirtyRef.current || !websiteId) return;
    setSaveStatus('saving');
    try {
      const w = websiteRef.current;
      const gs = globalStylesRef.current;
      const blks = blocksRef.current;

      if (w) {
        await updateWebsite(websiteId, {
          title: w.title,
          custom_styles: gs,
        });
      }

      await Promise.all(
        blks.map((b) =>
          updateBlock(websiteId, b.id, {
            content: b.content,
            styles: b.styles,
            order: b.order,
            is_visible: b.is_visible !== false,
          })
        )
      );

      dirtyRef.current = false;
      setSaveStatus('saved');
    } catch (err) {
      console.error('Autosave failed:', err);
      setSaveStatus('error');
    }
  }, [websiteId]);

  const scheduleSave = useCallback(() => {
    markDirty();
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      persist();
    }, AUTOSAVE_MS);
  }, [markDirty, persist]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  const saveNow = useCallback(async () => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    dirtyRef.current = true;
    await persist();
  }, [persist]);

  const updateGlobalStyles = useCallback(
    (patch) => {
      setGlobalStyles((prev) => {
        const next = { ...prev, ...patch };
        globalStylesRef.current = next;
        return next;
      });
      scheduleSave();
    },
    [scheduleSave]
  );

  const updateBlockContent = useCallback(
    (blockId, contentPatch) => {
      setBlocks((prev) =>
        prev.map((b) =>
          b.id === blockId ? { ...b, content: { ...b.content, ...contentPatch } } : b
        )
      );
      scheduleSave();
    },
    [scheduleSave]
  );

  const updateBlockStyles = useCallback(
    (blockId, stylesPatch) => {
      setBlocks((prev) =>
        prev.map((b) =>
          b.id === blockId ? { ...b, styles: { ...(b.styles || {}), ...stylesPatch } } : b
        )
      );
      scheduleSave();
    },
    [scheduleSave]
  );

  const reorderBlocks = useCallback(
    (newOrderedBlocks) => {
      const withOrder = newOrderedBlocks.map((b, idx) => ({ ...b, order: idx }));
      setBlocks(withOrder);
      blocksRef.current = withOrder;
      markDirty();
      reorderBlocksApi(
        websiteId,
        withOrder.map((b) => ({ block_id: b.id, order: b.order }))
      ).catch(console.error);
      scheduleSave();
    },
    [websiteId, markDirty, scheduleSave]
  );

  const addBlock = useCallback(
    async (type) => {
      const order = blocks.length;
      const created = await createBlock(websiteId, {
        type,
        order,
        content: getDefaultBlockContent(type),
        styles: {},
        is_visible: true,
      });
      setBlocks((prev) => [...prev, created].sort((a, b) => a.order - b.order));
      setSelectedBlockId(created.id);
      scheduleSave();
      return created;
    },
    [websiteId, blocks.length, scheduleSave]
  );

  const removeBlock = useCallback(
    async (blockId) => {
      await deleteBlock(websiteId, blockId);
      setBlocks((prev) => {
        const next = prev.filter((b) => b.id !== blockId);
        if (selectedBlockId === blockId && next.length) {
          setSelectedBlockId(next[0].id);
        }
        return next;
      });
      scheduleSave();
    },
    [websiteId, selectedBlockId, scheduleSave]
  );

  const duplicateBlock = useCallback(
    async (blockId) => {
      const created = await duplicateBlockApi(websiteId, blockId);
      setBlocks((prev) => [...prev, created].sort((a, b) => a.order - b.order));
      setSelectedBlockId(created.id);
      scheduleSave();
      return created;
    },
    [websiteId, scheduleSave]
  );

  const applyAiPrompt = useCallback(
    async (blockId, prompt, images = []) => {
      setAiLoading(true);
      try {
        const result = await editBlockWithPromptApi(websiteId, blockId, prompt, images);
        setBlocks((prev) =>
          prev.map((b) =>
            b.id === blockId
              ? { ...b, content: result.content, styles: result.styles || b.styles }
              : b
          )
        );
        scheduleSave();
        return result;
      } finally {
        setAiLoading(false);
      }
    },
    [websiteId, scheduleSave]
  );

  const handlePublish = useCallback(async () => {
    await saveNow();
    const data = await publishWebsite(websiteId);
    setWebsite((w) => ({ ...w, ...data }));
    return data;
  }, [websiteId, saveNow]);

  const handleUnpublish = useCallback(async () => {
    const data = await unpublishWebsite(websiteId);
    setWebsite((w) => ({ ...w, ...data }));
    return data;
  }, [websiteId]);

  const handleDeleteWebsite = useCallback(async () => {
    await saveNow();
    await deleteWebsite(websiteId);
  }, [websiteId, saveNow]);

  const selectedBlock = blocks.find((b) => b.id === selectedBlockId) || null;

  const schema = website
    ? {
        id: website.id,
        slug: website.slug,
        title: website.title,
        meta_description: website.meta_description,
        status: website.status,
        styles: globalStyles,
        blocks,
      }
    : null;

  return {
    website,
    blocks,
    globalStyles,
    selectedBlockId,
    selectedBlock,
    schema,
    loading,
    error,
    saveStatus,
    aiLoading,
    setSelectedBlockId,
    load,
    saveNow,
    updateGlobalStyles,
    updateBlockContent,
    updateBlockStyles,
    reorderBlocks,
    addBlock,
    removeBlock,
    duplicateBlock,
    applyAiPrompt,
    publish: handlePublish,
    unpublish: handleUnpublish,
    deleteWebsite: handleDeleteWebsite,
  };
}

export default useConstructor;
