import { useEffect, useRef } from 'react';
import { usePapers } from '@/hooks/usePapers';
import { useUIStore } from '@/stores/uiStore';
import PaperCard from './PaperCard';

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-border-default bg-bg-surface p-4">
      <div className="mb-3 flex justify-between">
        <div className="h-5 w-24 rounded bg-bg-elevated" />
        <div className="h-7 w-10 rounded-lg bg-bg-elevated" />
      </div>
      <div className="mb-2 h-5 w-full rounded bg-bg-elevated" />
      <div className="mb-3 h-5 w-3/4 rounded bg-bg-elevated" />
      <div className="mb-2 h-3 w-1/2 rounded bg-bg-elevated" />
      <div className="space-y-1.5">
        <div className="h-3 w-full rounded bg-bg-elevated" />
        <div className="h-3 w-full rounded bg-bg-elevated" />
        <div className="h-3 w-2/3 rounded bg-bg-elevated" />
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

  // Infinite scroll observer
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
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="font-mono text-sm text-danger">Failed to load papers</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-3 rounded-lg bg-bg-elevated px-4 py-2 font-mono text-sm text-text-secondary hover:text-text-primary"
        >
          Retry
        </button>
      </div>
    );
  }

  const allPapers = data?.pages.flatMap((page) => page.papers) ?? [];

  if (allPapers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <p className="font-mono text-lg text-text-secondary">No papers yet</p>
        <p className="mt-1 font-mono text-sm text-text-tertiary">
          Papers will appear here after the pipeline runs
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {allPapers.map((paper) => (
        <PaperCard
          key={paper.id}
          paper={paper}
          isSelected={selectedPaperId === paper.id}
          onClick={() => selectPaper(paper.id)}
        />
      ))}

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} className="h-4" />

      {isFetchingNextPage && (
        <div className="flex justify-center py-4">
          <div className="font-mono text-xs text-text-tertiary">Loading more...</div>
        </div>
      )}
    </div>
  );
}
