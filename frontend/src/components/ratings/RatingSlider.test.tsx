import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import RatingSlider from './RatingSlider';

describe('RatingSlider', () => {
  it('renders with default value of 5', () => {
    render(<RatingSlider onSubmit={() => {}} />);
    expect(screen.getByText('5/10')).toBeInTheDocument();
    expect(screen.getByText('Submit Rating')).toBeInTheDocument();
  });

  it('renders with custom initial value', () => {
    render(<RatingSlider initialValue={8} onSubmit={() => {}} />);
    expect(screen.getByText('8/10')).toBeInTheDocument();
  });

  it('value changes on input change', () => {
    render(<RatingSlider onSubmit={() => {}} />);
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '9' } });
    expect(screen.getByText('9/10')).toBeInTheDocument();
  });

  it('calls onSubmit with current value when button clicked', () => {
    const onSubmit = vi.fn();
    render(<RatingSlider onSubmit={onSubmit} />);
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '7' } });
    fireEvent.click(screen.getByText('Submit Rating'));
    expect(onSubmit).toHaveBeenCalledWith(7);
  });

  it('shows loading state', () => {
    render(<RatingSlider onSubmit={() => {}} loading />);
    expect(screen.getByText('Submitting...')).toBeInTheDocument();
  });
});
