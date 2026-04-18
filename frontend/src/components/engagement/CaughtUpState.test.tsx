import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CaughtUpState from './CaughtUpState';

describe('CaughtUpState', () => {
  it('shows caught up message', () => {
    render(<CaughtUpState streak={3} />);
    expect(screen.getByText('All caught up!')).toBeInTheDocument();
    expect(screen.getByText("You've reviewed all your papers. New papers arrive daily.")).toBeInTheDocument();
  });

  it('shows streak when greater than 0', () => {
    render(<CaughtUpState streak={5} />);
    expect(screen.getByText(/5-day streak/)).toBeInTheDocument();
  });
});
