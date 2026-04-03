import { useEffect, useRef } from 'react';
import { usePapers } from '@/hooks/usePapers';
import { useUIStore } from '@/stores/uiStore';
import PaperCard from './PaperCard';

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div className="h-6 rounded-lg bg-bg-elevated" style={{ width: 100 }} />
        <div className="h-8 rounded-xl bg-bg-elevated" style={{ width: 48 }} />
      </div>
      <div className="h-5 w-full rounded bg-bg-elevated" style={{ marginBottom: 8 }} />
      <div className="h-5 rounded bg-bg-elevated" style={{ width: '75%', marginBottom: 12 }} />
      <div className="h-3 rounded bg-bg-elevated" style={{ width: '50%', marginBottom: 16 }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="h-3 w-full rounded bg-bg-elevated" />
        <div className="h-3 w-full rounded bg-bg-elevated" />
        <div className="h-3 rounded bg-bg-elevated" style={{ width: '66%' }} />
      </div>
    </div>
  );
}

interface PaperFeedProps {
  journal?: string;
  category?: string;
}

export default function PaperFeed({ journal, category }: PaperFeedProps) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    usePapers({ journal, category });
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const selectPaper = useUIStore((s) => s.selectPaper);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sentinelRef.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
        <p className="font-mono text-sm text-danger">Failed to load papers</p>
        <button
          onClick={() => window.location.reload()}
          className="rounded-xl bg-bg-elevated font-mono text-sm text-text-secondary hover:text-text-primary"
          style={{ marginTop: 12, padding: '10px 20px' }}
        >
          Retry
        </button>
      </div>
    );
  }

  const allPapers = data?.pages.flatMap((page) => page.papers) ?? [];

  if (allPapers.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 18 }} className="font-mono text-text-secondary">No papers yet</p>
        <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
          Papers will appear here after the pipeline runs
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {allPapers.map((paper) => (
        <PaperCard
          key={paper.id}
          paper={paper}
          isSelected={selectedPaperId === paper.id}
          onClick={() => selectPaper(paper.id)}
        />
      ))}

      <div ref={sentinelRef} style={{ height: 16 }} />

      {isFetchingNextPage && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
          <span className="font-mono text-xs text-text-tertiary">Loading more...</span>
        </div>
      )}
    </div>
  );
}
