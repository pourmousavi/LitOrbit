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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <label className="font-mono text-text-secondary" style={{ fontSize: 12 }}>Your Rating</label>
        <span className="font-mono font-semibold text-text-primary" style={{ fontSize: 20 }}>{value}/10</span>
      </div>

      <input
        type="range"
        min={1}
        max={10}
        step={1}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        className={cn(
          'w-full cursor-pointer appearance-none rounded-full bg-border-default',
          '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5',
          '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent',
          '[&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-md',
        )}
        style={{ height: 6 }}
      />

      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>Not relevant</span>
        <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>Highly relevant</span>
      </div>

      <button
        onClick={() => onSubmit(value)}
        disabled={loading}
        className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
        style={{ width: '100%', padding: '12px 0' }}
      >
        {loading ? 'Submitting...' : 'Submit Rating'}
      </button>
    </div>
  );
}
