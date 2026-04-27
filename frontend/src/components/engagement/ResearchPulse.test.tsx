import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ResearchPulse from './ResearchPulse';
import type { PulseData } from '@/types';

const mockActivity = { rated: 8, podcasts: 3, collected: 2, shared: 1, opened: 5, login_days: 3, news_viewed: 2, news_rated: 1, news_starred: 1 };

const mockPulse: PulseData = {
  unreviewed_count: 6,
  weekly_stats: mockActivity,
  weekly_points: 105,
  lifetime_points: 1280,
  streak: 5,
  best_streak: 5,
  lab_total_papers: 20,
  lab_reviewed: 14,
  lab_review_pct: 70.0,
  leaderboard: [
    { user_id: 'u1', full_name: 'Alice', points: 120, activity: { ...mockActivity, rated: 10 }, is_current_user: false },
    { user_id: 'u2', full_name: 'You', points: 105, activity: mockActivity, is_current_user: true },
    { user_id: 'u3', full_name: 'Bob', points: 30, activity: { ...mockActivity, rated: 3 }, is_current_user: false },
  ],
  week_start: '2026-04-13',
  prior_7d_points: 80,
  prior_7d_rated: 6,
};

let mockReturn = { data: mockPulse as PulseData | undefined, isLoading: false, isError: false };

vi.mock('@/hooks/useEngagement', () => ({
  useEngagement: () => mockReturn,
}));

vi.mock('@/stores/pulseSettingsStore', () => ({
  usePulseSettings: () => ({ showPulseCard: true }),
}));

describe('ResearchPulse Banner', () => {
  beforeEach(() => {
    mockReturn = { data: { ...mockPulse }, isLoading: false, isError: false };
    localStorage.clear();
  });

  it('renders banner with rank', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/#2 of 3/)).toBeInTheDocument();
  });

  it('shows points change vs last week', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/\+25 pts this week/)).toBeInTheDocument();
  });

  it('shows mini leaderboard on desktop', () => {
    render(<ResearchPulse />);
    // Top 3 names should be present (as first names)
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByText(/Bob/)).toBeInTheDocument();
  });

  it('expands to show detail on click', () => {
    render(<ResearchPulse />);
    // Click the banner
    fireEvent.click(screen.getByText(/#2 of 3/).closest('button')!);
    // Should now show streak and leaderboard label
    expect(screen.getByText(/streak/)).toBeInTheDocument();
    expect(screen.getByText('Leaderboard')).toBeInTheDocument();
  });

  it('shows points in sparkline area', () => {
    render(<ResearchPulse />);
    expect(screen.getAllByText(/pts/).length).toBeGreaterThanOrEqual(1);
  });
});
