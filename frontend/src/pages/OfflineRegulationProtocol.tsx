import { useState } from 'react';
import { Button } from '../components/Button';
import { StatusNotice } from '../components/StatusNotice';
import { Surface } from '../components/Surface';
import {
  addDeferredCapture,
  deleteOfflineOrientation,
  exportOfflineOrientation,
  hasOfflineOrientation,
  loadOfflineOrientation,
  type OfflineOrientation,
} from '../offline/orientationStore';

const STEPS = [
  ['Trigger', 'What happened in one sentence? Use only what a camera could record.'],
  ['Known facts', 'What do you know for certain? Separate observations from assumptions.'],
  ['Story', 'What are you afraid this means? Add one interpretation that does not assume bad intent.'],
  ['Emotion and urge', 'Name the strongest emotion and what you want to do immediately.'],
  ['Best next action', 'Choose one reversible action that protects tomorrow, then wait at least 30 minutes before anything irreversible.'],
] as const;

export function OfflineRegulationProtocol() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<string[]>(() => STEPS.map(() => ''));
  const [pin, setPin] = useState('');
  const [orientation, setOrientation] = useState<OfflineOrientation | null>(null);
  const [orientationError, setOrientationError] = useState('');
  const [pendingText, setPendingText] = useState('');

  const update = (value: string) => {
    setAnswers((current) => current.map((answer, index) => (index === step ? value : answer)));
  };

  const unlockOrientation = async () => {
    try {
      setOrientation(await loadOfflineOrientation(pin));
      setOrientationError('');
    } catch (cause) {
      setOrientationError((cause as Error).message);
    }
  };

  const deferCapture = async () => {
    try {
      await addDeferredCapture(pendingText, pin);
      setOrientation(await loadOfflineOrientation(pin));
      setPendingText('');
      setOrientationError('');
    } catch (cause) {
      setOrientationError((cause as Error).message);
    }
  };

  const downloadOrientation = async () => {
    try {
      const content = await exportOfflineOrientation(pin);
      const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'pkm-offline-orientation.json';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setOrientationError((cause as Error).message);
    }
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 safe-bottom space-y-5">
      <StatusNotice variant="caution">
        Offline protocol. Nothing entered here is saved or sent anywhere.
      </StatusNotice>

      <Surface>
        <h2 className="font-semibold text-ink">If safety is at risk</h2>
        <p className="text-sm text-muted mt-2">
          This PKM is not emergency infrastructure. For immediate danger call local emergency services.
        </p>
        <ul className="text-sm text-ink mt-3 space-y-1">
          <li>Philippines: 911 · NCMH crisis line 1553</li>
          <li>United States: 911 · call or text 988</li>
          <li>Elsewhere: findahelpline.com</li>
        </ul>
      </Surface>

      {hasOfflineOrientation() && (
        <Surface>
          <h2 className="font-semibold text-ink">Your offline orientation</h2>
          {!orientation ? (
            <div className="space-y-3 mt-3">
              <p className="text-sm text-muted">Unlock the encrypted snapshot stored on this device.</p>
              <input aria-label="Offline passphrase" className="input-field" type="password" autoComplete="current-password" value={pin} onChange={(event) => setPin(event.target.value)} />
              <Button onClick={() => void unlockOrientation()} disabled={pin.length < 8}>Unlock snapshot</Button>
            </div>
          ) : (
            <div className="space-y-3 mt-3 text-sm">
              {[
                ['Values', orientation.confirmedValues],
                ['Rules', orientation.personalRules],
                ['Grounding actions', orientation.groundingActions],
                ['Commitments', orientation.commitments],
              ].map(([label, items]) => (
                <div key={label as string}>
                  <h3 className="font-medium text-ink">{label as string}</h3>
                  {(items as string[]).length ? <ul className="list-disc pl-5 text-muted">{(items as string[]).map((item) => <li key={item}>{item}</li>)}</ul> : <p className="text-muted">None cached.</p>}
                </div>
              ))}
              <p className="text-muted">Pending owner review: {orientation.deferredCaptures.length}</p>
              <textarea aria-label="Deferred offline capture" className="textarea-field h-24" placeholder="Optional note to review when you are back online" value={pendingText} onChange={(event) => setPendingText(event.target.value)} />
              <div className="flex gap-2">
                <Button onClick={() => void deferCapture()} disabled={!pendingText.trim()}>Encrypt for later review</Button>
                <Button variant="secondary" onClick={() => void downloadOrientation()}>Export</Button>
              </div>
            </div>
          )}
          {orientationError && <p role="alert" className="text-sm text-danger mt-3">{orientationError}</p>}
          <button className="text-sm text-danger mt-4" onClick={() => { if (confirm('Delete the offline snapshot and pending captures from this device?')) { deleteOfflineOrientation(); setOrientation(null); } }}>Delete offline data</button>
        </Surface>
      )}

      <div className="flex gap-1" aria-label={`Step ${step + 1} of ${STEPS.length}`}>
        {STEPS.map((_, index) => (
          <div key={index} className={`h-1 flex-1 rounded-full ${index <= step ? 'bg-action' : 'bg-border'}`} />
        ))}
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">Step {step + 1} of {STEPS.length}</p>
          <h1 className="text-xl font-semibold text-ink mt-1">{STEPS[step][0]}</h1>
          <p className="text-sm text-muted mt-2">{STEPS[step][1]}</p>
        </div>
        <textarea
          className="textarea-field h-36"
          value={answers[step]}
          onChange={(event) => update(event.target.value)}
          autoFocus
          aria-label={STEPS[step][0]}
        />
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}>
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button className="flex-1" onClick={() => setStep((current) => current + 1)} disabled={!answers[step].trim()}>
              Continue
            </Button>
          ) : (
            <Button className="flex-1" onClick={() => { setAnswers(STEPS.map(() => '')); setStep(0); }} disabled={!answers[step].trim()}>
              Clear and finish
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
