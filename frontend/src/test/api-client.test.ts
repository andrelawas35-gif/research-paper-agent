import { afterEach, describe, expect, it, vi } from 'vitest';
import { authenticate, isAuthenticated, lock } from '../api/client';

describe('owner authentication', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
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
      new Response(JSON.stringify({
        token: 'short-lived-session',
        expires_at: '2026-07-13T08:00:00Z',
        recent_auth_until: '2026-07-13T00:05:00Z',
      }), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      }),
    );

    await expect(authenticate('owner-key')).resolves.toBeUndefined();
    expect(isAuthenticated()).toBe(true);
    expect(sessionStorage.getItem('pkm_api_key')).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/auth/session', expect.objectContaining({
      method: 'POST',
      headers: { 'X-API-Key': 'owner-key' },
    }));
  });

  it('revokes and forgets the server session when the workspace locks', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: 'session-token' }), { status: 201 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    await authenticate('owner-key');

    await lock();

    expect(isAuthenticated()).toBe(false);
    expect(globalThis.fetch).toHaveBeenLastCalledWith('/api/auth/revoke', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer session-token' }),
    }));
  });
});
