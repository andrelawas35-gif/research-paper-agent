import { Surface } from '../components/Surface';
import { Button } from '../components/Button';
import { Dialog } from '../components/Dialog';
import { AppNav } from '../components/Navigation';
import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import * as api from '../api/client';
import type { SessionSummary } from '../api/client';

export function NowScreen() {
  const navigate = useNavigate();
  const [discardOpen, setDiscardOpen] = useState(false);
  const [draft, setDraft] = useState<SessionSummary | null>(null);
  const [discardError, setDiscardError] = useState('');
  const [discarding, setDiscarding] = useState(false);

  useEffect(() => {
    let cancelled = false;

    void api.sessions
      .list()
      .then(({ sessions }) => {
        if (cancelled) return;
        const unfinishedDraft = sessions.find(
          (candidate) =>
            candidate.is_private &&
            candidate.completed_at === null &&
            candidate.state !== 'expired' &&
            candidate.state !== 'completed',
        );
        setDraft(unfinishedDraft ?? null);
      })
      .catch(() => {
        // A draft is optional orientation data. Do not imply one exists when
        // the authenticated backend cannot confirm it.
        if (!cancelled) setDraft(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const discardDraft = async () => {
    if (!draft) return;
    setDiscarding(true);
    setDiscardError('');
    try {
      await api.sessions.expire(draft.session_id);
      setDraft(null);
      setDiscardOpen(false);
    } catch (error) {
      const apiError = error as api.ApiError;
      setDiscardError(apiError.detail || 'The draft could not be discarded.');
    } finally {
      setDiscarding(false);
    }
  };

  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const date = new Date().toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });

  const navItems = [
    { label: 'Now', href: '/', active: true, icon: '○' },
    { label: 'Chat', href: '/chat', disabled: true, icon: '○' },
    { label: 'Work', href: '/work', disabled: true, icon: '○' },
    { label: 'Compass', href: '/compass', disabled: true, icon: '○' },
  ];

  return (
    <div className="max-w-lg mx-auto px-4 py-8 flex flex-col gap-6">

      {/* ── Orientation header ─────────────────────────────────── */}
      <header className="flex items-center justify-between">
        <div>
          <time className="text-2xl font-bold text-ink">{time}</time>
          <p className="text-sm text-muted">{date}</p>
        </div>
        <button
          type="button"
          className="w-10 h-10 rounded-full bg-action-soft flex items-center justify-center text-action font-bold text-lg"
          aria-label="Lock workspace"
          onClick={() => {
            api.clearApiKey();
            window.location.reload();
          }}
        >
          P
        </button>
      </header>

      {/* ── What Matters Today ─────────────────────────────────── */}
      <Surface>
        <p className="text-xs text-muted uppercase tracking-wide mb-2">What matters today</p>
        <p className="text-base text-ink/80 italic">
          "Build tools that help you think clearly and act deliberately."
        </p>
        <p className="text-xs text-muted mt-3">
          This is a static orientation marker. Confirmed values and active work will appear here when available.
        </p>
      </Surface>

      {/* ── Regulation Anchor ──────────────────────────────────── */}
      <button
        onClick={() => navigate('/regulation')}
        className="w-full bg-action text-surface rounded-panel p-6 text-left
                   transition-all duration-state ease-calm
                   hover:brightness-110 focus-visible:ring-3 focus-visible:ring-action
                   focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
        aria-label="Open Regulation mode"
      >
        <p className="text-xs text-action-soft mb-2 uppercase tracking-wide">Regulation</p>
        <p className="text-lg font-semibold">Work through something difficult</p>
        <p className="text-sm text-action-soft/80 mt-1">
          Private · Step by step · You control the pace
        </p>
      </button>

      {/* ── Private Regulation draft card ──────────────────────── */}
      {draft && (
        <>
          <Surface>
            <p className="text-xs text-muted uppercase tracking-wide mb-2">Unfinished session</p>
            <div className="flex flex-col gap-3">
              <div>
                <p className="text-sm font-semibold">Private draft available</p>
                <p className="text-xs text-muted">Memory-only · Not saved to durable history</p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" onClick={() => navigate(`/regulation?session=${draft.session_id}`)}>
                  Resume
                </Button>
                <Button variant="tertiary" onClick={() => setDiscardOpen(true)}>
                  Discard
                </Button>
              </div>
              {discardError && <p className="text-sm text-danger" role="alert">{discardError}</p>}
            </div>
          </Surface>

          <Dialog
            open={discardOpen}
            onConfirm={discardDraft}
            onCancel={() => setDiscardOpen(false)}
            title="Discard draft?"
            confirmLabel={discarding ? 'Discarding…' : 'Discard'}
            destructive
          >
            This removes the memory-only Regulation session. You can start a new one at any time.
          </Dialog>
        </>
      )}

      {/* ── Privacy link ───────────────────────────────────────── */}
      <div className="text-center pb-2">
        <button
          onClick={() => navigate('/privacy')}
          className="text-xs text-muted hover:text-ink transition-colors duration-inline"
        >
          Data & Privacy
        </button>
      </div>

      {/* ── Bottom navigation ──────────────────────────────────── */}
      <AppNav items={navItems} />
    </div>
  );
}
