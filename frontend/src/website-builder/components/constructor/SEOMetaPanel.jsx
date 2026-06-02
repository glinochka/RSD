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
    <span className={`text-xs ${statusColors[status]}`}>
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
    <div className="bg-white rounded-lg border border-gray-200 p-4 mt-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
          <span className="text-white text-xs font-bold">G</span>
        </div>
        <div>
          <div className="text-xs text-gray-500">rsd-ai.ru</div>
          <div className="text-xs text-gray-400">https://rsd-ai.ru/...</div>
        </div>
      </div>

      <div className={`text-blue-700 text-lg font-medium hover:underline cursor-pointer truncate ${titleColor[preview.google_title_status]}`}>
        {preview.google_title || 'No title set'}
      </div>

      <div className={`text-sm mt-1 ${preview.google_description_status === 'error' ? 'text-red-600' : 'text-gray-600'}`}>
        {preview.google_description || 'No description set'}
      </div>

      <div className="mt-2 flex items-center gap-4 text-xs">
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
    <div className="bg-[#17212b] rounded-lg p-4 mt-4 max-w-sm">
      <div className="text-white text-sm font-medium mb-2">
        {preview.telegram_title || 'No title'}
      </div>

      <div className="bg-[#232e3c] rounded-lg overflow-hidden">
        {preview.telegram_image_url ? (
          <img
            src={preview.telegram_image_url}
            alt="OG Preview"
            className="w-full h-32 object-cover"
          />
        ) : (
          <div className="w-full h-32 bg-gray-600 flex items-center justify-center">
            <ImageIcon className="w-8 h-8 text-gray-400" />
          </div>
        )}
        <div className="p-3">
          <div className="text-[#8a96a3] text-xs">rsd-ai.ru</div>
          <div className="text-white text-sm mt-1 line-clamp-2">
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
    <div className="space-y-3">
      <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
        <Globe className="w-4 h-4" />
        Favicon
      </label>

      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-6 text-center transition-colors
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}
          ${uploading ? 'opacity-50' : ''}
        `}
      >
        {preview ? (
          <div className="flex flex-col items-center gap-3">
            <img
              src={preview}
              alt="Favicon preview"
              className="w-16 h-16 rounded-lg object-contain bg-gray-100"
            />
            <div className="text-xs text-gray-500">
              Recommended: 32x32, 180x180 (Apple touch)
            </div>
            <label className="cursor-pointer text-sm text-blue-600 hover:text-blue-700">
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
          <div className="flex flex-col items-center gap-3">
            <Upload className="w-8 h-8 text-gray-400" />
            <div className="text-sm text-gray-600">
              Drag and drop or{' '}
              <label className="cursor-pointer text-blue-600 hover:text-blue-700">
                <input
                  type="file"
                  accept="image/png,image/svg+xml,image/x-icon,image/vnd.microsoft.icon"
                  className="hidden"
                  onChange={(e) => handleUpload(e.target.files[0])}
                />
                browse
              </label>
            </div>
            <div className="text-xs text-gray-500">
              PNG, SVG, ICO. Max 5MB. Auto-converts to all sizes.
            </div>
          </div>
        )}
      </div>

      {uploading && (
        <div className="text-sm text-blue-600 flex items-center gap-2">
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
    <div className="space-y-3">
      <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
        <ImageIcon className="w-4 h-4" />
        OpenGraph Image
        <span className="text-xs font-normal text-gray-500">
          (1200 x 630 for social sharing)
        </span>
      </label>

      <div className="space-y-3">
        {preview && (
          <div className="relative">
            <img
              src={preview}
              alt="OG Preview"
              className="w-full h-40 object-cover rounded-lg bg-gray-100"
            />
            <button
              onClick={() => { setPreview(null); onUpdate(null); }}
              className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full hover:bg-red-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="flex gap-2">
          <label className={`
            flex-1 cursor-pointer border-2 border-dashed border-gray-300 rounded-lg p-3
            text-center hover:border-gray-400 transition-colors
            ${uploading ? 'opacity-50' : ''}
          `}>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => handleUpload(e.target.files[0])}
              disabled={uploading}
            />
            <Upload className="w-5 h-5 mx-auto mb-1 text-gray-400" />
            <span className="text-sm text-gray-600">
              {uploading ? 'Uploading...' : 'Upload'}
            </span>
          </label>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className={`
              flex-1 border-2 border-dashed border-blue-300 rounded-lg p-3
              text-center hover:border-blue-400 transition-colors
              ${generating ? 'opacity-50' : ''}
            `}
          >
            <Wand2 className="w-5 h-5 mx-auto mb-1 text-blue-500" />
            <span className="text-sm text-blue-600">
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
      <div className="p-4 text-center text-gray-500">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading SEO settings...
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">SEO & Metadata</h3>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {[
          { id: 'basic', label: 'Basic', icon: Globe },
          { id: 'social', label: 'Social', icon: ImageIcon },
          { id: 'preview', label: 'Preview', icon: ExternalLink },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors
              ${activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
              }
            `}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'basic' && (
        <div className="space-y-4">
          {/* Title */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
              Page Title
              <Info className="w-4 h-4 text-gray-400" title="Appears in browser tab and search results" />
            </label>
            <input
              type="text"
              value={meta.title}
              onChange={(e) => updateField('title', e.target.value)}
              placeholder="My Business Name"
              maxLength={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <div className="flex justify-between items-center">
              <CharacterCounter
                current={meta.title.length}
                limits={LIMITS.title}
                label="characters"
              />
              <span className="text-xs text-gray-500">
                Recommended: 30-60 characters
              </span>
            </div>
          </div>

          {/* Meta Description */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">
              Meta Description
            </label>
            <textarea
              value={meta.meta_description}
              onChange={(e) => updateField('meta_description', e.target.value)}
              placeholder="Brief description of your business for search engines..."
              maxLength={500}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
            />
            <div className="flex justify-between items-center">
              <CharacterCounter
                current={meta.meta_description.length}
                limits={LIMITS.metaDescription}
                label="characters"
              />
              <span className="text-xs text-gray-500">
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
        <div className="space-y-4">
          <div className="bg-blue-50 p-3 rounded-lg text-sm text-blue-700">
            These settings control how your site appears when shared on social media
            (Telegram, Facebook, Twitter, etc.)
          </div>

          {/* OG Title */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">
              Social Title
              <span className="text-xs font-normal text-gray-500 ml-2">
                (defaults to Page Title if empty)
              </span>
            </label>
            <input
              type="text"
              value={meta.og_title}
              onChange={(e) => updateField('og_title', e.target.value)}
              placeholder={meta.title || 'Social sharing title'}
              maxLength={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <CharacterCounter
              current={meta.og_title.length}
              limits={LIMITS.ogTitle}
              label="characters"
            />
          </div>

          {/* OG Description */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">
              Social Description
            </label>
            <textarea
              value={meta.og_description}
              onChange={(e) => updateField('og_description', e.target.value)}
              placeholder={meta.meta_description || 'Description for social sharing...'}
              maxLength={300}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
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
        <div className="space-y-4">
          {/* Warnings */}
          {preview?.warnings?.length > 0 && (
            <div className="space-y-2">
              {preview.warnings.map((warning, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800"
                >
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  {warning}
                </div>
              ))}
            </div>
          )}

          {preview?.warnings?.length === 0 && (
            <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
              <CheckCircle className="w-4 h-4" />
              All SEO settings look good!
            </div>
          )}

          {/* Google Preview */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold">
                G
              </div>
              Google Search Preview
            </h4>
            <GooglePreview preview={preview} />
          </div>

          {/* Telegram Preview */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <div className="w-5 h-5 rounded-full bg-blue-400 flex items-center justify-center text-white text-xs font-bold">
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
