import { Surface, Row } from '../components/Surface';
import { Button } from '../components/Button';
import { StatusNotice } from '../components/StatusNotice';
import { Dialog } from '../components/Dialog';
import { AppNav } from '../components/Navigation';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

interface NowScreenProps {
  offline: boolean;
  degraded: boolean;
}

export function NowScreen({ offline, degraded }: NowScreenProps) {
  const navigate = useNavigate();
  const [discardOpen, setDiscardOpen] = useState(false);

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
        <div className="w-10 h-10 rounded-full bg-action-soft flex items-center justify-center text-action font-bold text-lg" aria-label="Profile">
          P
        </div>
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
      <Surface>
        <p className="text-xs text-muted uppercase tracking-wide mb-2">Unfinished session</p>
        <div className="flex flex-col gap-3">
          <div>
            <p className="text-sm font-semibold">Private draft available</p>
            <p className="text-xs text-muted">Saved earlier today</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => navigate('/regulation')}>
              Resume
            </Button>
            <Button variant="tertiary" onClick={() => navigate('/regulation?action=retention')}>
              Change retention
            </Button>
            <Button variant="tertiary" onClick={() => setDiscardOpen(true)}>
              Discard
            </Button>
          </div>
        </div>
      </Surface>

      <Dialog
        open={discardOpen}
        onConfirm={() => { setDiscardOpen(false); /* TODO: call session.expire */ }}
        onCancel={() => setDiscardOpen(false)}
        title="Discard draft?"
        confirmLabel="Discard"
        destructive
      >
        This will permanently remove the unfinished Regulation session. You can start a new one at any time.
      </Dialog>

      {/* ── Action rows ────────────────────────────────────────── */}
      <Surface>
        <Row label="Capture a thought">
          <Button variant="tertiary">→</Button>
        </Row>
        <Row label="Continue work">
          <Button variant="tertiary">→</Button>
        </Row>
        <Row label="Study">
          <Button variant="tertiary">→</Button>
        </Row>
      </Surface>

      {/* ── Capability notice ──────────────────────────────────── */}
      {(offline || degraded) && (
        <StatusNotice variant={offline ? 'caution' : 'capability'}>
          {offline
            ? 'Offline — local protocols and safety resources are available.'
            : 'Model assistance paused — local protocol available.'}
        </StatusNotice>
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
