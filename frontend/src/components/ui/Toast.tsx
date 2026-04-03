import { create } from 'zustand';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';

type ToastType = 'success' | 'error' | 'info';

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastStore {
  toasts: ToastItem[];
  add: (type: ToastType, message: string) => void;
  remove: (id: number) => void;
}

let nextId = 0;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  add: (type, message) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, type, message }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export function toast(type: ToastType, message: string) {
  useToastStore.getState().add(type, message);
}

const icons = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
};

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);

  if (toasts.length === 0) return null;

  return (
    <div style={{ position: 'fixed', right: 16, top: 16, zIndex: 100, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map((t) => {
        const Icon = icons[t.type];
        return (
          <div
            key={t.id}
            className={cn(
              'flex items-center rounded-2xl border shadow-lg',
              t.type === 'success' && 'border-success/30 bg-success/10 text-success',
              t.type === 'error' && 'border-danger/30 bg-danger/10 text-danger',
              t.type === 'info' && 'border-accent/30 bg-accent/10 text-accent',
            )}
            style={{ gap: 10, padding: '12px 16px' }}
          >
            <Icon size={16} />
            <span className="font-mono text-sm">{t.message}</span>
            <button onClick={() => remove(t.id)} className="opacity-60 hover:opacity-100" style={{ marginLeft: 4 }}>
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
