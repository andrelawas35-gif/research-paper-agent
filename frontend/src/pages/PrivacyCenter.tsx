/**
 * PrivacyCenter — Data & Privacy Center (U3 frontend).
 *
 * Provides inspect, correct, export, delete, retention, consent,
 * and access-audit views for Regulation records.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../api/client';
import type { SessionSummary } from '../api/client';
import { StatusNotice } from '../components/StatusNotice';
import { SourceStamp } from '../components/SourceStamp';
import {
  deleteOfflineOrientation,
  exportOfflineOrientation,
  hasOfflineOrientation,
  saveOfflineOrientation,
} from '../offline/orientationStore';

type Tab = 'sessions' | 'offline' | 'export' | 'audit' | 'retention';

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
    if (!confirm('Cryptographically delete this session? Its key will be destroyed, making retained database and backup ciphertext unreadable.')) return;
    setLoading(true);
    try {
      await api.privacy.deleteSession(sessionId);
      setMessage('Session cryptographically deleted.');
      loadSessions();
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to delete session');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm('Cryptographically delete ALL Regulation sessions? Their keys will be destroyed and this cannot be undone.')) return;
    setLoading(true);
    try {
      const result = await api.privacy.deleteAll();
      setMessage(`${result.deleted_count} sessions cryptographically deleted.`);
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
    { id: 'offline', label: 'Offline' },
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
                ? 'border-action text-action'
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
        <StatusNotice variant="confirmation">{message}</StatusNotice>
      )}

      {error && (
        <StatusNotice variant="error">{error}</StatusNotice>
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
                <SourceStamp
                  sourceType="note"
                  date={s.created_at}
                  sensitivity={s.is_private ? 'identity_shaping' : 'low'}
                />
                <p className="text-muted text-xs">
                  {s.state}{s.is_private ? ' · Private' : ' · Saved'}
                  {s.safety_active ? ' · Safety Active' : ''}
                </p>
                <p className="text-muted text-xs">
                  {s.fact_count} facts · {s.emotion_count} emotions ·{' '}
                  {s.action_count} actions
                </p>
              </div>
              <button
                className="text-danger hover:text-danger/70 text-sm ml-4 shrink-0"
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
      {activeTab === 'offline' && <OfflineOrientationManager />}

      {/* Export tab */}
      {activeTab === 'export' && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="font-semibold mb-2">Export Your Data</h2>
            <p className="text-sm text-muted mb-4">
              Download a complete JSON export of your regulation data. The JSON
              contains readable sensitive content, so store it only in a
              location you trust and delete it when finished.
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

function OfflineOrientationManager() {
  const [values, setValues] = useState('');
  const [rules, setRules] = useState('');
  const [grounding, setGrounding] = useState('Wait 30 minutes before an irreversible action.');
  const [commitments, setCommitments] = useState('');
  const [pin, setPin] = useState('');
  const [consent, setConsent] = useState(false);
  const [regions, setRegions] = useState({ PH: true, US: true });
  const [stored, setStored] = useState(hasOfflineOrientation());
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const lines = (value: string) => value.split('\n').map((line) => line.trim()).filter(Boolean);

  const save = async () => {
    setError('');
    setMessage('');
    try {
      await saveOfflineOrientation({
        confirmedValues: lines(values),
        personalRules: lines(rules),
        groundingActions: lines(grounding),
        commitments: lines(commitments),
        safetyRegions: ([regions.PH && 'PH', regions.US && 'US'].filter(Boolean) as ('PH' | 'US')[]),
      }, pin, consent);
      setStored(true);
      setMessage('Encrypted offline snapshot saved on this device.');
    } catch (cause) {
      setError((cause as Error).message);
    }
  };

  const download = async () => {
    try {
      const content = await exportOfflineOrientation(pin);
      const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'pkm-offline-orientation.json';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError((cause as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <h2 className="font-semibold">Offline Orientation Snapshot</h2>
        <p className="text-sm text-muted">
          Store only what you deliberately confirm. The snapshot is encrypted with a device passphrase that the server never receives and cannot recover.
        </p>
        <p className="text-sm text-muted">
          This is an owner-reviewed device snapshot, not an automatically synchronized or canonical backend record. Review every line before saving.
        </p>
        {[
          ['Confirmed values', values, setValues],
          ['Personal rules', rules, setRules],
          ['Approved grounding actions', grounding, setGrounding],
          ['Active commitments', commitments, setCommitments],
        ].map(([label, value, setter]) => (
          <label key={label as string} className="block text-sm text-ink">
            {label as string} <span className="text-muted">(one per line)</span>
            <textarea className="textarea-field h-24 mt-1" value={value as string} onChange={(event) => (setter as (value: string) => void)(event.target.value)} />
          </label>
        ))}
        <fieldset>
          <legend className="text-sm text-ink">Cached safety regions</legend>
          <div className="flex gap-4 mt-2 text-sm">
            {(['PH', 'US'] as const).map((region) => (
              <label key={region} className="flex items-center gap-2">
                <input type="checkbox" checked={regions[region]} onChange={(event) => setRegions((current) => ({ ...current, [region]: event.target.checked }))} />
                {region === 'PH' ? 'Philippines' : 'United States'}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="block text-sm text-ink">
          Offline passphrase (14+ characters)
          <input className="input-field mt-1" type="password" autoComplete="new-password" value={pin} onChange={(event) => setPin(event.target.value)} />
        </label>
        <label className="flex items-start gap-2 text-sm text-ink">
          <input className="mt-1" type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          I consent to storing this encrypted snapshot and pending offline captures on this device.
        </label>
        {message && <StatusNotice variant="confirmation">{message}</StatusNotice>}
        {error && <StatusNotice variant="error">{error}</StatusNotice>}
        <button className="btn-primary w-full" onClick={() => void save()}>Save encrypted snapshot</button>
      </div>
      {stored && (
        <div className="card space-y-3">
          <p className="text-sm text-muted">An encrypted snapshot is stored on this browser.</p>
          <div className="flex gap-3">
            <button className="btn-secondary flex-1" onClick={() => void download()}>Export readable copy</button>
            <button className="btn-danger flex-1" onClick={() => { if (confirm('Delete the offline snapshot and pending captures from this device?')) { deleteOfflineOrientation(); setStored(false); } }}>Delete cache</button>
          </div>
        </div>
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
            Memory-only; removed when discarded or when the service restarts
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
          No sessions with active retention tracking.
        </p>
      )}
    </div>
  );
}
