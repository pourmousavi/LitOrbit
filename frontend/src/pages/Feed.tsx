import { useUIStore } from '@/stores/uiStore';
import PaperFeed from '@/components/papers/PaperFeed';
import PaperDetail from '@/components/papers/PaperDetail';

export default function Feed() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Feed column */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px 24px' }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }} className="font-mono text-text-primary">
            Paper Feed
          </h1>
          <PaperFeed />
        </div>
      </div>

      {/* Detail panel */}
      {selectedPaperId && (
        <div
          className="hidden border-l border-border-default bg-bg-surface md:block"
          style={{ width: 420, flexShrink: 0, overflowY: 'auto' }}
        >
          <PaperDetail />
        </div>
      )}
    </div>
  );
}
