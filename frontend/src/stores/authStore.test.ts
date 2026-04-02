import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock supabase before importing the store
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}));

import { useAuthStore } from './authStore';
import { supabase } from '@/lib/supabase';

describe('authStore', () => {
  beforeEach(() => {
    // Reset store state
    useAuthStore.setState({ user: null, session: null, loading: true });
    vi.clearAllMocks();
  });

  it('login sets user on success', async () => {
    const mockUser = { id: '123', email: 'test@test.com' };
    const mockSession = { access_token: 'token', user: mockUser };
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      data: { user: mockUser, session: mockSession },
      error: null,
    } as never);

    const result = await useAuthStore.getState().login('test@test.com', 'password');

    expect(result.error).toBeNull();
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().session).toEqual(mockSession);
  });

  it('login returns error on failure', async () => {
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValue({
      data: { user: null, session: null },
      error: { message: 'Invalid credentials' },
    } as never);

    const result = await useAuthStore.getState().login('bad@test.com', 'wrong');

    expect(result.error).toBe('Invalid credentials');
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('logout clears user', async () => {
    vi.mocked(supabase.auth.signOut).mockResolvedValue({ error: null } as never);

    // Set a user first
    useAuthStore.setState({
      user: { id: '123', email: 'test@test.com' } as never,
      session: { access_token: 'token' } as never,
    });

    await useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().session).toBeNull();
  });
});
