import { FormEvent, useState } from 'react';
import * as api from '../api/client';
import { Button } from '../components/Button';
import { Field } from '../components/Field';
import { Surface } from '../components/Surface';

interface UnlockScreenProps {
  onUnlock: () => void;
}

export function UnlockScreen({ onUnlock }: UnlockScreenProps) {
  const [key, setKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!key.trim()) return;
    setLoading(true);
    setError('');
    try {
      await api.authenticate(key.trim());
      api.setApiKey(key.trim());
      onUnlock();
    } catch (cause) {
      setError((cause as api.ApiError).detail || 'Unable to unlock your PKM.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-paper safe-top safe-bottom flex items-center px-4">
      <div className="w-full max-w-sm mx-auto space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 mx-auto rounded-full bg-action-soft text-action flex items-center justify-center font-bold text-xl" aria-hidden="true">P</div>
          <h1 className="text-2xl font-bold text-ink">Your private workspace</h1>
          <p className="text-sm text-muted">Enter the owner access key configured on your VM.</p>
        </div>
        <Surface>
          <form className="space-y-4" onSubmit={submit}>
            <Field id="owner-key" label="Owner access key" error={error}>
              <input
                id="owner-key"
                type="password"
                autoComplete="current-password"
                value={key}
                onChange={(event) => setKey(event.target.value)}
                className="input-field"
                required
                autoFocus
              />
            </Field>
            <Button className="w-full" type="submit" loading={loading} disabled={!key.trim()}>
              Unlock
            </Button>
          </form>
        </Surface>
        <p className="text-center text-xs text-muted">The key is kept only for this browser tab and is sent only to your PKM.</p>
      </div>
    </main>
  );
}
