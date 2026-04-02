import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PaperCard from './PaperCard';
import type { Paper } from '@/types';

const mockPaper: Paper = {
  id: '1',
  doi: '10.1000/test',
  title: 'A Novel Approach to Battery Degradation Modelling',
  authors: ['A. Smith', 'B. Jones', 'C. Lee'],
  abstract: 'We propose a physics-informed neural network for battery degradation prediction.',
  full_text: null,
  journal: 'Applied Energy',
  journal_source: 'scopus',
  published_date: '2024-03-15',
  early_access: false,
  url: 'https://example.com',
  pdf_path: null,
  categories: ['battery', 'degradation', 'machine learning'],
  summary: null,
  relevance_score: 8.5,
  score_reasoning: 'Highly relevant',
  created_at: '2024-03-15T00:00:00Z',
};

describe('PaperCard', () => {
  it('renders with mock paper data, shows title, score, journal', () => {
    render(<PaperCard paper={mockPaper} />);

    expect(screen.getByText(mockPaper.title)).toBeInTheDocument();
    expect(screen.getByText('Applied Energy')).toBeInTheDocument();
    expect(screen.getByText('8.5')).toBeInTheDocument();
  });

  it('shows green score colour for score >= 8', () => {
    render(<PaperCard paper={{ ...mockPaper, relevance_score: 8.5 }} />);
    const scoreBadge = screen.getByText('8.5');
    expect(scoreBadge.className).toContain('score-high');
  });

  it('shows amber score colour for score 5-7', () => {
    render(<PaperCard paper={{ ...mockPaper, relevance_score: 6.0 }} />);
    const scoreBadge = screen.getByText('6.0');
    expect(scoreBadge.className).toContain('score-mid');
  });

  it('shows grey score colour for score < 5', () => {
    render(<PaperCard paper={{ ...mockPaper, relevance_score: 3.0 }} />);
    const scoreBadge = screen.getByText('3.0');
    expect(scoreBadge.className).toContain('score-low');
  });

  it('shows early access badge when applicable', () => {
    render(<PaperCard paper={{ ...mockPaper, early_access: true }} />);
    expect(screen.getByText('Early Access')).toBeInTheDocument();
  });

  it('renders category chips', () => {
    render(<PaperCard paper={mockPaper} />);
    expect(screen.getByText('battery')).toBeInTheDocument();
    expect(screen.getByText('degradation')).toBeInTheDocument();
  });
});
