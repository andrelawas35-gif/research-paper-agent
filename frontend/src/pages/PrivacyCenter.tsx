/**
 * PrivacyCenter — Data & Privacy Center (U3 frontend).
 *
 * Provides inspect, correct, export, delete, retention, consent,
 * and access-audit views for Regulation records.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api/client';
import type { SessionSummary, RegulationSession } from '../api/client';

type Tab = 'sessions' | 'export' | 'audit' | 'retention';

export default function PrivacyCenter() {
  const [activeTab, setActiveTab] = useState<Tab>('sessions');
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (activeTab === 'sessions') {
      loadSessions();
    }
  }, [activeTab]);

  const loadSessions = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.privacy.listSessions();
      setSessions(result.sessions);
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (sessionId: string) => {
    if (!confirm('Permanently delete this session? This cannot be undone.')) return;
    setLoading(true);
    try {
      await api.privacy.deleteSession(sessionId);
      setMessage('Session deleted.');
      loadSessions();
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to delete session');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm('Permanently delete ALL regulation sessions? This cannot be undone.')) return;
    setLoading(true);
    try {
      const result = await api.privacy.deleteAll();
      setMessage(`${result.deleted_count} sessions deleted.`);
      loadSessions();
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to delete all sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await api.privacy.exportData('all');
      const blob = new Blob([JSON.stringify(result, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pkm-export-${result.export_id}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage('Export downloaded.');
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to export data');
    } finally {
      setLoading(false);
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'sessions', label: 'Sessions' },
    { id: 'export', label: 'Export' },
    { id: 'audit', label: 'Audit Log' },
    { id: 'retention', label: 'Retention' },
  ];

  return (
    <div className="max-w-lg mx-auto px-4 py-6 safe-bottom">
      <div className="flex items-center justify-between mb-6">
        <Link to="/" className="text-muted hover:text-ink text-sm">
          ← Home
        </Link>
        <h1 className="text-lg font-semibold">Data & Privacy Center</h1>
        <div className="w-12" />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`flex-1 pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-indigo-500 text-action'
                : 'border-transparent text-muted hover:text-ink'
            }`}
            onClick={() => {
              setActiveTab(tab.id);
              setMessage('');
              setError('');
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {message && (
        <div className="bg-emerald-900/30 border border-emerald-800 rounded-control p-3 text-emerald-200 text-sm mb-4">
          {message}
        </div>
      )}

      {error && (
        <div className="bg-danger/10/40 border border-danger rounded-control p-3 text-danger text-sm mb-4">
          {error}
        </div>
      )}

      {/* Sessions tab */}
      {activeTab === 'sessions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted">
              {sessions.length} regulation session{sessions.length !== 1 ? 's' : ''}
            </p>
            {sessions.length > 0 && (
              <button
                className="btn-danger text-sm py-1 px-3"
                onClick={handleDeleteAll}
                disabled={loading}
              >
                Delete All
              </button>
            )}
          </div>

          {loading && <p className="text-muted text-sm">Loading...</p>}

          {!loading && sessions.length === 0 && (
            <p className="text-muted text-sm">
              No regulation sessions found. Sessions from your check-ins will
              appear here.
            </p>
          )}

          {sessions.map((s) => (
            <div key={s.session_id} className="card flex items-start justify-between">
              <div className="space-y-1 text-sm">
                <p className="font-medium text-ink">
                  {s.trigger_event || 'Untitled'}
                </p>
                <p className="text-muted text-xs">
                  {s.created_at} • {s.state}
                  {s.is_private ? ' • Private' : ' • Saved'}
                  {s.safety_active ? ' • Safety Active' : ''}
                </p>
                <p className="text-slate-600 text-xs">
                  {s.fact_count} facts • {s.emotion_count} emotions •{' '}
                  {s.action_count} actions
                </p>
              </div>
              <button
                className="text-danger hover:text-red-300 text-sm ml-4 shrink-0"
                onClick={() => handleDelete(s.session_id)}
                disabled={loading}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Export tab */}
      {activeTab === 'export' && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold mb-2">Export Your Data</h2>
            <p className="text-sm text-muted mb-4">
              Download a complete JSON export of your regulation data. The
              export includes all sessions, rules, and metadata for the selected
              scope. Sensitive content is encrypted in the export.
            </p>
            <button
              className="btn-primary w-full"
              onClick={handleExport}
              disabled={loading}
            >
              {loading ? 'Exporting...' : 'Export All Regulation Data'}
            </button>
          </div>

          <div className="card">
            <h2 className="font-semibold mb-2">Export Scope</h2>
            <p className="text-sm text-muted">
              Currently exports all regulation sessions and personal rules.
              Private check-ins (ephemeral sessions) are not included.
              Intimate relationship content is excluded by default.
            </p>
          </div>
        </div>
      )}

      {/* Audit tab */}
      {activeTab === 'audit' && (
        <AuditTab />
      )}

      {/* Retention tab */}
      {activeTab === 'retention' && (
        <RetentionTab />
      )}
    </div>
  );
}

function AuditTab() {
  const [entries, setEntries] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    api.privacy
      .getAuditLog()
      .then((result) => setEntries(result.entries))
      .catch((e: unknown) =>
        setError((e as api.ApiError).detail || 'Failed to load audit log'),
      )
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Metadata-only access log. No content or sensitive data is recorded here.
      </p>

      {loading && <p className="text-muted text-sm">Loading...</p>}
      {error && (
        <div className="bg-danger/10/40 border border-danger rounded-control p-3 text-danger text-sm">
          {error}
        </div>
      )}

      {!loading && entries.length === 0 && (
        <p className="text-muted text-sm">No audit entries yet.</p>
      )}

      <div className="space-y-2">
        {entries.slice(-20).reverse().map((entry, i) => (
          <div key={i} className="card text-xs text-muted">
            <div className="flex justify-between">
              <span>{entry.endpoint as string}</span>
              <span>{entry.method as string}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RetentionTab() {
  const [data, setData] = useState<{
    default_retention_days: number;
    private_checkin_retention_hours: number;
    sessions: { session_id: string; expires_at: string }[];
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    api.privacy
      .getRetention()
      .then(setData)
      .catch((e: unknown) =>
        setError((e as api.ApiError).detail || 'Failed to load retention info'),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-muted text-sm">Loading...</p>;
  if (error)
    return (
      <div className="bg-danger/10/40 border border-danger rounded-control p-3 text-danger text-sm">
        {error}
      </div>
    );
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="font-semibold mb-2">Retention Policy</h2>
        <div className="space-y-2 text-sm text-ink">
          <p>
            <span className="text-muted">Default retention:</span>{' '}
            {data.default_retention_days} days
          </p>
          <p>
            <span className="text-muted">Private check-ins:</span>{' '}
            {data.private_checkin_retention_hours} hours (then automatically
            deleted)
          </p>
        </div>
      </div>

      {data.sessions.length > 0 && (
        <div className="card">
          <h2 className="font-semibold mb-2">Session Expiry</h2>
          <div className="space-y-2">
            {data.sessions.map((s) => (
              <div
                key={s.session_id}
                className="text-sm flex justify-between text-muted"
              >
                <span className="font-mono text-xs">{s.session_id.slice(0, 12)}...</span>
                <span>Expires: {s.expires_at}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.sessions.length === 0 && (
        <p className="text-sm text-muted">
          No sessions with active retention tracking. Sessions are automatically
          deleted after their retention period.
        </p>
      )}
    </div>
  );
}
