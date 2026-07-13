import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { OfflineRegulationProtocol } from '../pages/OfflineRegulationProtocol';

describe('OfflineRegulationProtocol', () => {
  it('bundles a usable memory-only flow and local safety references', () => {
    render(<OfflineRegulationProtocol />);

    expect(screen.getByText(/Nothing entered here is saved/i)).toBeInTheDocument();
    expect(screen.getByText(/Philippines: 911/i)).toBeInTheDocument();
    expect(screen.getByText(/United States: 911/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Trigger'), { target: { value: 'Observed fact' } });
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(screen.getByRole('heading', { name: 'Known facts' })).toBeInTheDocument();
  });
});
