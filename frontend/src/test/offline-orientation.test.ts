import { beforeEach, describe, expect, it } from 'vitest';
import {
  addDeferredCapture,
  deleteOfflineOrientation,
  exportOfflineOrientation,
  hasOfflineOrientation,
  loadOfflineOrientation,
  saveOfflineOrientation,
} from '../offline/orientationStore';

const snapshot = {
  confirmedValues: ['honesty', 'steadiness'],
  personalRules: ['Do not repeatedly ask the same question.'],
  groundingActions: ['Wait 30 minutes before an irreversible action.'],
  commitments: ['Finish the paper draft.'],
  safetyRegions: ['PH', 'US'] as ('PH' | 'US')[],
};

describe('encrypted offline orientation store', () => {
  beforeEach(() => localStorage.clear());

  it('stores only ciphertext and requires the owner PIN to inspect or export', async () => {
    await saveOfflineOrientation(snapshot, 'correct horse battery staple', true);

    expect(hasOfflineOrientation()).toBe(true);
    expect(JSON.stringify(localStorage)).not.toContain('honesty');
    await expect(loadOfflineOrientation('wrong pin')).rejects.toThrow('Unable to unlock');
    await expect(loadOfflineOrientation('correct horse battery staple')).resolves.toMatchObject(snapshot);
    await expect(exportOfflineOrientation('correct horse battery staple')).resolves.toContain('steadiness');
  });

  it('keeps deferred capture encrypted until the owner reviews it', async () => {
    await saveOfflineOrientation(snapshot, 'owner passphrase', true);
    await addDeferredCapture('Observed one sentence fact.', 'owner passphrase');

    expect(JSON.stringify(localStorage)).not.toContain('Observed one sentence fact.');
    const restored = await loadOfflineOrientation('owner passphrase');
    expect(restored.deferredCaptures).toHaveLength(1);
    expect(restored.deferredCaptures[0].text).toBe('Observed one sentence fact.');
  });

  it('does not cache without explicit consent and can be deleted completely', async () => {
    await expect(saveOfflineOrientation(snapshot, 'owner passphrase', false)).rejects.toThrow('consent');
    await saveOfflineOrientation(snapshot, 'owner passphrase', true);
    deleteOfflineOrientation();
    expect(hasOfflineOrientation()).toBe(false);
  });
});
