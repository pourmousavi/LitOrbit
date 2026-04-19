import { useEffect, useRef, useState } from 'react';
import { useQueryClient, useMutation, type InfiniteData } from '@tanstack/react-query';
import { CheckSquare, Check, X, LibraryBig } from 'lucide-react';
import { usePapers } from '@/hooks/usePapers';
import { useEngagement } from '@/hooks/useEngagement';
import { useUIStore } from '@/stores/uiStore';
import { useScholarLibStore } from '@/stores/scholarLibStore';
import PaperCard from './PaperCard';
import CaughtUpState from '@/components/engagement/CaughtUpState';
import ScholarLibModal from '@/components/integrations/ScholarLibModal';
import BulkScholarLibModal from '@/components/integrations/BulkScholarLibModal';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import type { Paper, PapersResponse } from '@/types';

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
  search?: string;
  sort?: string;
  favorites?: boolean;
}

export default function PaperFeed({ journal, category, search, sort, favorites }: PaperFeedProps) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    usePapers({ journal, category, search, sort, favorites });
  const { data: pulse } = useEngagement();
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const selectPaper = useUIStore((s) => s.selectPaper);
  const queryClient = useQueryClient();
  const sentinelRef = useRef<HTMLDivElement>(null);
  const scholarLibConnected = useScholarLibStore((s) => s.status === 'connected');

  // Bulk selection
  const [bulkMode, setBulkMode] = useState(false);
  const [selectedPaperIds, setSelectedPaperIds] = useState<Set<string>>(new Set());
  const [scholarLibPaper, setScholarLibPaper] = useState<Paper | null>(null);
  const [showBulkScholarLibModal, setShowBulkScholarLibModal] = useState(false);

  const toggleSelection = (id: string) => {
    setSelectedPaperIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setFavoriteInCache = (id: string, value: boolean) => {
    queryClient.setQueriesData<InfiniteData<PapersResponse>>({ queryKey: ['papers'] }, (old) => {
      if (!old) return old;
      return {
        ...old,
        pages: old.pages.map((page) => ({
          ...page,
          papers: page.papers.map((p) => (p.id === id ? { ...p, is_favorite: value } : p)),
        })),
      };
    });
  };

  const favoriteMutation = useMutation({
    mutationFn: async ({ id, value }: { id: string; value: boolean }) => {
      if (value) await api.post(`/api/v1/papers/${id}/favorite`);
      else await api.delete(`/api/v1/papers/${id}/favorite`);
    },
    onMutate: ({ id, value }) => {
      const prev = queryClient.getQueriesData<InfiniteData<PapersResponse>>({ queryKey: ['papers'] });
      setFavoriteInCache(id, value);
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      // rollback
      ctx?.prev?.forEach(([key, data]) => queryClient.setQueryData(key, data));
    },
  });

  const handleToggleFavorite = (paperId: string, current: boolean) => {
    favoriteMutation.mutate({ id: paperId, value: !current });
  };

  const handleSelectPaper = (id: string) => {
    selectPaper(id);
    // Optimistically mark this paper as opened in the cached feed pages
    queryClient.setQueriesData<InfiniteData<PapersResponse>>({ queryKey: ['papers'] }, (old) => {
      if (!old) return old;
      return {
        ...old,
        pages: old.pages.map((page) => ({
          ...page,
          papers: page.papers.map((p) => (p.id === id ? { ...p, is_opened: true } : p)),
        })),
      };
    });
  };

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
    // Show "caught up" state if user has reviewed all papers (no active filters)
    if (!search && !journal && !category && pulse && pulse.unreviewed_count === 0 && pulse.weekly_stats.rated > 0) {
      return <CaughtUpState streak={pulse.streak} />;
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 18 }} className="font-mono text-text-secondary">No papers yet</p>
        <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
          Papers will appear here after the pipeline runs
        </p>
      </div>
    );
  }

  const allPapersMap = new Map(allPapers.map((p) => [p.id, p]));
  const selectedPapers = [...selectedPaperIds].map((id) => allPapersMap.get(id)).filter(Boolean) as Paper[];

  return (
    <>
      {/* Bulk select toggle */}
      {scholarLibConnected && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <button
            onClick={() => { setBulkMode(!bulkMode); setSelectedPaperIds(new Set()); }}
            className={cn(
              'flex items-center rounded-xl font-mono text-xs transition',
              bulkMode ? 'bg-accent/10 text-accent' : 'text-text-tertiary hover:text-text-secondary',
            )}
            style={{ gap: 4, padding: '6px 12px' }}
          >
            <CheckSquare size={13} />
            {bulkMode ? `${selectedPaperIds.size} selected` : 'Select'}
          </button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {allPapers.map((paper) => (
          <div key={paper.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            {bulkMode && (
              <div
                onClick={(e) => { e.stopPropagation(); toggleSelection(paper.id); }}
                className={cn(
                  'flex items-center justify-center rounded-md border transition cursor-pointer',
                  selectedPaperIds.has(paper.id)
                    ? 'border-accent bg-accent text-white'
                    : 'border-border-default bg-bg-base text-transparent hover:border-border-strong',
                )}
                style={{ width: 20, height: 20, flexShrink: 0, marginTop: 18 }}
              >
                <Check size={13} />
              </div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <PaperCard
                paper={paper}
                isSelected={selectedPaperId === paper.id}
                onClick={() => handleSelectPaper(paper.id)}
                onToggleFavorite={() => handleToggleFavorite(paper.id, !!paper.is_favorite)}
                onSendToScholarLib={() => setScholarLibPaper(paper)}
              />
            </div>
          </div>
        ))}

        <div ref={sentinelRef} style={{ height: 16 }} />

        {isFetchingNextPage && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
            <span className="font-mono text-xs text-text-tertiary">Loading more...</span>
          </div>
        )}
      </div>

      {/* Floating bulk action bar */}
      {bulkMode && selectedPaperIds.size > 0 && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center rounded-2xl border border-border-default bg-bg-surface shadow-lg"
          style={{ gap: 12, padding: '12px 20px' }}
        >
          <span className="font-mono text-sm text-text-primary">
            {selectedPaperIds.size} paper{selectedPaperIds.size > 1 ? 's' : ''} selected
          </span>
          <button
            onClick={() => setShowBulkScholarLibModal(true)}
            className="flex items-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
            style={{ gap: 6, padding: '10px 16px' }}
          >
            <LibraryBig size={14} />
            Add to ScholarLib
          </button>
          <button
            onClick={() => { setBulkMode(false); setSelectedPaperIds(new Set()); }}
            className="rounded-lg text-text-tertiary transition hover:text-text-primary"
            style={{ padding: 6 }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Single paper ScholarLib modal */}
      {scholarLibPaper && (
        <ScholarLibModal
          paper={scholarLibPaper}
          onClose={() => setScholarLibPaper(null)}
        />
      )}

      {/* Bulk ScholarLib modal */}
      {showBulkScholarLibModal && selectedPapers.length > 0 && (
        <BulkScholarLibModal
          papers={selectedPapers}
          onClose={() => setShowBulkScholarLibModal(false)}
          onSuccess={() => { setBulkMode(false); setSelectedPaperIds(new Set()); }}
        />
      )}
    </>
  );
}
