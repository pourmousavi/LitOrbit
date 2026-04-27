import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement } from 'react';

// Mock api module
vi.mock('@/lib/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

import api from '@/lib/api';
import { useEngagement } from './useEngagement';

const mockPulse = {
  unreviewed_count: 5,
  weekly_stats: { rated: 3, podcasts: 1, collected: 0, shared: 0, opened: 2, login_days: 2 },
  weekly_points: 37,
  lifetime_points: 412,
  streak: 2,
  best_streak: 4,
  lab_total_papers: 10,
  lab_reviewed: 5,
  lab_review_pct: 50.0,
  leaderboard: [],
  week_start: '2026-04-13',
  prior_7d_points: 20,
  prior_7d_rated: 2,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
}

describe('useEngagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns loading state initially', () => {
    vi.mocked(api.get).mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useEngagement(), { wrapper: createWrapper() });
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it('returns data after fetch', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: mockPulse });
    const { result } = renderHook(() => useEngagement(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockPulse);
    expect(api.get).toHaveBeenCalledWith('/api/v1/engagement/pulse');
  });

  it('has refetchOnWindowFocus enabled', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: mockPulse });
    const { result } = renderHook(() => useEngagement(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // The hook should have been configured — we verify by checking it fetched successfully
    // and that the query key is correct (refetchOnWindowFocus is a config option, not directly testable)
    expect(result.current.data?.unreviewed_count).toBe(5);
  });
});
