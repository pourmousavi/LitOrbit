import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FeedbackDialogProps {
  question: string;
  options: string[];
  onSelect: (option: string) => void;
  onDismiss: () => void;
}

export default function FeedbackDialog({ question, options, onSelect, onDismiss }: FeedbackDialogProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 200);
    }, 10000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const handleSelect = (option: string) => {
    onSelect(option);
    setVisible(false);
    setTimeout(onDismiss, 200);
  };

  return (
    <div
      className={cn(
        'fixed inset-x-0 bottom-0 z-[60] transition-transform duration-200',
        visible ? 'translate-y-0' : 'translate-y-full',
      )}
    >
      <div
        className="mx-auto rounded-t-2xl border border-border-default bg-bg-surface shadow-xl"
        style={{ maxWidth: 520, padding: 24 }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
          <p className="font-serif text-text-primary" style={{ fontSize: 14, lineHeight: 1.5 }}>{question}</p>
          <button
            onClick={() => {
              setVisible(false);
              setTimeout(onDismiss, 200);
            }}
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-text-primary"
            style={{ padding: 6, flexShrink: 0 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Options */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {options.map((option) => (
            <button
              key={option}
              onClick={() => handleSelect(option)}
              className="rounded-xl border border-border-default bg-bg-base font-mono text-text-secondary transition hover:border-accent hover:text-accent"
              style={{ fontSize: 12, padding: '10px 16px' }}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
