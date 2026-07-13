import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NowScreen } from '../pages/NowScreen';
import * as api from '../api/client';

vi.mock('../api/client', () => ({
  sessions: {
    list: vi.fn(),
    expire: vi.fn(),
  },
}));

describe('NowScreen private drafts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not invent a draft when the backend cannot confirm one', async () => {
    vi.mocked(api.sessions.list).mockRejectedValue(new Error('offline'));

    render(
      <MemoryRouter>
        <NowScreen />
      </MemoryRouter>,
    );

    await waitFor(() => expect(api.sessions.list).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Private draft available')).not.toBeInTheDocument();
  });

  it('shows a draft only when returned by the backend', async () => {
    vi.mocked(api.sessions.list).mockResolvedValue({
      count: 1,
      sessions: [
        {
          session_id: 'session-123',
          state: 'active',
          trigger_event: 'Private check-in',
          is_private: true,
          created_at: '2026-07-13T12:00:00Z',
          completed_at: null,
          safety_active: false,
          emotion_count: 0,
          fact_count: 1,
          action_count: 0,
        },
      ],
    });

    render(
      <MemoryRouter>
        <NowScreen />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Private draft available')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
  });
});
