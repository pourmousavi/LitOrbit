import { ExternalLink, Bookmark, ThumbsUp, ThumbsDown, Check } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { FeedItem } from '@/types/feed';
import { cn, formatDate } from '@/lib/utils';
import api from '@/lib/api';

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return 'just now';
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(dateStr);
}

function relevanceColor(score: number | null): string {
  if (score === null) return 'text-text-tertiary';
  if (score >= 0.7) return 'text-score-high';
  if (score >= 0.4) return 'text-score-mid';
  return 'text-score-low';
}

interface NewsCardProps {
  item: FeedItem;
  onClick?: () => void;
}

export default function NewsCard({ item, onClick }: NewsCardProps) {
  const news = item.news;
  const queryClient = useQueryClient();

  const invalidateFeed = () => queryClient.invalidateQueries({ queryKey: ['feed'] });

  const starMutation = useMutation({
    mutationFn: async () => {
      const endpoint = item.user_state.starred ? 'unstar' : 'star';
      await api.post(`/api/v1/news/${item.item_id}/${endpoint}`);
    },
    onSuccess: invalidateFeed,
  });

  const rateMutation = useMutation({
    mutationFn: async (rating: string) => {
      await api.post(`/api/v1/news/${item.item_id}/rate`, { rating });
    },
    onSuccess: invalidateFeed,
  });

  const markReadMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/news/${item.item_id}/mark_read`);
    },
    onSuccess: invalidateFeed,
  });

  if (!news) return null;

  const currentRating = item.user_state.rating;

  return (
    <article
      onClick={() => {
        if (!item.user_state.read) markReadMutation.mutate();
        onClick?.();
      }}
      className={cn(
        'group cursor-pointer rounded-2xl border border-border-default bg-bg-surface transition-all overflow-hidden',
        'hover:border-border-strong',
        item.user_state.read && 'opacity-60 hover:opacity-100',
      )}
      style={{ padding: 14 }}
    >
      {/* Top row: type badge + source + time + relevance */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <span className="rounded-lg bg-warning/15 font-mono text-xs text-warning" style={{ padding: '4px 10px' }}>
            News
          </span>
          {item.source_name && (
            <span className="rounded-lg bg-bg-elevated font-mono text-xs text-text-secondary" style={{ padding: '4px 10px' }}>
              {item.source_name}
            </span>
          )}
          <span className="font-mono text-xs text-text-tertiary">
            {timeAgo(item.published_at)}
          </span>
          {item.user_state.read && (
            <span className="flex items-center rounded-lg bg-bg-elevated font-mono text-xs text-text-tertiary" style={{ padding: '4px 10px', gap: 4 }}>
              <Check size={11} /> Read
            </span>
          )}
        </div>
        {item.relevance_score !== null && (
          <span
            className={cn('rounded-xl font-mono text-sm font-semibold', relevanceColor(item.relevance_score))}
            style={{ padding: '6px 12px', flexShrink: 0, backgroundColor: 'var(--color-bg-elevated)' }}
          >
            {item.relevance_score.toFixed(2)}
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="font-sans font-semibold text-text-primary line-clamp-2" style={{ fontSize: 15, lineHeight: 1.4, marginBottom: 6 }}>
        {item.title}
      </h3>

      {/* Author */}
      {news.author && (
        <p className="font-mono text-xs text-text-secondary" style={{ marginBottom: 8 }}>
          {news.author}
        </p>
      )}

      {/* Excerpt */}
      {item.excerpt && (
        <p className="text-sm leading-relaxed text-text-secondary line-clamp-3" style={{ marginBottom: 12 }}>
          {item.excerpt}
        </p>
      )}

      {/* Tags */}
      {news.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          {news.tags.slice(0, 6).map((tag) => (
            <span
              key={tag}
              className="rounded-full bg-warning/10 font-mono text-xs text-warning"
              style={{ padding: '2px 10px' }}
            >
              {tag}
            </span>
          ))}
          {news.tags.length > 6 && (
            <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>+{news.tags.length - 6}</span>
          )}
        </div>
      )}

      {/* Cluster coverage */}
      {news.cluster_also_covered_in.length > 0 && (
        <p className="font-mono text-xs text-text-tertiary italic" style={{ marginBottom: 12 }}>
          Also covered by {news.cluster_also_covered_in.map(c => c.source_name).join(', ')}
        </p>
      )}

      {/* Cross-link */}
      {item.cross_links.length > 0 && item.cross_links[0].target_type === 'paper' && (
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 12 }}>
          ↳ See also in Papers: {item.cross_links[0].target_title}
        </p>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 4 }}>
        <button
          className={cn(
            'rounded-lg transition hover:bg-bg-elevated',
            item.user_state.starred ? 'text-accent' : 'text-text-tertiary hover:text-accent',
          )}
          onClick={(e) => { e.stopPropagation(); starMutation.mutate(); }}
          title={item.user_state.starred ? 'Unstar' : 'Star'}
          style={{ padding: 8 }}
        >
          <Bookmark size={16} fill={item.user_state.starred ? 'currentColor' : 'none'} />
        </button>
        <button
          className={cn(
            'rounded-lg transition hover:bg-bg-elevated',
            currentRating === 'thumbs_up' ? 'text-success' : 'text-text-tertiary hover:text-success',
          )}
          onClick={(e) => { e.stopPropagation(); rateMutation.mutate('thumbs_up'); }}
          title="Thumbs up"
          style={{ padding: 8 }}
        >
          <ThumbsUp size={16} fill={currentRating === 'thumbs_up' ? 'currentColor' : 'none'} />
        </button>
        <button
          className={cn(
            'rounded-lg transition hover:bg-bg-elevated',
            currentRating === 'thumbs_down' ? 'text-danger' : 'text-text-tertiary hover:text-danger',
          )}
          onClick={(e) => { e.stopPropagation(); rateMutation.mutate('thumbs_down'); }}
          title="Thumbs down"
          style={{ padding: 8 }}
        >
          <ThumbsDown size={16} fill={currentRating === 'thumbs_down' ? 'currentColor' : 'none'} />
        </button>
        <a
          href={news.url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
          onClick={(e) => e.stopPropagation()}
          title="Open article"
          style={{ padding: 8 }}
        >
          <ExternalLink size={16} />
        </a>
      </div>
    </article>
  );
}
