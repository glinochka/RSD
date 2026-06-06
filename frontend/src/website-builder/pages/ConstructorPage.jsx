/**
 * Visual Website Constructor Page (Stage 4)
 */
import React, { useState, useMemo, useEffect } from 'react';
import axios from 'axios';
import { API_ROUTES } from '../../config/constants';
import { getAuthHeaders } from '../../utils/authToken';
import { useParams, useNavigate } from 'react-router-dom';
import ProtectedRoute from '../../components/ProtectedRoute';
import { NAVIGATION_ROUTES } from '../../config/constants';
import { useConstructor } from '../hooks/useConstructor';
import WebsiteRenderer from '../components/WebsiteRenderer';
import AgentWidget from '../components/AgentWidget';
import QuickContactButtons from '../components/QuickContactButtons';
import { WebsiteAgentProvider } from '../context/WebsiteAgentContext';
import DeviceSwitcher, { DEVICES } from '../components/DeviceSwitcher';
import {
  ConstructorTopBar,
  BlockListPanel,
  BlockSettingsPanel,
  AiPromptPanel,
  AddBlockModal,
  DeleteBlockDialog,
  SEOMetaPanel,
} from '../components/constructor';
import { buildPlaceholderVars } from '../utils/placeholders';
import '../styles/constructor.css';

