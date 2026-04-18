import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import NavBadge from './NavBadge';

describe('NavBadge', () => {
  it('shows count when greater than 0', () => {
    render(<NavBadge count={5} />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders nothing when count is 0', () => {
    const { container } = render(<NavBadge count={0} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows the correct number', () => {
    render(<NavBadge count={12} />);
    expect(screen.getByText('12')).toBeInTheDocument();
  });
});
