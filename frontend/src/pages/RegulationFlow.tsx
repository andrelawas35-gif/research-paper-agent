/**
 * RegulationFlow — Guided PWA Regulation check-in (U1).
 *
 * Implements the trigger → facts → interpretations → emotions →
 * urges → actions → outcome flow with explicit steps, progress
 * indicator, pause/resume, capture confirmation, offline rules,
 * and safety resources.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import * as api from '../api/client';
import type {
  RegulationSession,
  AssistResult,
  SafetyResources,
} from '../api/client';
import ProgressBar from '../components/ProgressBar';
import SafetyResourcesPanel from '../components/SafetyResourcesPanel';

// ── Step definitions ────────────────────────────────────────────────

const STEPS = [
  { id: 'trigger', label: 'Trigger', number: 1 },
  { id: 'safety', label: 'Safety', number: 2 },
  { id: 'facts', label: 'Facts', number: 3 },
  { id: 'interpret', label: 'Interpret', number: 4 },
  { id: 'emotions', label: 'Emotions', number: 5 },
  { id: 'urges', label: 'Urges', number: 6 },
  { id: 'actions', label: 'Actions', number: 7 },
  { id: 'outcome', label: 'Outcome', number: 8 },
] as const;

type StepId = (typeof STEPS)[number]['id'];

// ── Sub-components ──────────────────────────────────────────────────

function TriggerStep({
  onStart,
  loading,
  error,
}: {
  onStart: (text: string, isPrivate: boolean) => void;
  loading: boolean;
  error: string;
}) {
  const [text, setText] = useState('');
  const [isPrivate, setIsPrivate] = useState(false);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">What happened?</h2>
        <p className="text-muted text-sm">
          Describe the situation in one sentence. Focus on what a camera would
          have recorded — not your interpretation yet.
        </p>
      </div>

      <textarea
        className="textarea-field h-32"
        placeholder="E.g., I sent a message and haven't received a reply in six hours..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={loading}
      />

      <label className="flex items-center gap-3 text-sm text-muted">
        <input
          type="checkbox"
          checked={isPrivate}
          onChange={(e) => setIsPrivate(e.target.checked)}
          className="rounded bg-paper border-border"
        />
        Private Check-In — this session will not be saved to durable history
      </label>

      {error && (
        <div className="bg-danger/10/40 border border-danger rounded-control p-3 text-danger text-sm">
          {error}
        </div>
      )}

      <button
        className="btn-primary w-full"
        disabled={!text.trim() || loading}
        onClick={() => onStart(text.trim(), isPrivate)}
      >
        {loading ? 'Creating session...' : 'Begin Check-In'}
      </button>
    </div>
  );
}

function SafetyStep({
  session,
  onComplete,
  loading,
  error,
}: {
  session: RegulationSession;
  onComplete: (category: string) => void;
  loading: boolean;
  error: string;
}) {
  const [category, setCategory] = useState('none');
  const [resources, setResources] = useState<SafetyResources | null>(null);

  useEffect(() => {
    api.safety.getResources().then(setResources).catch(() => {});
  }, []);

  const categories = [
    { value: 'none', label: 'No safety concern', description: 'Continue to coaching' },
    { value: 'self_harm', label: 'Self-harm', description: 'Thoughts of harming yourself' },
    { value: 'violence', label: 'Violence', description: 'Thoughts of harming others' },
    { value: 'abuse', label: 'Abuse', description: 'Experiencing or at risk of abuse' },
    { value: 'immediate_danger', label: 'Immediate danger', description: 'Urgent safety risk' },
  ];

  const selectedCat = categories.find((c) => c.value === category);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">Safety Check</h2>
        <p className="text-muted text-sm">
          Before we continue, please let us know if any of the following apply.
          This helps route you to the right support.
        </p>
      </div>

      <div className="space-y-3">
        {categories.map((cat) => (
          <button
            key={cat.value}
            className={`w-full text-left p-4 rounded-control border transition-colors ${
              category === cat.value
                ? 'border-indigo-500 bg-action/10 text-indigo-200'
                : 'border-border bg-paper/50 text-ink hover:border-border'
            }`}
            onClick={() => setCategory(cat.value)}
          >
            <div className="font-medium">{cat.label}</div>
            <div className="text-sm text-muted">{cat.description}</div>
          </button>
        ))}
      </div>

      {selectedCat && selectedCat.value !== 'none' && resources && (
        <div className="bg-amber-900/30 border border-amber-800 rounded-control p-4">
          <SafetyResourcesPanel
            category={category}
            resources={resources.resources}
          />
        </div>
      )}

      {error && (
        <div className="bg-danger/10/40 border border-danger rounded-control p-3 text-danger text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button
          className="btn-primary flex-1"
          disabled={loading}
          onClick={() => onComplete(category)}
        >
          {loading ? 'Processing...' : 'Continue'}
        </button>
      </div>
    </div>
  );
}

function FactsStep({
  session,
  onComplete,
  loading,
}: {
  session: RegulationSession;
  onComplete: (facts: { text: string; certainty: number; source: string }[]) => void;
  loading: boolean;
}) {
  const [items, setItems] = useState<{ text: string; certainty: number }[]>(
    session.facts.length > 0
      ? session.facts.map((f) => ({ text: f.text, certainty: f.certainty }))
      : [{ text: '', certainty: 0.8 }],
  );

  const addItem = () => setItems([...items, { text: '', certainty: 0.8 }]);
  const removeItem = (i: number) => setItems(items.filter((_, idx) => idx !== i));
  const updateItem = (i: number, field: string, value: string | number) => {
    const updated = [...items];
    updated[i] = { ...updated[i], [field]: value };
    setItems(updated);
  };

  const validItems = items.filter((i) => i.text.trim());
  const hasItems = validItems.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">What are the facts?</h2>
        <p className="text-muted text-sm">
          List only what you know happened — what a camera would record.
          Separate these from what you think they mean.
        </p>
      </div>

      <div className="space-y-4">
        {items.map((item, i) => (
          <div key={i} className="card space-y-3">
            <div className="flex items-start justify-between gap-2">
              <textarea
                className="textarea-field h-20 flex-1"
                placeholder="E.g., I sent a message at 2pm and haven't received a reply..."
                value={item.text}
                onChange={(e) => updateItem(i, 'text', e.target.value)}
                disabled={loading}
              />
              {items.length > 1 && (
                <button
                  className="text-muted hover:text-danger p-1"
                  onClick={() => removeItem(i)}
                  aria-label="Remove fact"
                >
                  ✕
                </button>
              )}
            </div>
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted">Certainty:</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={item.certainty}
                onChange={(e) => updateItem(i, 'certainty', parseFloat(e.target.value))}
                className="flex-1 accent-indigo-500"
                disabled={loading}
              />
              <span className="text-sm text-ink w-8">
                {Math.round(item.certainty * 100)}%
              </span>
            </div>
          </div>
        ))}
      </div>

      <button
        className="btn-secondary w-full text-sm"
        onClick={addItem}
        disabled={loading}
      >
        + Add another fact
      </button>

      <button
        className="btn-primary w-full"
        disabled={!hasItems || loading}
        onClick={() =>
          onComplete(validItems.map((i) => ({ ...i, source: 'user_report' })))
        }
      >
        {loading ? 'Saving...' : 'Continue'}
      </button>
    </div>
  );
}

function InterpretationsStep({
  onComplete,
  loading,
}: {
  session: RegulationSession;
  onComplete: (
    interpretations: {
      text: string;
      plausibility: number;
      evidence_for: string[];
      evidence_against: string[];
    }[],
  ) => void;
  loading: boolean;
}) {
  const [items, setItems] = useState<
    { text: string; plausibility: number; evidenceFor: string; evidenceAgainst: string }[]
  >([{ text: '', plausibility: 0.5, evidenceFor: '', evidenceAgainst: '' }]);

  const addItem = () =>
    setItems([...items, { text: '', plausibility: 0.5, evidenceFor: '', evidenceAgainst: '' }]);
  const removeItem = (i: number) => setItems(items.filter((_, idx) => idx !== i));
  const updateItem = (i: number, field: string, value: string | number) => {
    const updated = [...items];
    updated[i] = { ...updated[i], [field]: value };
    setItems(updated);
  };

  const validItems = items.filter((i) => i.text.trim());

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">
          What could these facts mean?
        </h2>
        <p className="text-muted text-sm">
          Consider at least two interpretations — including one that does not
          assume bad intent. Rate how plausible each one feels.
        </p>
      </div>

      <div className="space-y-4">
        {items.map((item, i) => (
          <div key={i} className="card space-y-3">
            <div className="flex items-start justify-between gap-2">
              <textarea
                className="textarea-field h-20 flex-1"
                placeholder={`Interpretation ${i + 1}: Maybe they are...`}
                value={item.text}
                onChange={(e) => updateItem(i, 'text', e.target.value)}
                disabled={loading}
              />
              {items.length > 1 && (
                <button
                  className="text-muted hover:text-danger p-1"
                  onClick={() => removeItem(i)}
                  aria-label="Remove interpretation"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
              <label className="text-sm text-muted">Plausibility:</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={item.plausibility}
                onChange={(e) => updateItem(i, 'plausibility', parseFloat(e.target.value))}
                className="flex-1 accent-indigo-500"
                disabled={loading}
              />
              <span className="text-sm text-ink w-8">
                {Math.round(item.plausibility * 100)}%
              </span>
            </div>

            <input
              className="input-field text-sm"
              placeholder="Evidence for this interpretation..."
              value={item.evidenceFor}
              onChange={(e) => updateItem(i, 'evidenceFor', e.target.value)}
              disabled={loading}
            />
            <input
              className="input-field text-sm"
              placeholder="Evidence against this interpretation..."
              value={item.evidenceAgainst}
              onChange={(e) => updateItem(i, 'evidenceAgainst', e.target.value)}
              disabled={loading}
            />
          </div>
        ))}
      </div>

      <button
        className="btn-secondary w-full text-sm"
        onClick={addItem}
        disabled={loading}
      >
        + Add another interpretation
      </button>

      {validItems.length === 1 && (
        <div className="bg-amber-900/30 border border-amber-800 rounded-control p-3 text-amber-200 text-sm">
          Consider adding at least one more interpretation that doesn't assume bad
          intent. This helps avoid jumping to conclusions.
        </div>
      )}

      <button
        className="btn-primary w-full"
        disabled={validItems.length === 0 || loading}
        onClick={() =>
          onComplete(
            validItems.map((i) => ({
              text: i.text,
              plausibility: i.plausibility,
              evidence_for: i.evidenceFor
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean),
              evidence_against: i.evidenceAgainst
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean),
            })),
          )
        }
      >
        {loading ? 'Saving...' : 'Continue'}
      </button>
    </div>
  );
}

function EmotionsStep({
  onComplete,
  loading,
}: {
  session: RegulationSession;
  onComplete: (emotions: { label: string; intensity: number; description: string }[]) => void;
  loading: boolean;
}) {
  const EMOTIONS = [
    'anger', 'fear', 'sadness', 'jealousy', 'shame', 'guilt',
    'anxiety', 'frustration', 'hurt', 'disappointment', 'loneliness',
    'overwhelmed', 'confusion', 'numb', 'relief', 'hope', 'gratitude', 'other',
  ];

  const [selected, setSelected] = useState<Record<string, number>>({});

  const toggleEmotion = (label: string) => {
    setSelected((prev) => {
      const next = { ...prev };
      if (next[label]) {
        delete next[label];
      } else {
        next[label] = 5;
      }
      return next;
    });
  };

  const setIntensity = (label: string, intensity: number) => {
    setSelected((prev) => ({ ...prev, [label]: intensity }));
  };

  const selectedList = Object.entries(selected);
  const hasSelection = selectedList.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">What are you feeling?</h2>
        <p className="text-muted text-sm">
          Tap emotions that resonate, then adjust intensity. You can select
          multiple.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {EMOTIONS.map((emotion) => (
          <button
            key={emotion}
            className={`px-3 py-2 rounded-control text-sm font-medium transition-colors ${
              selected[emotion]
                ? 'bg-action text-white'
                : 'bg-paper text-muted hover:bg-slate-700'
            }`}
            onClick={() => toggleEmotion(emotion)}
            disabled={loading}
          >
            {emotion}
          </button>
        ))}
      </div>

      {selectedList.map(([label, intensity]) => (
        <div key={label} className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="font-medium capitalize">{label}</span>
            <span className="text-sm text-muted">{intensity}/10</span>
          </div>
          <input
            type="range"
            min="1"
            max="10"
            value={intensity}
            onChange={(e) => setIntensity(label, parseInt(e.target.value))}
            className="w-full accent-indigo-500"
            disabled={loading}
          />
        </div>
      ))}

      <button
        className="btn-primary w-full"
        disabled={!hasSelection || loading}
        onClick={() =>
          onComplete(
            selectedList.map(([label, intensity]) => ({
              label,
              intensity,
              description: '',
            })),
          )
        }
      >
        {loading ? 'Saving...' : 'Continue'}
      </button>
    </div>
  );
}

function UrgesStep({
  onComplete,
  loading,
}: {
  session: RegulationSession;
  onComplete: (urges: { text: string; strength: number }[]) => void;
  loading: boolean;
}) {
  const [items, setItems] = useState<{ text: string; strength: number }[]>(
    session.urges.length > 0
      ? session.urges.map((u) => ({ text: u.text, strength: u.strength }))
      : [{ text: '', strength: 5 }],
  );

  const addItem = () => setItems([...items, { text: '', strength: 5 }]);
  const removeItem = (i: number) => setItems(items.filter((_, idx) => idx !== i));
  const updateItem = (i: number, field: string, value: string | number) => {
    const updated = [...items];
    updated[i] = { ...updated[i], [field]: value };
    setItems(updated);
  };

  const validItems = items.filter((i) => i.text.trim());

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">
          What do you feel like doing?
        </h2>
        <p className="text-muted text-sm">
          Name your urges honestly — they are information, not instructions.
          No judgment.
        </p>
      </div>

      <div className="space-y-4">
        {items.map((item, i) => (
          <div key={i} className="card space-y-3">
            <div className="flex items-start justify-between gap-2">
              <textarea
                className="textarea-field h-20 flex-1"
                placeholder="E.g., Send another message asking why they haven't replied..."
                value={item.text}
                onChange={(e) => updateItem(i, 'text', e.target.value)}
                disabled={loading}
              />
              {items.length > 1 && (
                <button
                  className="text-muted hover:text-danger p-1"
                  onClick={() => removeItem(i)}
                  aria-label="Remove urge"
                >
                  ✕
                </button>
              )}
            </div>
            <div className="flex items-center gap-3">
              <label className="text-sm text-muted">Strength:</label>
              <input
                type="range"
                min="1"
                max="10"
                value={item.strength}
                onChange={(e) => updateItem(i, 'strength', parseInt(e.target.value))}
                className="flex-1 accent-indigo-500"
                disabled={loading}
              />
              <span className="text-sm text-ink w-6">{item.strength}</span>
            </div>
          </div>
        ))}
      </div>

      <button
        className="btn-secondary w-full text-sm"
        onClick={addItem}
        disabled={loading}
      >
        + Add another urge
      </button>

      <button
        className="btn-primary w-full"
        disabled={validItems.length === 0 || loading}
        onClick={() =>
          onComplete(validItems.map((i) => ({ text: i.text, strength: i.strength })))
        }
      >
        {loading ? 'Saving...' : 'Continue'}
      </button>
    </div>
  );
}

function ActionsStep({
  onComplete,
  assistResult,
  loading,
  skipAssist,
}: {
  session: RegulationSession;
  onComplete: (
    actions: { text: string; reversible: boolean; waiting_period_minutes: number }[],
  ) => void;
  assistResult: AssistResult | null;
  loading: boolean;
  skipAssist: () => void;
}) {
  const [items, setItems] = useState<
    { text: string; reversible: boolean; waitMinutes: number }[]
  >([{ text: '', reversible: true, waitMinutes: 15 }]);

  const addItem = () =>
    setItems([...items, { text: '', reversible: true, waitMinutes: 15 }]);
  const removeItem = (i: number) => setItems(items.filter((_, idx) => idx !== i));
  const updateItem = (i: number, field: string, value: string | number | boolean) => {
    const updated = [...items];
    updated[i] = { ...updated[i], [field]: value };
    setItems(updated);
  };

  const validItems = items.filter((i) => i.text.trim());

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-2">
          What will you do?
        </h2>
        <p className="text-muted text-sm">
          Choose actions aligned with your values and long-term wellbeing.
          Consider waiting before acting on strong emotions.
        </p>
      </div>

      {assistResult && !assistResult.is_degraded && assistResult.model_response && (
        <div className="bg-indigo-900/20 border border-indigo-800 rounded-control p-4">
          <h3 className="text-sm font-semibold text-action mb-2">
            AI Suggestions
          </h3>
          <p className="text-sm text-ink whitespace-pre-wrap">
            {(assistResult.model_response as Record<string, unknown>).uncertainty as string || ''}
          </p>
        </div>
      )}

      {assistResult?.is_degraded && (
        <div className="bg-amber-900/20 border border-amber-800 rounded-control p-4">
          <p className="text-sm text-amber-200">
            AI assistance is unavailable. The offline protocol is active —
            your own judgment is the guide here.
          </p>
          <button className="btn-secondary mt-3 text-sm" onClick={skipAssist}>
            Dismiss
          </button>
        </div>
      )}

      <div className="space-y-4">
        {items.map((item, i) => (
          <div key={i} className="card space-y-3">
            <div className="flex items-start justify-between gap-2">
              <textarea
                className="textarea-field h-20 flex-1"
                placeholder="E.g., Wait until tomorrow before deciding how to respond..."
                value={item.text}
                onChange={(e) => updateItem(i, 'text', e.target.value)}
                disabled={loading}
              />
              {items.length > 1 && (
                <button
                  className="text-muted hover:text-danger p-1"
                  onClick={() => removeItem(i)}
                  aria-label="Remove action"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex items-center gap-3 text-sm">
              <label className="flex items-center gap-2 text-muted">
                <input
                  type="checkbox"
                  checked={item.reversible}
                  onChange={(e) => updateItem(i, 'reversible', e.target.checked)}
                  className="rounded bg-paper border-border"
                  disabled={loading}
                />
                Reversible
              </label>
              <label className="text-muted">
                Wait{' '}
                <input
                  type="number"
                  min="0"
                  max="1440"
                  value={item.waitMinutes}
                  onChange={(e) => updateItem(i, 'waitMinutes', parseInt(e.target.value) || 0)}
                  className="w-16 bg-paper border border-border rounded px-2 py-1 text-ink"
                  disabled={loading}
                />{' '}
                min
              </label>
            </div>
          </div>
        ))}
      </div>

      <button
        className="btn-secondary w-full text-sm"
        onClick={addItem}
        disabled={loading}
      >
        + Add another action
      </button>

      <button
        className="btn-primary w-full"
        disabled={validItems.length === 0 || loading}
        onClick={() =>
          onComplete(
            validItems.map((i) => ({
              text: i.text,
              reversible: i.reversible,
              waiting_period_minutes: i.waitMinutes,
            })),
          )
        }
      >
        {loading ? 'Completing...' : 'Complete Check-In'}
      </button>
    </div>
  );
}

function OutcomeStep({
  session,
  onComplete,
  loading,
}: {
  session: RegulationSession;
  onComplete: (outcomes: { text: string; was_helpful: boolean | null }[]) => void;
  loading: boolean;
}) {
  const [text, setText] = useState('');
  const [wasHelpful, setWasHelpful] = useState<boolean | null>(null);

  return (
    <div className="space-y-6 text-center">
      <div className="text-4xl mb-4">✅</div>
      <h2 className="text-xl font-semibold">Check-in complete</h2>
      <p className="text-muted text-sm">
        Great job working through this. How did it go? Recording the outcome
        helps you learn what works for you.
      </p>

      <textarea
        className="textarea-field h-24"
        placeholder="What happened after you took action? (optional)"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={loading}
      />

      <div className="flex justify-center gap-3">
        <button
          className={`px-6 py-2 rounded-control font-medium transition-colors ${
            wasHelpful === true
              ? 'bg-action text-white'
              : 'bg-paper text-muted hover:bg-slate-700'
          }`}
          onClick={() => setWasHelpful(true)}
          disabled={loading}
        >
          Helpful
        </button>
        <button
          className={`px-6 py-2 rounded-control font-medium transition-colors ${
            wasHelpful === false
              ? 'bg-red-600 text-white'
              : 'bg-paper text-muted hover:bg-slate-700'
          }`}
          onClick={() => setWasHelpful(false)}
          disabled={loading}
        >
          Not helpful
        </button>
      </div>

      <button
        className="btn-primary w-full"
        disabled={loading}
        onClick={() =>
          onComplete(
            text.trim()
              ? [{ text: text.trim(), was_helpful: wasHelpful }]
              : [],
          )
        }
      >
        {loading ? 'Saving...' : 'Finish'}
      </button>

      <Link
        to="/regulation"
        className="block text-sm text-muted hover:text-ink"
      >
        Skip — I'll record the outcome later
      </Link>
    </div>
  );
}

function CompletedView({ session }: { session: RegulationSession }) {
  return (
    <div className="space-y-6 text-center">
      <div className="text-5xl mb-4">🎯</div>
      <h2 className="text-xl font-semibold">You're all set</h2>
      <p className="text-muted">
        Your check-in has been saved. Here's a summary:
      </p>

      <div className="card text-left space-y-2 text-sm">
        <p>
          <span className="text-muted">Trigger:</span>{' '}
          {session.trigger_event}
        </p>
        {session.facts.length > 0 && (
          <p>
            <span className="text-muted">Facts:</span>{' '}
            {session.facts.length} recorded
          </p>
        )}
        {session.emotions.length > 0 && (
          <p>
            <span className="text-muted">Emotions:</span>{' '}
            {session.emotions.map((e) => e.label).join(', ')}
          </p>
        )}
        {session.actions.length > 0 && (
          <p>
            <span className="text-muted">Actions:</span>{' '}
            {session.actions.map((a) => a.text).join('; ')}
          </p>
        )}
        {session.is_private && (
          <p className="text-amber-300 text-xs">
            This was a Private Check-In — not saved to durable history.
          </p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <Link to="/regulation" className="btn-primary text-center">
          New Check-In
        </Link>
        <Link to="/privacy" className="btn-secondary text-center">
          Data & Privacy Center
        </Link>
      </div>
    </div>
  );
}

// ── Main RegulationFlow component ────────────────────────────────────

export default function RegulationFlow() {
  const navigate = useNavigate();

  const [currentStep, setCurrentStep] = useState<StepId>('trigger');
  const [session, setSession] = useState<RegulationSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [assistResult, setAssistResult] = useState<AssistResult | null>(null);
  const [isComplete, setIsComplete] = useState(false);

  // Reset state for new flow
  const resetFlow = useCallback(() => {
    setCurrentStep('trigger');
    setSession(null);
    setLoading(false);
    setError('');
    setAssistResult(null);
    setIsComplete(false);
  }, []);

  // Handle trigger step
  const handleStart = async (triggerEvent: string, isPrivate: boolean) => {
    setLoading(true);
    setError('');
    try {
      const sess = await api.sessions.create(triggerEvent, isPrivate);
      setSession(sess);
      setCurrentStep('safety');
    } catch (e: unknown) {
      const apiErr = e as api.ApiError;
      setError(apiErr.detail || 'Failed to create session. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  // Handle safety screen
  const handleSafety = async (category: string) => {
    if (!session) return;
    setLoading(true);
    setError('');
    try {
      const result = await api.sessions.completeSafetyScreen(
        session.session_id,
        category,
      );
      const updated = await api.sessions.get(session.session_id);
      setSession(updated);
      if (result.safety_category !== 'none') {
        // Show safety resources and stay on safety step
        setLoading(false);
        return;
      }
      setCurrentStep('facts');
    } catch (e: unknown) {
      const apiErr = e as api.ApiError;
      setError(apiErr.detail || 'Failed to complete safety screen');
    } finally {
      setLoading(false);
    }
  };

  // Handle facts
  const handleFacts = async (
    facts: { text: string; certainty: number; source: string }[],
  ) => {
    if (!session) return;
    setLoading(true);
    try {
      const updated = await api.sessions.recordFacts(session.session_id, facts);
      setSession(updated);
      setCurrentStep('interpret');
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to save facts');
    } finally {
      setLoading(false);
    }
  };

  // Handle interpretations
  const handleInterpretations = async (
    interpretations: {
      text: string;
      plausibility: number;
      evidence_for: string[];
      evidence_against: string[];
    }[],
  ) => {
    if (!session) return;
    setLoading(true);
    try {
      const updated = await api.sessions.recordInterpretations(
        session.session_id,
        interpretations,
      );
      setSession(updated);
      setCurrentStep('emotions');
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to save interpretations');
    } finally {
      setLoading(false);
    }
  };

  // Handle emotions
  const handleEmotions = async (
    emotions: { label: string; intensity: number; description: string }[],
  ) => {
    if (!session) return;
    setLoading(true);
    try {
      const updated = await api.sessions.recordEmotions(
        session.session_id,
        emotions,
      );
      setSession(updated);
      setCurrentStep('urges');
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to save emotions');
    } finally {
      setLoading(false);
    }
  };

  // Handle urges
  const handleUrges = async (urges: { text: string; strength: number }[]) => {
    if (!session) return;
    setLoading(true);
    try {
      const updated = await api.sessions.recordUrges(session.session_id, urges);
      setSession(updated);

      // Try to get AI assistance for the actions step
      try {
        const assist = await api.sessions.assist(session.session_id);
        setAssistResult(assist);
      } catch {
        // AI assistance failure is non-blocking
        setAssistResult(null);
      }

      setCurrentStep('actions');
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to save urges');
    } finally {
      setLoading(false);
    }
  };

  // Handle actions + complete
  const handleActions = async (
    actions: { text: string; reversible: boolean; waiting_period_minutes: number }[],
  ) => {
    if (!session) return;
    setLoading(true);
    try {
      await api.sessions.recordActions(session.session_id, actions);
      await api.sessions.complete(session.session_id, actions);
      const updated = await api.sessions.get(session.session_id);
      setSession(updated);
      setCurrentStep('outcome');
    } catch (e: unknown) {
      setError((e as api.ApiError).detail || 'Failed to complete session');
    } finally {
      setLoading(false);
    }
  };

  // Handle outcome
  const handleOutcome = async (
    outcomes: { text: string; was_helpful: boolean | null }[],
  ) => {
    if (!session) return;
    if (outcomes.length === 0) {
      setIsComplete(true);
      return;
    }
    setLoading(true);
    try {
      await api.sessions.recordOutcomes(session.session_id, outcomes);
      const updated = await api.sessions.get(session.session_id);
      setSession(updated);
      setIsComplete(true);
    } catch {
      setIsComplete(true); // proceed even if outcome recording fails
    } finally {
      setLoading(false);
    }
  };

  const stepIndex = STEPS.findIndex((s) => s.id === currentStep);
  const progress = isComplete ? 100 : (stepIndex / (STEPS.length - 1)) * 100;

  return (
    <div className="max-w-lg mx-auto px-4 py-6 safe-bottom">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          className="text-muted hover:text-ink text-sm"
          onClick={() => {
            if (isComplete || currentStep === 'trigger') {
              navigate('/');
            } else {
              resetFlow();
            }
          }}
        >
          ← {currentStep === 'trigger' ? 'Home' : 'Start over'}
        </button>
        <h1 className="text-lg font-semibold">Regulation Check-In</h1>
        <div className="w-12" /> {/* spacer */}
      </div>

      {/* Progress bar */}
      {!isComplete && (
        <div className="mb-6">
          <ProgressBar
            steps={STEPS}
            currentStep={currentStep}
            completed={isComplete}
          />
        </div>
      )}

      {/* Step content */}
      <div className="min-h-[400px]">
        {isComplete && session ? (
          <CompletedView session={session} />
        ) : (
          <>
            {currentStep === 'trigger' && (
              <TriggerStep onStart={handleStart} loading={loading} error={error} />
            )}
            {currentStep === 'safety' && session && (
              <SafetyStep
                session={session}
                onComplete={handleSafety}
                loading={loading}
                error={error}
              />
            )}
            {currentStep === 'facts' && session && (
              <FactsStep
                session={session}
                onComplete={handleFacts}
                loading={loading}
              />
            )}
            {currentStep === 'interpret' && session && (
              <InterpretationsStep
                session={session}
                onComplete={handleInterpretations}
                loading={loading}
              />
            )}
            {currentStep === 'emotions' && session && (
              <EmotionsStep
                session={session}
                onComplete={handleEmotions}
                loading={loading}
              />
            )}
            {currentStep === 'urges' && session && (
              <UrgesStep
                session={session}
                onComplete={handleUrges}
                loading={loading}
              />
            )}
            {currentStep === 'actions' && session && (
              <ActionsStep
                session={session}
                onComplete={handleActions}
                assistResult={assistResult}
                loading={loading}
                skipAssist={() => setAssistResult(null)}
              />
            )}
            {currentStep === 'outcome' && session && (
              <OutcomeStep
                session={session}
                onComplete={handleOutcome}
                loading={loading}
              />
            )}
          </>
        )}
      </div>

      {/* Pause / Resume */}
      {!isComplete && currentStep !== 'trigger' && session && (
        <div className="mt-8 pt-4 border-t border-border text-center">
          <p className="text-xs text-muted">
            Session {session.session_id.slice(0, 8)}... •
            {session.is_private ? ' Private' : ' Saved'} •
            Step {stepIndex + 1} of {STEPS.length}
          </p>
          <p className="text-xs text-slate-600 mt-1">
            You can close this page and come back — your progress is preserved.
          </p>
        </div>
      )}
    </div>
  );
}