const ConstructorPageContent = () => {
  const { websiteId } = useParams();
  const navigate = useNavigate();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [blockToDelete, setBlockToDelete] = useState(null);
  const [currentDevice, setCurrentDevice] = useState('desktop');
  const [actionError, setActionError] = useState(null);
  const [rightPanelTab, setRightPanelTab] = useState('settings');
  const [deletingWebsite, setDeletingWebsite] = useState(false);
  const [aiFeedback, setAiFeedback] = useState(null);

  const [agentData, setAgentData] = useState(null);

  const {
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
    saveNow,
    updateGlobalStyles,
    updateBlockContent,
    updateBlockStyles,
    reorderBlocks,
    addBlock,
    removeBlock,
    duplicateBlock,
    applyAiPrompt,
    publish,
    unpublish,
    deleteWebsite,
  } = useConstructor(websiteId);

  const placeholderVars = useMemo(
    () => ({
      ...buildPlaceholderVars(website || {}),
      phone: agentData?.contacts?.phone || '',
      email: agentData?.contacts?.email || '',
    }),
    [website, agentData]
  );

  useEffect(() => {
    if (!website?.agent_id) {
      setAgentData(null);
      return;
    }
    const embed = website.status === 'published';
    axios
      .get(
        `${import.meta.env.VITE_API_URL || ''}${API_ROUTES.AGENT_PUBLIC_DATA(website.agent_id)}?embed=${embed}`,
        { headers: getAuthHeaders() }
      )
      .then((res) => setAgentData(res.data))
      .catch(() => setAgentData(null));
  }, [website?.agent_id, website?.status]);

  const previewSchema = schema
    ? { ...schema, styles: globalStyles, blocks }
    : null;

  const deviceStyle = {
    width: DEVICES[currentDevice].width,
    maxWidth: '100%',
    margin: '0 auto',
  };

  const handlePublish = async () => {
    try {
      setActionError(null);
      await publish();
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleUnpublish = async () => {
    try {
      setActionError(null);
      await unpublish();
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!blockToDelete) return;
    try {
      await removeBlock(blockToDelete.id);
      setBlockToDelete(null);
    } catch (e) {
      setActionError(e.message);
    }
  };

  const handleDeleteWebsite = async () => {
    const confirmed = window.confirm(
      'Удалить сайт безвозвратно? Будут удалены все блоки и связанные данные.'
    );
    if (!confirmed) {
      return;
    }

    try {
      setActionError(null);
      setDeletingWebsite(true);
      await deleteWebsite();
      navigate(NAVIGATION_ROUTES.AGENTS);
    } catch (e) {
      setActionError(e.response?.data?.detail || e.message || 'Не удалось удалить сайт');
    } finally {
      setDeletingWebsite(false);
    }
  };

  if (loading) {
    return (
      <div className="wb-constructor-loading">
        <div className="wb-spinner" />
        <p>Загрузка конструктора...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wb-constructor-loading">
        <p className="wb-error-text">{error}</p>
        <button type="button" className="wb-btn wb-btn--primary" onClick={() => navigate(-1)}>
          Назад
        </button>
      </div>
    );
  }

  return (
    <div className="wb-constructor">
      <ConstructorTopBar
        title={website?.title}
        status={website?.status}
        saveStatus={saveStatus}
        onSave={saveNow}
        onPreview={() => navigate(NAVIGATION_ROUTES.WEBSITE_PREVIEW(websiteId))}
        onPublish={handlePublish}
        onUnpublish={handleUnpublish}
        onDeleteWebsite={handleDeleteWebsite}
        deletingWebsite={deletingWebsite}
      />

      {actionError && (
        <div className="wb-constructor-alert">{actionError}</div>
      )}

      <div className="wb-constructor__body">
        {!blocks?.some((b) => b.type === 'fullpage') && (
          <BlockListPanel
            blocks={blocks}
            selectedBlockId={selectedBlockId}
            onSelect={setSelectedBlockId}
            onReorder={reorderBlocks}
            onAddClick={() => setAddModalOpen(true)}
            onDuplicate={duplicateBlock}
            onDelete={(id) => {
              const b = blocks.find((x) => x.id === id);
              setBlockToDelete(b);
            }}
            onClearSelection={() => setSelectedBlockId(null)}
          />
        )}

        <main className="wb-constructor__canvas">
          <div className="wb-canvas-toolbar">
            <DeviceSwitcher currentDevice={currentDevice} onDeviceChange={setCurrentDevice} />
          </div>
          <div className="wb-canvas-frame" style={deviceStyle}>
            {previewSchema && (
              <div onClick={() => setSelectedBlockId(null)} role="presentation">
                <WebsiteAgentProvider agent={agentData} agentId={website?.agent_id}>
                  <WebsiteRenderer
                    schema={previewSchema}
                    editMode
                    selectedBlockId={selectedBlockId}
                    onSelectBlock={setSelectedBlockId}
                    onContentChange={updateBlockContent}
                    placeholderVars={placeholderVars}
                  />
                  <AgentWidget
                    apiKey={agentData?.widget_api_key}
                    enabled={Boolean(agentData?.widget_api_key)}
                  />
                  <QuickContactButtons
                    contacts={agentData?.contacts}
                    primaryColor={globalStyles?.primaryColor}
                  />
                </WebsiteAgentProvider>
              </div>
            )}
          </div>
          {!selectedBlock && (
            <div className="wb-selection-hint">
              <span>Нажмите на любой блок в превью или в списке слева для детальной настройки</span>
            </div>
          )}
        </main>

        <div className="wb-constructor__sidebar-right">
          {/* Right panel tabs */}
          <div className="wb-panel-tabs">
            <button
              type="button"
              className={`wb-panel-tab ${rightPanelTab === 'settings' ? 'wb-panel-tab--active' : ''}`}
              onClick={() => setRightPanelTab('settings')}
            >
              {blocks?.some((b) => b.type === 'fullpage') ? 'AI' : 'Styles'}
            </button>
            <button
              type="button"
              className={`wb-panel-tab ${rightPanelTab === 'seo' ? 'wb-panel-tab--active' : ''}`}
              onClick={() => setRightPanelTab('seo')}
            >
              SEO
            </button>
          </div>

          {rightPanelTab === 'settings' && (
            <>
              {!blocks?.some((b) => b.type === 'fullpage') && (
                <BlockSettingsPanel
                  selectedBlock={selectedBlock}
                  globalStyles={globalStyles}
                  onGlobalStylesChange={updateGlobalStyles}
                  onBlockStylesChange={updateBlockStyles}
                />
              )}
              <AiPromptPanel
                selectedBlock={selectedBlock}
                blocks={blocks}
                loading={aiLoading}
                onSubmit={async (blockId, prompt, images) => {
                  try {
                    setActionError(null);
                    const result = await applyAiPrompt(blockId, prompt, images);
                    // Show success feedback with change summary if available
                    if (result?.change_summary) {
                      setAiFeedback({
                        type: 'success',
                        message: result.change_summary,
                        timestamp: Date.now(),
                      });
                    }
                  } catch (e) {
                    setActionError(e.response?.data?.detail || e.message || 'Ошибка AI');
                    setAiFeedback({
                      type: 'error',
                      message: e.response?.data?.detail || e.message || 'Ошибка AI',
                      timestamp: Date.now(),
                    });
                  }
                }}
              />
              {/* AI Feedback */}
              {aiFeedback && (
                <div className={`wb-ai-feedback wb-ai-feedback--${aiFeedback.type}`}>
                  <div className="wb-ai-feedback-content">
                    {aiFeedback.type === 'success' ? (
                      <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                    <span>{aiFeedback.message}</span>
                  </div>
                  <button
                    type="button"
                    className="wb-ai-feedback-close"
                    onClick={() => setAiFeedback(null)}
                  >
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              )}
            </>
          )}

          {rightPanelTab === 'seo' && (
            <SEOMetaPanel
              websiteId={websiteId}
              website={website}
              onUpdate={() => {
                // Refresh website data if needed
              }}
            />
          )}
        </div>
      </div>

      <AddBlockModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onSelect={async (type) => {
          try {
            await addBlock(type);
          } catch (e) {
            setActionError(e.message);
          }
        }}
      />

      <DeleteBlockDialog
        block={blockToDelete}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setBlockToDelete(null)}
      />
    </div>
  );
};

const ConstructorPage = () => (
  <ProtectedRoute>
    <ConstructorPageContent />
  </ProtectedRoute>
);

export default ConstructorPage;
