import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';
import PaperFeed from '@/components/papers/PaperFeed';
import PaperDetail from '@/components/papers/PaperDetail';

export default function Feed() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);

  return (
    <div className="flex h-full min-h-svh">
      {/* Feed column */}
      <div
        className={cn(
          'flex-1 overflow-y-auto p-4',
          selectedPaperId && 'hidden md:block',
        )}
      >
        <div className="mx-auto max-w-2xl">
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <h1 className="font-mono text-lg font-medium text-text-primary">Paper Feed</h1>
          </div>

          <PaperFeed />
        </div>
      </div>

      {/* Detail panel */}
      {selectedPaperId && (
        <div
          className={cn(
            'border-l border-border-default bg-bg-surface',
            'fixed inset-0 z-30 md:static md:z-auto',
            'md:w-[380px] md:shrink-0',
          )}
        >
          <PaperDetail />
        </div>
      )}
    </div>
  );
}
