import { afterEach, describe, expect, it, vi } from 'vitest';
import { authenticate } from '../api/client';

describe('owner authentication', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('rejects a 200 response that is not an authenticated API response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('<!doctype html>', {
        status: 200,
        headers: { 'content-type': 'text/html' },
      }),
    );

    await expect(authenticate('not-a-key')).rejects.toMatchObject({
      detail: 'Unable to verify access.',
    });
  });

  it('accepts only the explicit authenticated response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ authenticated: true, owner_id: 'owner' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );

    await expect(authenticate('owner-key')).resolves.toBeUndefined();
  });
});
