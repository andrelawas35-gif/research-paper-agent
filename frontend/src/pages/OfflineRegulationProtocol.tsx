import { useState } from 'react';
import { Button } from '../components/Button';
import { StatusNotice } from '../components/StatusNotice';
import { Surface } from '../components/Surface';

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

  const update = (value: string) => {
    setAnswers((current) => current.map((answer, index) => (index === step ? value : answer)));
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
