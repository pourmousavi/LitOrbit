import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ResearchPulse from './ResearchPulse';
import type { PulseData } from '@/types';

// Mock useEngagement hook
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
    expect(screen.getByText(/8\/14 rated/)).toBeInTheDocument();
  });

  it('shows progress bar with correct percentage', () => {
    render(<ResearchPulse />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '57');
  });

  it('shows streak count', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/5-day streak/)).toBeInTheDocument();
  });

  it('shows activity breakdown', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/8 rated/)).toBeInTheDocument();
    expect(screen.getByText(/3 podcasts/)).toBeInTheDocument();
    expect(screen.getByText(/2 collected/)).toBeInTheDocument();
  });

  it('shows piling up warning when unreviewed > 3', () => {
    render(<ResearchPulse />);
    expect(screen.getByText(/6 papers piling up/)).toBeInTheDocument();
  });

  it('does not show piling up warning when unreviewed <= 3', () => {
    mockReturn = { data: { ...mockPulse, unreviewed_count: 2 }, isLoading: false, isError: false };
    render(<ResearchPulse />);
    expect(screen.queryByText(/piling up/)).not.toBeInTheDocument();
  });

  it('switches to Lab Pulse tab and shows leaderboard', () => {
    render(<ResearchPulse />);
    fireEvent.click(screen.getByText('Lab Pulse'));
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText(/70%/)).toBeInTheDocument();
  });

  it('highlights current user in leaderboard', () => {
    render(<ResearchPulse />);
    fireEvent.click(screen.getByText('Lab Pulse'));
    const currentUserRow = screen.getByTestId('leaderboard-current-user');
    expect(currentUserRow).toBeInTheDocument();
    expect(currentUserRow.textContent).toContain('You');
  });

  it('collapsed mode shows summary line', () => {
    localStorage.setItem('litorbit-pulse-collapsed', 'true');
    render(<ResearchPulse />);
    expect(screen.getByText(/8\/14 rated/)).toBeInTheDocument();
    expect(screen.getByText(/#2 in lab/)).toBeInTheDocument();
  });

  it('collapse persists to localStorage', () => {
    render(<ResearchPulse />);
    // Click the collapse (chevron up) button
    const buttons = screen.getAllByRole('button');
    const collapseBtn = buttons.find((b) => b.querySelector('svg.lucide-chevron-up'));
    if (collapseBtn) fireEvent.click(collapseBtn);
    expect(localStorage.getItem('litorbit-pulse-collapsed')).toBe('true');
  });
});
