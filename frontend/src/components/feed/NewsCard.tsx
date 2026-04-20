import { Bookmark, Headphones, Share2, Star, LibraryBig, Check } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useScholarLibStore } from '@/stores/scholarLibStore';
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
  isSelected?: boolean;
  onClick?: () => void;
}

export default function NewsCard({ item, isSelected, onClick }: NewsCardProps) {
  const news = item.news;
  const queryClient = useQueryClient();
  const scholarLibConnected = useScholarLibStore((s) => s.status === 'connected');

  const starMutation = useMutation({
    mutationFn: async () => {
      const endpoint = item.user_state.starred ? 'unstar' : 'star';
      await api.post(`/api/v1/news/${item.item_id}/${endpoint}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['feed'] }),
  });

  const markReadMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/news/${item.item_id}/mark_read`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['feed'] }),
  });

  if (!news) return null;

  return (
    <article
      onClick={() => {
        if (!item.user_state.read) markReadMutation.mutate();
        onClick?.();
      }}
      className={cn(
        'group cursor-pointer rounded-2xl border border-border-default bg-bg-surface transition-all overflow-hidden',
        'hover:border-border-strong',
        isSelected && 'border-warning bg-bg-elevated',
        item.user_state.read && !isSelected && 'opacity-60 hover:opacity-100',
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
            {item.relevance_score.toFixed(1)}
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
            <span key={tag} className="rounded-full bg-warning/10 font-mono text-xs text-warning" style={{ padding: '2px 10px' }}>
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

      {/* Bottom row: categories + actions — matches PaperCard layout */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {news.categories.slice(0, 3).map((cat) => (
            <span key={cat} className="rounded-full bg-bg-elevated font-mono text-xs text-text-tertiary" style={{ padding: '3px 10px' }}>
              {cat}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            className={cn(
              'rounded-lg transition hover:bg-bg-elevated',
              item.user_state.starred ? 'text-accent' : 'text-text-tertiary hover:text-accent',
            )}
            onClick={(e) => { e.stopPropagation(); starMutation.mutate(); }}
            title={item.user_state.starred ? 'Remove from favorites' : 'Save for later'}
            style={{ padding: 8 }}
          >
            <Bookmark size={16} fill={item.user_state.starred ? 'currentColor' : 'none'} />
          </button>
          {scholarLibConnected && (
            <button
              className={cn(
                'rounded-lg transition',
                item.user_state.sent_to_scholarlib
                  ? 'text-success cursor-default'
                  : 'text-text-tertiary hover:bg-bg-elevated hover:text-accent',
              )}
              style={{ padding: 8 }}
              title={item.user_state.sent_to_scholarlib ? 'In ScholarLib' : 'Add to ScholarLib'}
              onClick={(e) => { e.stopPropagation(); if (!item.user_state.sent_to_scholarlib) onClick?.(); }}
              disabled={item.user_state.sent_to_scholarlib}
            >
              {item.user_state.sent_to_scholarlib ? <Check size={16} /> : <LibraryBig size={16} />}
            </button>
          )}
          <button
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
            onClick={(e) => { e.stopPropagation(); onClick?.(); }}
            title="Podcast & details"
            style={{ padding: 8 }}
          >
            <Headphones size={16} />
          </button>
          <button
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
            onClick={(e) => { e.stopPropagation(); onClick?.(); }}
            title="Share"
            style={{ padding: 8 }}
          >
            <Share2 size={16} />
          </button>
          <button
            className={cn(
              'rounded-lg transition hover:bg-bg-elevated',
              item.user_state.rating != null ? 'text-warning' : 'text-text-tertiary hover:text-warning',
            )}
            onClick={(e) => { e.stopPropagation(); onClick?.(); }}
            title={item.user_state.rating != null ? `Your rating: ${item.user_state.rating}/10` : 'Rate'}
            style={{ padding: 8 }}
          >
            <Star size={16} fill={item.user_state.rating != null ? 'currentColor' : 'none'} />
          </button>
        </div>
      </div>
    </article>
  );
}
