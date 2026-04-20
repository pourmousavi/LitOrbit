import { useEffect, useRef } from 'react';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { useFeed } from '@/hooks/useFeed';
import { useUIStore } from '@/stores/uiStore';
import FeedItemCard from './FeedItemCard';
import type { FeedFilters } from '@/types/feed';
import api from '@/lib/api';

function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div className="h-6 rounded-lg bg-bg-elevated" style={{ width: 100 }} />
        <div className="h-8 rounded-xl bg-bg-elevated" style={{ width: 48 }} />
      </div>
      <div className="h-5 w-full rounded bg-bg-elevated" style={{ marginBottom: 8 }} />
      <div className="h-5 rounded bg-bg-elevated" style={{ width: '75%', marginBottom: 12 }} />
      <div className="h-3 rounded bg-bg-elevated" style={{ width: '50%' }} />
    </div>
  );
}

interface UnifiedFeedListProps {
  filters: Partial<FeedFilters>;
}

export default function UnifiedFeedList({ filters }: UnifiedFeedListProps) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } = useFeed(filters);
  const selectPaper = useUIStore((s) => s.selectPaper);
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const queryClient = useQueryClient();
  const sentinelRef = useRef<HTMLDivElement>(null);

  const favoriteMutation = useMutation({
    mutationFn: async ({ id, value }: { id: string; value: boolean }) => {
      if (value) await api.post(`/api/v1/papers/${id}/favorite`);
      else await api.delete(`/api/v1/papers/${id}/favorite`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['papers'] });
    },
  });

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
        {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
        <p className="font-mono text-sm text-danger">Failed to load feed</p>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['feed'] })}
          className="rounded-xl bg-bg-elevated font-mono text-sm text-text-secondary hover:text-text-primary"
          style={{ marginTop: 12, padding: '10px 20px' }}
        >
          Retry
        </button>
      </div>
    );
  }

  const allItems = data?.pages.flatMap((page) => page.items) ?? [];

  if (allItems.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 18 }} className="font-mono text-text-secondary">No items yet</p>
        <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
          {filters.type === 'news'
            ? 'News will appear here after the ingest runs'
            : 'Papers and news will appear here after pipelines run'}
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {allItems.map((item) => (
        <FeedItemCard
          key={`${item.item_type}-${item.item_id}`}
          item={item}
          isSelected={item.item_type === 'paper' && selectedPaperId === item.item_id}
          onSelect={() => {
            if (item.item_type === 'paper') {
              selectPaper(item.item_id);
            } else if (item.news?.url) {
              window.open(item.news.url, '_blank');
            }
          }}
          onToggleFavorite={
            item.item_type === 'paper'
              ? () => favoriteMutation.mutate({ id: item.item_id, value: !item.user_state.starred })
              : undefined
          }
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
