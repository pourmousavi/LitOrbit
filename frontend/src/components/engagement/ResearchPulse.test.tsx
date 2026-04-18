import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ResearchPulse from './ResearchPulse';
import type { PulseData } from '@/types';

const mockPulse: PulseData = {
  unreviewed_count: 6,
  weekly_stats: { rated: 8, podcasts: 3, collected: 2, shared: 1, opened: 5, login_days: 3 },
  weekly_points: 105,
  streak: 5,
  best_streak: 5,
  lab_total_papers: 20,
  lab_reviewed: 14,
  lab_review_pct: 70.0,
  leaderboard: [
    { user_id: 'u1', full_name: 'Alice', points: 120, activity: { rated: 10, podcasts: 4, collected: 3, shared: 2, opened: 8, login_days: 4 }, is_current_user: false },
    { user_id: 'u2', full_name: 'You', points: 105, activity: { rated: 8, podcasts: 3, collected: 2, shared: 1, opened: 5, login_days: 3 }, is_current_user: true },
    { user_id: 'u3', full_name: 'Bob', points: 30, activity: { rated: 3, podcasts: 0, collected: 0, shared: 0, opened: 2, login_days: 2 }, is_current_user: false },
  ],
  week_start: '2026-04-13',
  last_week_points: 80,
  last_week_rated: 6,
};

let mockReturn = { data: mockPulse as PulseData | undefined, isLoading: false, isError: false };

vi.mock('@/hooks/useEngagement', () => ({
  useEngagement: () => mockReturn,
}));

vi.mock('@/stores/pulseSettingsStore', () => ({
  usePulseSettings: () => ({ showPulseCard: true }),
}));

describe('ResearchPulse', () => {
  beforeEach(() => {
    mockReturn = { data: { ...mockPulse }, isLoading: false, isError: false };
    localStorage.clear();
  });

  it('renders My Pulse tab by default', () => {
    render(<ResearchPulse />);
    expect(screen.getByText('My Pulse')).toBeInTheDocument();
    expect(screen.getByText('This week')).toBeInTheDocument();
  });

  it('shows ring gauge with percentage', () => {
    render(<ResearchPulse />);
    expect(screen.getByText('RATED')).toBeInTheDocument();
    // 8 of 14 = 57%
    expect(screen.getByText('57')).toBeInTheDocument();
  });

  it('shows streak strip', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/-day streak/)).toBeInTheDocument();
    expect(screen.getByText(/best 5d/)).toBeInTheDocument();
  });

  it('shows activity sparklets', () => {
    render(<ResearchPulse />);
    expect(screen.getByText('rated')).toBeInTheDocument();
    expect(screen.getByText('podcasts')).toBeInTheDocument();
    expect(screen.getByText('collected')).toBeInTheDocument();
  });

  it('shows nudge when unreviewed > 3', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/unrated/)).toBeInTheDocument();
  });

  it('does not show nudge when unreviewed <= 3', () => {
    mockReturn = { data: { ...mockPulse, unreviewed_count: 2 }, isLoading: false, isError: false };
    render(<ResearchPulse />);
    expect(screen.queryByText(/unrated/)).not.toBeInTheDocument();
  });

  it('switches to Lab Pulse and shows podium', () => {
    render(<ResearchPulse />);
    fireEvent.click(screen.getByText('Lab Pulse'));
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('Team progress')).toBeInTheDocument();
  });

  it('shows points in sparklets', () => {
    render(<ResearchPulse />);
    expect(screen.getByText('105')).toBeInTheDocument();
    expect(screen.getByText(/pts earned/)).toBeInTheDocument();
  });

  it('shows week number', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/WK \d+/)).toBeInTheDocument();
  });
});
