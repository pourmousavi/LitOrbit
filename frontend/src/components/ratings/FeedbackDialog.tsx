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
    // Animate in
    requestAnimationFrame(() => setVisible(true));

    // Auto-dismiss after 10 seconds
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
        'fixed inset-x-0 bottom-0 z-60 transition-transform duration-200',
        visible ? 'translate-y-0' : 'translate-y-full',
      )}
    >
      <div className="mx-auto max-w-lg rounded-t-2xl border border-border-default bg-bg-surface p-5 shadow-xl">
        {/* Header */}
        <div className="mb-4 flex items-start justify-between">
          <p className="font-serif text-sm leading-relaxed text-text-primary">{question}</p>
          <button
            onClick={() => {
              setVisible(false);
              setTimeout(onDismiss, 200);
            }}
            className="ml-3 shrink-0 rounded-full p-1 text-text-tertiary hover:text-text-primary"
          >
            <X size={16} />
          </button>
        </div>

        {/* Options */}
        <div className="flex flex-wrap gap-2">
          {options.map((option) => (
            <button
              key={option}
              onClick={() => handleSelect(option)}
              className="rounded-lg border border-border-default bg-bg-base px-3 py-2 font-mono text-xs text-text-secondary transition hover:border-accent hover:text-accent"
            >
              {option}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
