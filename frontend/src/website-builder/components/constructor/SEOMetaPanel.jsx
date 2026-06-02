import React, { useState, useEffect, useCallback } from 'react';
import {
  Globe,
  Image as ImageIcon,
  Upload,
  Wand2,
  AlertTriangle,
  CheckCircle,
  Info,
  ExternalLink,
  RefreshCw,
  X,
} from 'lucide-react';
import {
  fetchSEOMeta,
  updateSEOMeta,
  fetchSEOPreview,
  uploadFavicon,
  uploadOGImage,
  generateOGImage,
} from '../../utils/api';
import '../../styles/constructor.css';

// Character count limits
const LIMITS = {
  title: { min: 30, max: 60, warning: 70 },
  metaDescription: { min: 120, max: 160, warning: 180 },
  ogTitle: { min: 30, max: 60, warning: 100 },
  ogDescription: { min: 60, max: 300, warning: 300 },
};

function CharacterCounter({ current, limits, label }) {
  const { min, max, warning } = limits;
  let status = 'good';
  if (current < min) status = 'warning';
  else if (current > max) status = current > warning ? 'error' : 'warning';

  const statusColors = {
    good: 'text-green-600',
    warning: 'text-yellow-600',
    error: 'text-red-600',
  };

  return (
    <span className={`wb-seo-counter ${statusColors[status]}`}>
      {current}/{max} {label}
    </span>
  );
}

function GooglePreview({ preview }) {
  if (!preview) return null;

  const titleColor = {
    good: 'text-green-700',
    warning: 'text-yellow-700',
    error: 'text-red-700',
  };

  return (
    <div className="wb-seo-preview-card">
      <div className="wb-seo-preview-head">
        <div className="wb-seo-preview-badge">
          <span>G</span>
        </div>
        <div>
          <div className="wb-seo-preview-domain">rsd-ai.ru</div>
          <div className="wb-seo-preview-url">https://rsd-ai.ru/...</div>
        </div>
      </div>

      <div className={`wb-seo-preview-title ${titleColor[preview.google_title_status]}`}>
        {preview.google_title || 'No title set'}
      </div>

      <div className={`wb-seo-preview-desc ${preview.google_description_status === 'error' ? 'text-red-600' : 'text-gray-600'}`}>
        {preview.google_description || 'No description set'}
      </div>

      <div className="wb-seo-preview-metrics">
        <CharacterCounter
          current={preview.google_title_length}
          limits={LIMITS.title}
          label="title"
        />
        <CharacterCounter
          current={preview.google_description_length}
          limits={LIMITS.metaDescription}
          label="description"
        />
      </div>
    </div>
  );
}

function TelegramPreview({ preview }) {
  if (!preview) return null;

  return (
    <div className="wb-seo-tg-preview">
      <div className="wb-seo-tg-title">
        {preview.telegram_title || 'No title'}
      </div>

      <div className="wb-seo-tg-card">
        {preview.telegram_image_url ? (
          <img
            src={preview.telegram_image_url}
            alt="OG Preview"
            className="wb-seo-tg-image"
          />
        ) : (
          <div className="wb-seo-tg-image wb-seo-tg-image--placeholder">
            <ImageIcon className="w-8 h-8 text-slate-400" />
          </div>
        )}
        <div className="wb-seo-tg-body">
          <div className="wb-seo-tg-domain">rsd-ai.ru</div>
          <div className="wb-seo-tg-desc">
            {preview.telegram_description || 'No description'}
          </div>
        </div>
      </div>
    </div>
  );
}

function FaviconUploader({ websiteId, currentUrl, onUpdate }) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(currentUrl);

  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      await handleUpload(file);
    }
  }, []);

  const handleUpload = async (file) => {
    if (!file) return;

    setUploading(true);
    try {
      // Preview
      const reader = new FileReader();
      reader.onloadend = () => setPreview(reader.result);
      reader.readAsDataURL(file);

      // Upload
      const result = await uploadFavicon(websiteId, file);
      if (result.success) {
        onUpdate(result.favicon_url);
      }
    } catch (error) {
      console.error('Favicon upload failed:', error);
      alert('Failed to upload favicon');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="wb-seo-section">
      <label className="wb-seo-label">
        <Globe className="w-4 h-4" />
        Favicon
      </label>

      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`wb-seo-uploader ${isDragging ? 'wb-seo-uploader--drag' : ''} ${uploading ? 'wb-seo-uploader--busy' : ''}`}
      >
        {preview ? (
          <div className="wb-seo-uploader-stack">
            <img
              src={preview}
              alt="Favicon preview"
              className="wb-seo-favicon-preview"
            />
            <div className="wb-seo-muted">
              Recommended: 32x32, 180x180 (Apple touch)
            </div>
            <label className="wb-seo-link">
              <input
                type="file"
                accept="image/png,image/svg+xml,image/x-icon,image/vnd.microsoft.icon"
                className="hidden"
                onChange={(e) => handleUpload(e.target.files[0])}
              />
              Change favicon
            </label>
          </div>
        ) : (
          <div className="wb-seo-uploader-stack">
            <Upload className="w-8 h-8 text-slate-400" />
            <div className="wb-seo-text">
              Drag and drop or{' '}
              <label className="wb-seo-link">
                <input
                  type="file"
                  accept="image/png,image/svg+xml,image/x-icon,image/vnd.microsoft.icon"
                  className="hidden"
                  onChange={(e) => handleUpload(e.target.files[0])}
                />
                browse
              </label>
            </div>
            <div className="wb-seo-muted">
              PNG, SVG, ICO. Max 5MB. Auto-converts to all sizes.
            </div>
          </div>
        )}
      </div>

      {uploading && (
        <div className="wb-seo-progress">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Converting favicon...
        </div>
      )}
    </div>
  );
}

