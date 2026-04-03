import { useUIStore } from '@/stores/uiStore';
import PaperFeed from '@/components/papers/PaperFeed';
import PaperDetail from '@/components/papers/PaperDetail';

export default function Feed() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);

  return (
    <div className="flex min-h-svh">
      {/* Feed column */}
      <div
        className="flex-1 overflow-y-auto p-6"
        style={{ display: selectedPaperId ? undefined : 'block' }}
      >
        <div className="mx-auto max-w-2xl">
          <h1 className="mb-6 font-mono text-xl font-medium text-text-primary">Paper Feed</h1>
          <PaperFeed />
        </div>
      </div>

      {/* Detail panel */}
      {selectedPaperId && (
        <div
          className="hidden border-l border-border-default bg-bg-surface md:block"
          style={{ width: 400, flexShrink: 0 }}
        >
          <PaperDetail />
        </div>
      )}
    </div>
  );
}
