/**
 * Domain Manager Panel
 * UI for managing custom domains (Stage 7)
 *
 * Features:
 * - Add new custom domain
 * - DNS verification instructions
 * - Verify domain (DNS TXT record check)
 * - Remove domain
 * - View verification status
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Globe,
  Plus,
  Trash2,
  CheckCircle,
  AlertCircle,
  Clock,
  ExternalLink,
  RefreshCw,
  Copy,
  Check,
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

function authHeaders() {
  const token = localStorage.getItem('accessToken');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const DomainManagerPanel = ({ websiteId, slug }) => {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [newDomain, setNewDomain] = useState('');
  const [addingDomain, setAddingDomain] = useState(false);
  const [verifyingDomain, setVerifyingDomain] = useState(null);
  const [copiedField, setCopiedField] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);

  // Base domain for subdomain access
  const baseDomain = window.location.hostname.includes('rsd-ai.ru')
    ? 'rsd-ai.ru'
    : window.location.hostname;

  const subdomainUrl = slug ? `${slug}.${baseDomain}` : null;

  const fetchDomains = useCallback(async () => {
    if (!websiteId) return;

    try {
      setLoading(true);
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/domains`,
        { headers: authHeaders() }
      );
      setDomains(response.data || []);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load domains');
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    fetchDomains();
  }, [fetchDomains]);

  const handleAddDomain = async () => {
    if (!newDomain.trim()) return;

    // Validate domain format
    const domainRegex = /^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$/;
    if (!domainRegex.test(newDomain)) {
      setError('Invalid domain format. Example: example.com');
      return;
    }

    try {
      setAddingDomain(true);
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/domains`,
        { domain: newDomain },
        { headers: authHeaders() }
      );

      // Add new domain to list
      setDomains([...domains, response.data]);
      setNewDomain('');
      setShowAddModal(false);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail?.message || err.response?.data?.detail || 'Failed to add domain');
    } finally {
      setAddingDomain(false);
    }
  };

  const handleVerifyDomain = async (domainId, domain) => {
    try {
      setVerifyingDomain(domainId);
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/domains/${domainId}/verify`,
        {},
        { headers: authHeaders() }
      );

      // Update domain status
      setDomains(domains.map(d =>
        d.id === domainId
          ? { ...d, verification_status: response.data.verification_status }
          : d
      ));
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Verification failed');
    } finally {
      setVerifyingDomain(null);
    }
  };

  const handleRemoveDomain = async (domainId) => {
    if (!window.confirm('Are you sure you want to remove this domain?')) return;

    try {
      await axios.delete(
        `${API_BASE_URL}/api/v1/websites/${websiteId}/domains/${domainId}`,
        { headers: authHeaders() }
      );

      // Remove from list
      setDomains(domains.filter(d => d.id !== domainId));
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove domain');
    }
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'verified':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-yellow-500" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'verified':
        return 'Verified';
      case 'pending':
        return 'Pending verification';
      case 'failed':
        return 'Verification failed';
      default:
        return 'Unknown';
    }
  };

  const getStatusClass = (status) => {
    switch (status) {
      case 'verified':
        return 'bg-green-50 text-green-700 border-green-200';
      case 'pending':
        return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      case 'failed':
        return 'bg-red-50 text-red-700 border-red-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-blue-500" />
          <h3 className="text-lg font-semibold">Custom Domains</h3>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Domain
        </button>
      </div>

      {/* Subdomain info */}
      {subdomainUrl && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-700">
            <strong>Free subdomain available:</strong>{' '}
            <a
              href={`https://${subdomainUrl}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:no-underline inline-flex items-center gap-1"
            >
              {subdomainUrl}
              <ExternalLink className="w-3 h-3" />
            </a>
          </p>
          <p className="text-xs text-blue-600 mt-1">
            Your website is automatically available at this address when published.
          </p>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Domain list */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="w-5 h-5 text-gray-400 animate-spin" />
        </div>
      ) : domains.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <Globe className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No custom domains configured</p>
          <p className="text-xs mt-1">
            Add your own domain (e.g., example.com) to make your site more professional.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {domains.map((domain) => (
            <div
              key={domain.id}
              className={`p-4 rounded-lg border ${getStatusClass(domain.verification_status)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(domain.verification_status)}
                  <div>
                    <p className="font-medium">{domain.domain}</p>
                    <p className="text-sm opacity-75">
                      {getStatusText(domain.verification_status)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {domain.verification_status === 'verified' && (
                    <a
                      href={`https://${domain.domain}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 hover:bg-white/50 rounded transition-colors"
                      title="Open website"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  {domain.verification_status !== 'verified' && (
                    <button
                      onClick={() => handleVerifyDomain(domain.id, domain.domain)}
                      disabled={verifyingDomain === domain.id}
                      className="p-1.5 hover:bg-white/50 rounded transition-colors"
                      title="Verify domain"
                    >
                      {verifyingDomain === domain.id ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <RefreshCw className="w-4 h-4" />
                      )}
                    </button>
                  )}
                  <button
                    onClick={() => handleRemoveDomain(domain.id)}
                    className="p-1.5 hover:bg-white/50 rounded transition-colors text-red-500"
                    title="Remove domain"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* DNS Instructions for pending domains */}
              {domain.verification_status === 'pending' && domain.dns_record_name && (
                <div className="mt-3 p-3 bg-white/70 rounded border border-current border-opacity-20">
                  <p className="text-sm font-medium mb-2">DNS Configuration Required:</p>
                  <p className="text-sm mb-3">
                    Add the following TXT record to your DNS to verify domain ownership:
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <code className="flex-1 px-2 py-1.5 bg-gray-100 rounded text-xs font-mono">
                        Name: {domain.dns_record_name}
                      </code>
                      <button
                        onClick={() => copyToClipboard(domain.dns_record_name, `name-${domain.id}`)}
                        className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                      >
                        {copiedField === `name-${domain.id}` ? (
                          <Check className="w-4 h-4 text-green-500" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 px-2 py-1.5 bg-gray-100 rounded text-xs font-mono">
                        Value: {domain.verification_token}
                      </code>
                      <button
                        onClick={() => copyToClipboard(domain.verification_token, `value-${domain.id}`)}
                        className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                      >
                        {copiedField === `value-${domain.id}` ? (
                          <Check className="w-4 h-4 text-green-500" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                  <p className="text-xs mt-3 opacity-75">
                    After adding the TXT record, click the verify button above.
                    DNS changes may take up to 24 hours to propagate.
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add Domain Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md m-4">
            <h4 className="text-lg font-semibold mb-4">Add Custom Domain</h4>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Domain Name
                </label>
                <input
                  type="text"
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value.toLowerCase())}
                  placeholder="example.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Enter your domain without http:// or https://
                </p>
              </div>

              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  <strong>Before adding:</strong> Make sure you own this domain and can modify its DNS settings.
                  You will need to add a TXT record for verification.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddDomain}
                disabled={addingDomain || !newDomain.trim()}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {addingDomain ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Add Domain
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DomainManagerPanel;