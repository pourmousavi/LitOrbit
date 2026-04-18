import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import NavBadge from './NavBadge';

describe('NavBadge', () => {
  it('shows count when greater than 0', () => {
    render(<NavBadge count={5} />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('shows green checkmark when count is 0', () => {
    render(<NavBadge count={0} />);
    expect(screen.getByText('\u2713')).toBeInTheDocument();
  });

  it('shows the correct number', () => {
    render(<NavBadge count={12} />);
    expect(screen.getByText('12')).toBeInTheDocument();
  });
});
