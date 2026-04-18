import { useEffect, useRef } from 'react';
import { useQueryClient, useMutation, type InfiniteData } from '@tanstack/react-query';
import { usePapers } from '@/hooks/usePapers';
import { useEngagement } from '@/hooks/useEngagement';
import { useUIStore } from '@/stores/uiStore';
import PaperCard from './PaperCard';
import CaughtUpState from '@/components/engagement/CaughtUpState';
import api from '@/lib/api';
import type { PapersResponse } from '@/types';

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {allPapers.map((paper) => (
        <PaperCard
          key={paper.id}
          paper={paper}
          isSelected={selectedPaperId === paper.id}
          onClick={() => handleSelectPaper(paper.id)}
          onToggleFavorite={() => handleToggleFavorite(paper.id, !!paper.is_favorite)}
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
