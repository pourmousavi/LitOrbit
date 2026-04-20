import { ArrowLeft, ExternalLink, Bookmark, ThumbsUp, ThumbsDown, Loader2, Info } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNewsItem } from '@/hooks/useNewsItem';
import { useUIStore } from '@/stores/uiStore';
import { cn, formatDate } from '@/lib/utils';
import api from '@/lib/api';

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return 'Unknown';
  const d = new Date(dateStr);
  return d.toLocaleString('en-AU', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function relevanceColor(score: number | null): string {
  if (score === null) return 'text-text-tertiary';
  if (score >= 0.7) return 'text-score-high';
  if (score >= 0.4) return 'text-score-mid';
  return 'text-score-low';
}

function relevanceBg(score: number | null): string {
  if (score === null) return 'bg-bg-elevated';
  if (score >= 0.7) return 'bg-score-high/20';
  if (score >= 0.4) return 'bg-score-mid/20';
  return 'bg-score-low/20';
}

export default function NewsDetail() {
  const selectedNewsId = useUIStore((s) => s.selectedNewsId);
  const selectNews = useUIStore((s) => s.selectNews);
  const { data: item, isLoading } = useNewsItem(selectedNewsId);
  const queryClient = useQueryClient();

  const starMutation = useMutation({
    mutationFn: async () => {
      // Toggle — check current state from detail endpoint? For now just star.
      await api.post(`/api/v1/news/${selectedNewsId}/star`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-item', selectedNewsId] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });

  const unstarMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/news/${selectedNewsId}/unstar`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-item', selectedNewsId] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });

  const rateMutation = useMutation({
    mutationFn: async (rating: string) => {
      await api.post(`/api/v1/news/${selectedNewsId}/rate`, { rating });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-item', selectedNewsId] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });

  const scrapeMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/news/${selectedNewsId}/scrape`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-item', selectedNewsId] });
    },
  });

  // Mark as read on open
  useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/news/${selectedNewsId}/mark_read`);
    },
  }).mutate;

  if (!selectedNewsId) return null;

  if (isLoading) {
    return (
      <div className="animate-pulse" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="h-4 rounded bg-bg-elevated" style={{ width: 60 }} />
        <div className="h-6 w-full rounded bg-bg-elevated" />
        <div className="h-6 rounded bg-bg-elevated" style={{ width: '75%' }} />
        <div className="h-3 rounded bg-bg-elevated" style={{ width: '50%' }} />
        <div className="h-40 w-full rounded-xl bg-bg-elevated" />
      </div>
    );
  }

  if (!item) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Sticky header */}
      <div
        className="border-b border-border-default bg-bg-surface"
        style={{
          position: 'sticky', top: 0, zIndex: 10,
          padding: '12px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <button
          onClick={() => selectNews(null)}
          className="flex items-center rounded-lg font-mono text-sm text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary"
          style={{ gap: 6, padding: '6px 10px' }}
        >
          <ArrowLeft size={16} />
          <span className="md:hidden">Back</span>
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg text-text-secondary transition hover:bg-bg-elevated hover:text-accent"
            style={{ padding: 8 }}
            title="Open original article"
          >
            <ExternalLink size={16} />
          </a>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* Meta line: source + type badge */}
          <div className="font-mono text-text-secondary" style={{ fontSize: 12, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
            <span className="rounded-lg bg-warning/15 text-warning" style={{ padding: '3px 8px' }}>News</span>
            <span>{item.source_name}</span>
          </div>

          {/* Title */}
          <h2 className="font-sans font-semibold text-text-primary" style={{ fontSize: 20, lineHeight: 1.35 }}>
            {item.title}
          </h2>

          {/* Author */}
          {item.author && (
            <p className="font-mono text-text-secondary" style={{ fontSize: 12 }}>
              {item.author}
            </p>
          )}

          {/* Dates */}
          <div className="font-mono text-text-tertiary" style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {item.published_at && <span>Published: {formatDate(item.published_at)}</span>}
            <span>Fetched: {formatDateTime(item.created_at)}</span>
            {item.full_text_scraped_at && <span>Full text scraped: {formatDateTime(item.full_text_scraped_at)}</span>}
          </div>

          {/* External link */}
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center font-mono text-accent hover:underline"
            style={{ gap: 4, fontSize: 12 }}
          >
            {item.url.replace(/^https?:\/\//, '').slice(0, 60)}...
            <ExternalLink size={11} />
          </a>

          {/* Tags */}
          {item.tags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
              <span className="font-mono text-text-tertiary" style={{ fontSize: 12, flexShrink: 0 }}>Tags:</span>
              {item.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-warning/10 font-mono text-xs text-warning" style={{ padding: '3px 12px' }}>
                  {tag}
                </span>
              ))}
            </div>
          )}

          {/* Relevance Score */}
          {item.relevance_score !== null && (
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>Relevance Score</span>
                <span className={cn('font-mono font-semibold', relevanceColor(item.relevance_score))} style={{ fontSize: 28 }}>
                  {item.relevance_score.toFixed(2)}
                </span>
              </div>
              <div className="rounded-full bg-border-default" style={{ height: 6, overflow: 'hidden' }}>
                <div
                  className={cn('rounded-full', relevanceBg(item.relevance_score).replace('bg-', 'bg-').replace('/20', ''))}
                  style={{
                    height: '100%',
                    width: `${Math.min(item.relevance_score * 100, 100)}%`,
                    transition: 'width 0.3s',
                    backgroundColor: item.relevance_score >= 0.7 ? 'var(--color-score-high, #22c55e)' : item.relevance_score >= 0.4 ? 'var(--color-score-mid, #f59e0b)' : '#888',
                  }}
                />
              </div>
            </div>
          )}

          {/* Cluster siblings */}
          {item.cluster_also_covered_in.length > 0 && (
            <Section title="Also Covered By">
              <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 16 }}>
                {item.cluster_also_covered_in.map((sibling) => (
                  <div key={sibling.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0' }}>
                    <span className="font-mono text-xs text-text-tertiary">{sibling.source_name}</span>
                    <a
                      href={sibling.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs text-accent hover:underline"
                      style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    >
                      {sibling.title}
                    </a>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Full text */}
          <Section title="Article Content">
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
              {item.full_text ? (
                <div className="text-text-primary" style={{ fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                  {item.full_text}
                </div>
              ) : item.excerpt ? (
                <>
                  <p className="text-text-primary" style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 16 }}>
                    {item.excerpt}
                  </p>
                  <button
                    onClick={() => scrapeMutation.mutate()}
                    disabled={scrapeMutation.isPending}
                    className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                    style={{ gap: 8, padding: '10px 16px' }}
                  >
                    {scrapeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Info size={14} />}
                    Fetch full article
                  </button>
                  {scrapeMutation.isSuccess && (
                    <p className="font-mono text-xs text-success" style={{ marginTop: 8 }}>Full text fetched. Refreshing...</p>
                  )}
                  {scrapeMutation.isError && (
                    <p className="font-mono text-xs text-danger" style={{ marginTop: 8 }}>
                      Could not fetch full text (paywall or blocked)
                    </p>
                  )}
                </>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
                  <p className="font-mono text-xs text-text-tertiary">
                    No article text available yet.
                  </p>
                  <button
                    onClick={() => scrapeMutation.mutate()}
                    disabled={scrapeMutation.isPending}
                    className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                    style={{ gap: 8, padding: '10px 16px' }}
                  >
                    {scrapeMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Info size={14} />}
                    Fetch full article
                  </button>
                </div>
              )}
            </div>
          </Section>

          {/* Actions — star + rate */}
          <Section title="Actions">
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Star */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <button
                  onClick={() => starMutation.mutate()}
                  disabled={starMutation.isPending}
                  className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-accent hover:text-accent"
                  style={{ gap: 8, padding: '10px 16px' }}
                >
                  <Bookmark size={14} />
                  Star
                </button>
                <button
                  onClick={() => unstarMutation.mutate()}
                  disabled={unstarMutation.isPending}
                  className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-border-strong hover:text-text-primary"
                  style={{ gap: 8, padding: '10px 16px' }}
                >
                  Unstar
                </button>
              </div>

              {/* Rate */}
              <div>
                <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 10 }}>Rate this article:</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => rateMutation.mutate('thumbs_up')}
                    disabled={rateMutation.isPending}
                    className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-success hover:text-success"
                    style={{ gap: 6, padding: '10px 16px' }}
                  >
                    <ThumbsUp size={14} /> Useful
                  </button>
                  <button
                    onClick={() => rateMutation.mutate('thumbs_down')}
                    disabled={rateMutation.isPending}
                    className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-danger hover:text-danger"
                    style={{ gap: 6, padding: '10px 16px' }}
                  >
                    <ThumbsDown size={14} /> Not relevant
                  </button>
                </div>
                {rateMutation.isSuccess && (
                  <p className="font-mono text-xs text-success" style={{ marginTop: 8 }}>Rating submitted</p>
                )}
              </div>
            </div>
          </Section>

          {/* Source info */}
          <Section title="Source Info">
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div className="font-mono text-xs text-text-secondary">
                Source: <strong className="text-text-primary">{item.source_name}</strong>
              </div>
              <div className="font-mono text-xs text-text-secondary">
                Authority weight: <strong className="text-text-primary">{item.authority_weight.toFixed(2)}</strong>
              </div>
              <a
                href={item.source_website}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-xs text-accent hover:underline inline-flex items-center"
                style={{ gap: 4 }}
              >
                {item.source_website} <ExternalLink size={10} />
              </a>
            </div>
          </Section>

          <div style={{ height: 24 }} />
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3
        className="font-mono font-medium tracking-widest text-text-tertiary uppercase"
        style={{ fontSize: 11, marginBottom: 12 }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}
