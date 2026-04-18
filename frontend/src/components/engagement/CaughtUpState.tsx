import { CheckCircle2, Flame } from 'lucide-react';

export default function CaughtUpState({ streak }: { streak: number }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        paddingTop: 80,
        gap: 8,
      }}
    >
      <CheckCircle2 size={40} className="text-accent" />
      <p className="font-mono text-lg text-text-primary" style={{ fontWeight: 600 }}>
        All caught up!
      </p>
      <p className="font-mono text-sm text-text-tertiary">
        You've reviewed all your papers. New papers arrive daily.
      </p>
      {streak > 0 && (
        <p
          className="font-mono text-sm text-text-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4 }}
        >
          <Flame size={14} style={{ color: '#f97316' }} />
          {streak}-day streak — keep it going!
        </p>
      )}
    </div>
  );
}
