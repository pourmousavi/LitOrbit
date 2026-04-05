import { create } from 'zustand';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import api from '@/lib/api';

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ error: string | null }>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  session: null,
  loading: true,

  login: async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) {
      return { error: error.message };
    }
    set({ user: data.user, session: data.session });
    // Record login event (fire and forget)
    api.post('/api/v1/users/login-event').catch(() => {});
    return { error: null };
  },

  logout: async () => {
    await supabase.auth.signOut();
    set({ user: null, session: null });
  },

  initialize: async () => {
    const { data } = await supabase.auth.getSession();
    set({
      user: data.session?.user ?? null,
      session: data.session,
      loading: false,
    });

    // Debounced login ping on session restore (once per hour)
    if (data.session) {
      const lastPing = localStorage.getItem('litorbit-last-login-ping');
      const now = Date.now();
      if (!lastPing || now - Number(lastPing) > 3600000) {
        api.post('/api/v1/users/login-event').catch(() => {});
        localStorage.setItem('litorbit-last-login-ping', String(now));
      }
    }

    supabase.auth.onAuthStateChange((_event, session) => {
      set({
        user: session?.user ?? null,
        session,
      });
    });
  },
}));
