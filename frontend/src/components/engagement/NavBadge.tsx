import { Check } from 'lucide-react';

export default function NavBadge({ count }: { count: number }) {
  if (count <= 0) {
    return (
      <span className="font-mono" style={{ fontSize: 10, color: '#555' }}>
        <Check size={11} />
      </span>
    );
  }

  const amber = count >= 50;

  return (
    <span
      className="font-mono"
      style={{
        fontSize: 10,
        color: amber ? 'var(--color-warning, #f59e0b)' : '#888',
        padding: '1px 6px',
        borderRadius: 3,
        background: 'var(--color-bg-elevated, #1c1c1c)',
        border: '1px solid var(--color-border-default, #2a2a2a)',
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      {count > 99 ? '99+' : count}
    </span>
  );
}