function OGImageUploader({ websiteId, website, currentUrl, onUpdate }) {
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [preview, setPreview] = useState(currentUrl);

  const handleUpload = async (file) => {
    if (!file) return;

    setUploading(true);
    try {
      const reader = new FileReader();
      reader.onloadend = () => setPreview(reader.result);
      reader.readAsDataURL(file);

      const result = await uploadOGImage(websiteId, file);
      if (result.success) {
        onUpdate(result.og_image_url);
      }
    } catch (error) {
      console.error('OG image upload failed:', error);
      alert('Failed to upload image');
    } finally {
      setUploading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await generateOGImage(websiteId, {
        title: website?.title || 'My Website',
        description: website?.meta_description || '',
        background_color: website?.custom_styles?.primaryColor || '#3B82F6',
        text_color: '#FFFFFF',
      });

      if (result.success) {
        onUpdate(result.og_image_url);
        setPreview(result.og_image_url);
      }
    } catch (error) {
      console.error('OG image generation failed:', error);
      alert('Failed to generate image');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="wb-seo-section">
      <label className="wb-seo-label">
        <ImageIcon className="w-4 h-4" />
        OpenGraph Image
        <span className="wb-seo-muted">
          (1200 x 630 for social sharing)
        </span>
      </label>

      <div className="wb-seo-stack">
        {preview && (
          <div className="wb-seo-og-wrap">
            <img
              src={preview}
              alt="OG Preview"
              className="wb-seo-og-image"
            />
            <button
              onClick={() => { setPreview(null); onUpdate(null); }}
              className="wb-seo-og-delete"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="wb-seo-actions-row">
          <label className={`wb-seo-action-card ${uploading ? 'wb-seo-action-card--busy' : ''}`}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => handleUpload(e.target.files[0])}
              disabled={uploading}
            />
            <Upload className="w-5 h-5 mx-auto mb-1 text-slate-400" />
            <span className="wb-seo-action-label">
              {uploading ? 'Uploading...' : 'Upload'}
            </span>
          </label>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className={`wb-seo-action-card wb-seo-action-card--primary ${generating ? 'wb-seo-action-card--busy' : ''}`}
          >
            <Wand2 className="w-5 h-5 mx-auto mb-1 text-blue-500" />
            <span className="wb-seo-action-label wb-seo-action-label--primary">
              {generating ? 'Generating...' : 'Auto-generate'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}

export function SEOMetaPanel({ websiteId, website, onUpdate }) {
  const [meta, setMeta] = useState({
    title: '',
    meta_description: '',
    og_title: '',
    og_description: '',
    og_image_url: null,
    favicon_url: null,
  });
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');

  useEffect(() => {
    if (websiteId) {
      loadData();
    }
  }, [websiteId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [metaData, previewData] = await Promise.all([
        fetchSEOMeta(websiteId),
        fetchSEOPreview(websiteId),
      ]);

      setMeta({
        title: metaData.title || '',
        meta_description: metaData.meta_description || '',
        og_title: metaData.og_title || '',
        og_description: metaData.og_description || '',
        og_image_url: metaData.og_image_url,
        favicon_url: metaData.favicon_url,
      });
      setPreview(previewData);
    } catch (error) {
      console.error('Failed to load SEO data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateSEOMeta(websiteId, {
        title: meta.title || null,
        meta_description: meta.meta_description || null,
        og_title: meta.og_title || null,
        og_description: meta.og_description || null,
        og_image_url: meta.og_image_url,
        favicon_url: meta.favicon_url,
      });

      // Refresh preview
      const previewData = await fetchSEOPreview(websiteId);
      setPreview(previewData);

      onUpdate?.();
    } catch (error) {
      console.error('Failed to save SEO data:', error);
      alert('Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field, value) => {
    setMeta(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div className="wb-seo-loading">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading SEO settings...
      </div>
    );
  }

  return (
    <div className="wb-seo-root">
      <div className="wb-seo-header">
        <h3 className="wb-seo-title">SEO & Metadata</h3>
        <button
          onClick={handleSave}
          disabled={saving}
          className="wb-btn wb-btn--primary"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Tabs */}
      <div className="wb-seo-tabs">
        {[
          { id: 'basic', label: 'Basic', icon: Globe },
          { id: 'social', label: 'Social', icon: ImageIcon },
          { id: 'preview', label: 'Preview', icon: ExternalLink },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`wb-seo-tab ${activeTab === tab.id ? 'wb-seo-tab--active' : ''}`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'basic' && (
        <div className="wb-seo-stack">
          {/* Title */}
          <div className="wb-seo-section">
            <label className="wb-seo-label">
              Page Title
              <Info className="w-4 h-4 text-slate-400" title="Appears in browser tab and search results" />
            </label>
            <input
              type="text"
              value={meta.title}
              onChange={(e) => updateField('title', e.target.value)}
              placeholder="My Business Name"
              maxLength={100}
              className="wb-seo-input"
            />
            <div className="wb-seo-row-between">
              <CharacterCounter
                current={meta.title.length}
                limits={LIMITS.title}
                label="characters"
              />
              <span className="wb-seo-muted">
                Recommended: 30-60 characters
              </span>
            </div>
          </div>

          {/* Meta Description */}
          <div className="wb-seo-section">
            <label className="wb-seo-label">
              Meta Description
            </label>
            <textarea
              value={meta.meta_description}
              onChange={(e) => updateField('meta_description', e.target.value)}
              placeholder="Brief description of your business for search engines..."
              maxLength={500}
              rows={3}
              className="wb-seo-input wb-seo-input--textarea"
            />
            <div className="wb-seo-row-between">
              <CharacterCounter
                current={meta.meta_description.length}
                limits={LIMITS.metaDescription}
                label="characters"
              />
              <span className="wb-seo-muted">
                Recommended: 120-160 characters
              </span>
            </div>
          </div>

          {/* Favicon */}
          <FaviconUploader
            websiteId={websiteId}
            currentUrl={meta.favicon_url}
            onUpdate={(url) => updateField('favicon_url', url)}
          />
        </div>
      )}

      {activeTab === 'social' && (
        <div className="wb-seo-stack">
          <div className="wb-seo-info">
            These settings control how your site appears when shared on social media
            (Telegram, Facebook, Twitter, etc.)
          </div>

          {/* OG Title */}
          <div className="wb-seo-section">
            <label className="wb-seo-label">
              Social Title
              <span className="wb-seo-muted">
                (defaults to Page Title if empty)
              </span>
            </label>
            <input
              type="text"
              value={meta.og_title}
              onChange={(e) => updateField('og_title', e.target.value)}
              placeholder={meta.title || 'Social sharing title'}
              maxLength={100}
              className="wb-seo-input"
            />
            <CharacterCounter
              current={meta.og_title.length}
              limits={LIMITS.ogTitle}
              label="characters"
            />
          </div>

          {/* OG Description */}
          <div className="wb-seo-section">
            <label className="wb-seo-label">
              Social Description
            </label>
            <textarea
              value={meta.og_description}
              onChange={(e) => updateField('og_description', e.target.value)}
              placeholder={meta.meta_description || 'Description for social sharing...'}
              maxLength={300}
              rows={3}
              className="wb-seo-input wb-seo-input--textarea"
            />
            <CharacterCounter
              current={meta.og_description.length}
              limits={LIMITS.ogDescription}
              label="characters"
            />
          </div>

          {/* OG Image */}
          <OGImageUploader
            websiteId={websiteId}
            website={website}
            currentUrl={meta.og_image_url}
            onUpdate={(url) => updateField('og_image_url', url)}
          />
        </div>
      )}

      {activeTab === 'preview' && (
        <div className="wb-seo-stack">
          {/* Warnings */}
          {preview?.warnings?.length > 0 && (
            <div className="wb-seo-stack">
              {preview.warnings.map((warning, idx) => (
                <div
                  key={idx}
                  className="wb-seo-warning"
                >
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  {warning}
                </div>
              ))}
            </div>
          )}

          {preview?.warnings?.length === 0 && (
            <div className="wb-seo-success">
              <CheckCircle className="w-4 h-4" />
              All SEO settings look good!
            </div>
          )}

          {/* Google Preview */}
          <div className="wb-seo-section">
            <h4 className="wb-seo-subtitle">
              <div className="wb-seo-mini-badge">
                G
              </div>
              Google Search Preview
            </h4>
            <GooglePreview preview={preview} />
          </div>

          {/* Telegram Preview */}
          <div className="wb-seo-section">
            <h4 className="wb-seo-subtitle">
              <div className="wb-seo-mini-badge wb-seo-mini-badge--alt">
                T
              </div>
              Telegram Link Preview
            </h4>
            <TelegramPreview preview={preview} />
          </div>
        </div>
      )}
    </div>
  );
}
