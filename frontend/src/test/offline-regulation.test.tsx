import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { OfflineRegulationProtocol } from '../pages/OfflineRegulationProtocol';
import { saveOfflineOrientation } from '../offline/orientationStore';

describe('OfflineRegulationProtocol', () => {
  beforeEach(() => localStorage.clear());

  it('bundles a usable memory-only flow and local safety references', () => {
    render(<OfflineRegulationProtocol />);

    expect(screen.getByText(/Nothing entered here is saved/i)).toBeInTheDocument();
    expect(screen.getByText(/Philippines: 911/i)).toBeInTheDocument();
    expect(screen.getByText(/United States: 911/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Trigger'), { target: { value: 'Observed fact' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('heading', { name: 'Known facts' })).toBeInTheDocument();
  });

  it('lets the owner inspect the consented snapshot and encrypt a deferred capture', async () => {
    await saveOfflineOrientation({
      confirmedValues: ['steadiness'],
      personalRules: ['Do not repeatedly ask the same question.'],
      groundingActions: ['Wait 30 minutes.'],
      commitments: ['Finish the draft.'],
      safetyRegions: ['PH'],
    }, 'offline passphrase', true);
    render(<OfflineRegulationProtocol />);

    fireEvent.change(screen.getByLabelText('Offline passphrase'), { target: { value: 'offline passphrase' } });
    fireEvent.click(screen.getByRole('button', { name: 'Unlock snapshot' }));
    await waitFor(() => expect(screen.getByText('steadiness')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('Deferred offline capture'), { target: { value: 'Review this later.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Encrypt for later review' }));
    await waitFor(() => expect(screen.getByText('Pending owner review: 1')).toBeInTheDocument());
    expect(localStorage.getItem('pkm_offline_orientation_v1')).not.toContain('Review this later.');
  });
});
