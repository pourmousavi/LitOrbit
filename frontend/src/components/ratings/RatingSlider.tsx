import { useState } from 'react';
import { cn } from '@/lib/utils';

interface RatingSliderProps {
  initialValue?: number;
  onSubmit: (value: number) => void;
  loading?: boolean;
}

export default function RatingSlider({ initialValue = 5, onSubmit, loading }: RatingSliderProps) {
  const [value, setValue] = useState(initialValue);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="font-mono text-xs text-text-secondary">Your Rating</label>
        <span className="font-mono text-lg font-medium text-text-primary">{value}/10</span>
      </div>

      <input
        type="range"
        min={1}
        max={10}
        step={1}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        className={cn(
          'w-full cursor-pointer appearance-none rounded-full bg-border-default h-1.5',
          '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4',
          '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent',
          '[&::-webkit-slider-thumb]:cursor-pointer',
        )}
      />

      <div className="flex justify-between font-mono text-xs text-text-tertiary">
        <span>Not relevant</span>
        <span>Highly relevant</span>
      </div>

      <button
        onClick={() => onSubmit(value)}
        disabled={loading}
        className="w-full rounded-lg bg-accent py-2 font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
      >
        {loading ? 'Submitting...' : 'Submit Rating'}
      </button>
    </div>
  );
}
