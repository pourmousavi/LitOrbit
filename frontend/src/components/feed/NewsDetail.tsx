import React, { useEffect, useState } from 'react';
import { ArrowLeft, ExternalLink, Bookmark, Loader2, Info, Play, Download, Trash2, Share2, LibraryBig } from 'lucide-react';
import ShareModal from '@/components/sharing/ShareModal';
import { useScholarLibStore } from '@/stores/scholarLibStore';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNewsItem } from '@/hooks/useNewsItem';
import { useUIStore } from '@/stores/uiStore';
import { usePlayerStore } from '@/stores/playerStore';
import { cn, formatDate, getScoreColor } from '@/lib/utils';
import RatingSlider from '@/components/ratings/RatingSlider';
import FeedbackDialog from '@/components/ratings/FeedbackDialog';
import { useDeletePodcast } from '@/hooks/usePodcast';
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

  const scrapeMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/news/${selectedNewsId}/scrape`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['news-item', selectedNewsId] });
    },
  });

  // Fetch existing rating
  const { data: existingRating } = useQuery<{ rating: number | null }>({
    queryKey: ['news-rating', selectedNewsId],
    queryFn: async () => (await api.get(`/api/v1/news/${selectedNewsId}/my-rating`)).data,
    enabled: !!selectedNewsId,
  });

  interface NewsRatingResult {
    rating_id: string;
    follow_up_question: string | null;
    follow_up_options: string[] | null;
  }

  const [feedback, setFeedback] = useState<NewsRatingResult | null>(null);

  const ratingMutation = useMutation({
    mutationFn: async (value: number) => {
      const { data } = await api.post<NewsRatingResult>(`/api/v1/news/${selectedNewsId}/rate`, { rating: value });
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['news-rating', selectedNewsId] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      queryClient.invalidateQueries({ queryKey: ['engagement', 'pulse'] });
      if (data.follow_up_question && data.follow_up_options) {
        setFeedback(data);
      }
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: async (option: string) => {
      await api.post(`/api/v1/news/${selectedNewsId}/rate-feedback`, null, { params: { feedback_type: option } });
    },
  });

  // Podcast
  const [voiceMode, setVoiceMode] = useState<'single' | 'dual'>('single');
  const { data: podcastStatus } = useQuery<{
    status: string; podcast: { id: string; audio_url: string; duration_seconds: number | null } | null; error?: string; estimated_seconds?: number;
  }>({
    queryKey: ['news-podcast', selectedNewsId, voiceMode],
    queryFn: async () => (await api.get(`/api/v1/news/${selectedNewsId}/podcast`, { params: { voice_mode: voiceMode } })).data,
    enabled: !!selectedNewsId,
    refetchInterval: (query) => query.state.data?.status === 'generating' ? 3000 : false,
  });
  const generatePodcast = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/api/v1/news/${selectedNewsId}/podcast/generate`, null, { params: { voice_mode: voiceMode } });
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['news-podcast', selectedNewsId, voiceMode], { status: 'generating', podcast: null, estimated_seconds: data.estimated_seconds });
      queryClient.invalidateQueries({ queryKey: ['news-podcast', selectedNewsId] });
    },
  });
  const deletePodcast = useDeletePodcast();
  const setTrack = usePlayerStore((s) => s.setTrack);
  const apiBase = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

  // Share + ScholarLib
  const [showShareModal, setShowShareModal] = useState(false);
  const scholarLibConnected = useScholarLibStore((s) => s.status === 'connected');

  // Mark as read on open
  useEffect(() => {
    if (selectedNewsId) {
      api.post(`/api/v1/news/${selectedNewsId}/mark_read`).catch(() => {});
    }
  }, [selectedNewsId]);

  // Reset feedback on item change
  useEffect(() => {
    setFeedback(null);
    ratingMutation.reset();
  }, [selectedNewsId]);

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

  const scoreColor = getScoreColor;
  const parsedSummary: { key_points?: string; industry_impact?: string; relevance?: string; suggested_action?: string } | null = (() => {
    if (!item.summary) return null;
    try { return JSON.parse(item.summary); } catch { return null; }
  })();

  return (
    <>
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
          <button
            onClick={() => setShowShareModal(true)}
            className="rounded-lg text-text-secondary transition hover:bg-bg-elevated hover:text-accent"
            style={{ padding: 8 }}
            title="Share"
          >
            <Share2 size={16} />
          </button>
          {scholarLibConnected && (
            <button
              className="rounded-lg text-text-secondary transition hover:bg-bg-elevated hover:text-accent"
              style={{ padding: 8 }}
              title="ScholarLib (coming soon)"
              disabled
            >
              <LibraryBig size={16} />
            </button>
          )}
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

          {/* Relevance Score (LLM-scored, same 0-10 scale as papers) */}
          {item.llm_score !== null ? (
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>Relevance Score</span>
                <span className={cn('font-mono font-semibold', scoreColor(item.llm_score))} style={{ fontSize: 28 }}>
                  {item.llm_score.toFixed(1)}
                  <span className="text-text-tertiary" style={{ fontSize: 14 }}>/10</span>
                </span>
              </div>
              <div className="rounded-full bg-border-default" style={{ height: 6, overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${(item.llm_score / 10) * 100}%`,
                    transition: 'width 0.3s',
                    borderRadius: 999,
                    backgroundColor: item.llm_score >= 8 ? 'var(--color-score-high, #22c55e)' : item.llm_score >= 5 ? 'var(--color-score-mid, #f59e0b)' : '#888',
                  }}
                />
              </div>
              {item.llm_score_reasoning && (
                <p className="text-text-secondary" style={{ fontSize: 13, marginTop: 12, lineHeight: 1.5 }}>{item.llm_score_reasoning}</p>
              )}
            </div>
          ) : item.relevance_score !== null ? (
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>Anchor Similarity</span>
                <span className={cn('font-mono font-semibold', relevanceColor(item.relevance_score))} style={{ fontSize: 20 }}>
                  {item.relevance_score.toFixed(2)}
                </span>
              </div>
              <p className="font-mono text-xs text-text-tertiary">
                Not yet scored by AI. Score will be generated on next ingest run.
              </p>
            </div>
          ) : null}

          {/* AI Summary */}
          {parsedSummary && (
            <Section title="AI Summary">
              <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                {parsedSummary.key_points && <SummaryBlock label="Key Points" text={parsedSummary.key_points} />}
                {parsedSummary.industry_impact && <SummaryBlock label="Industry Impact" text={parsedSummary.industry_impact} />}
                {parsedSummary.relevance && <SummaryBlock label="Relevance" text={parsedSummary.relevance} />}
                {parsedSummary.suggested_action && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>Suggested:</span>
                    <span className={cn(
                      'rounded-full font-mono',
                      parsedSummary.suggested_action === 'read_fully' && 'bg-success/15 text-success',
                      parsedSummary.suggested_action === 'skim' && 'bg-warning/15 text-warning',
                      parsedSummary.suggested_action === 'monitor' && 'bg-bg-elevated text-text-secondary',
                    )} style={{ fontSize: 12, padding: '4px 12px' }}>
                      {parsedSummary.suggested_action.replace('_', ' ')}
                    </span>
                  </div>
                )}
              </div>
            </Section>
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
          {/* Podcast */}
          <Section title="Podcast">
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', gap: 8 }}>
                {(['single', 'dual'] as const).map((mode) => (
                  <button key={mode} onClick={() => setVoiceMode(mode)}
                    className={cn('rounded-xl font-mono text-xs transition', voiceMode === mode ? 'bg-accent text-white' : 'bg-bg-elevated text-text-secondary hover:text-text-primary')}
                    style={{ padding: '8px 16px' }}>
                    {mode === 'single' ? 'Single voice' : 'Dual voice'}
                  </button>
                ))}
              </div>

              {podcastStatus?.status === 'ready' && podcastStatus.podcast ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => setTrack(`${apiBase}${podcastStatus.podcast!.audio_url}`, item.title, item.source_name)}
                    className="flex items-center justify-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
                    style={{ gap: 8, padding: '12px 0', flex: 1 }}>
                    <Play size={15} />
                    Play {podcastStatus.podcast.duration_seconds ? `(${Math.floor(podcastStatus.podcast.duration_seconds / 60)}m ${podcastStatus.podcast.duration_seconds % 60}s)` : ''}
                  </button>
                  <a href={`${apiBase}/api/v1/podcasts/download/${podcastStatus.podcast.id}`}
                    className="flex items-center justify-center rounded-xl border border-border-default bg-bg-elevated text-text-secondary transition hover:border-accent hover:text-accent"
                    style={{ padding: '12px 14px' }} title="Download MP3">
                    <Download size={16} />
                  </a>
                  <button onClick={() => { if (confirm('Delete this podcast?')) deletePodcast.mutate(podcastStatus.podcast!.id); }}
                    disabled={deletePodcast.isPending}
                    className="flex items-center justify-center rounded-xl border border-border-default bg-bg-elevated text-text-secondary transition hover:border-danger hover:text-danger disabled:opacity-50"
                    style={{ padding: '12px 14px' }} title="Delete podcast">
                    <Trash2 size={16} />
                  </button>
                </div>
              ) : podcastStatus?.status === 'generating' ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '14px 0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Loader2 size={16} className="animate-spin text-accent" />
                    <span className="font-mono text-sm text-text-secondary">Generating podcast...</span>
                  </div>
                  <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>
                    You can navigate away — it runs in the background.
                  </span>
                </div>
              ) : (
                <button onClick={() => generatePodcast.mutate()}
                  disabled={generatePodcast.isPending || (!item.summary && !item.full_text && !item.excerpt)}
                  className="flex items-center justify-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                  style={{ gap: 8, padding: '12px 0', width: '100%' }}>
                  {generatePodcast.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                  Generate Podcast
                </button>
              )}

              {podcastStatus?.status === 'failed' && (
                <div className="rounded-xl bg-danger/10" style={{ padding: '10px 14px' }}>
                  <p className="font-mono text-xs text-danger">Generation failed.</p>
                </div>
              )}
            </div>
          </Section>

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

          {/* Star */}
          <Section title="Bookmark">
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
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
          </Section>

          {/* Rating */}
          <Section title="Your Rating" key={`rating-${selectedNewsId}`}>
            <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
              {existingRating?.rating != null && (
                <p className="font-mono text-xs text-text-secondary" style={{ textAlign: 'center', marginBottom: 12 }}>
                  You rated this article <strong>{existingRating.rating}/10</strong>
                </p>
              )}
              <RatingSlider
                key={selectedNewsId}
                initialValue={existingRating?.rating ?? undefined}
                onSubmit={(value) => ratingMutation.mutate(value)}
                loading={ratingMutation.isPending}
              />
              {ratingMutation.isSuccess && !feedback && (
                <p className="font-mono text-xs text-success" style={{ textAlign: 'center', marginTop: 10 }}>Rating submitted</p>
              )}
              {ratingMutation.isError && (
                <p className="font-mono text-xs text-danger" style={{ textAlign: 'center', marginTop: 10 }}>Failed to submit</p>
              )}
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

    {/* Feedback dialog */}
    {feedback?.follow_up_question && feedback.follow_up_options && (
      <FeedbackDialog
        question={feedback.follow_up_question}
        options={feedback.follow_up_options}
        onSelect={(option) => feedbackMutation.mutate(option)}
        onDismiss={() => setFeedback(null)}
      />
    )}

    {/* Share modal */}
    {showShareModal && item && (
      <ShareModal
        paper={{
          id: item.id,
          title: item.title,
          authors: item.author ? [item.author] : [],
          abstract: item.excerpt,
          journal: item.source_name,
          journal_source: 'news',
          doi: null,
          full_text: item.full_text,
          published_date: item.published_at,
          online_date: null,
          early_access: false,
          url: item.url,
          pdf_path: null,
          keywords: item.tags,
          categories: item.categories,
          summary: item.summary,
          relevance_score: item.llm_score,
          score_reasoning: item.llm_score_reasoning,
          created_at: item.created_at,
          created_by_name: null,
          collections: [],
          is_opened: true,
          is_favorite: false,
          user_rating: null,
        }}
        onClose={() => setShowShareModal(false)}
      />
    )}
    </>
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

function SummaryBlock({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="font-mono text-accent" style={{ fontSize: 12, marginBottom: 6 }}>{label}</p>
      <p className="text-text-primary" style={{ fontSize: 13, lineHeight: 1.6 }}>{text}</p>
    </div>
  );
}
