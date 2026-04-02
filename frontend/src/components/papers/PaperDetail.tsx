import { useState } from 'react';
import { ArrowLeft, ExternalLink, Share2, Play, Loader2 } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { usePaper } from '@/hooks/usePapers';
import { usePodcastStatus, useGeneratePodcast } from '@/hooks/usePodcast';
import { useUIStore } from '@/stores/uiStore';
import { usePlayerStore } from '@/stores/playerStore';
import { cn, getScoreColor, formatDate } from '@/lib/utils';
import api from '@/lib/api';
import RatingSlider from '@/components/ratings/RatingSlider';
import FeedbackDialog from '@/components/ratings/FeedbackDialog';
import ShareModal from '@/components/sharing/ShareModal';
import type { PaperSummary } from '@/types';

interface RatingResult {
  rating_id: string;
  follow_up_question: string | null;
  follow_up_options: string[] | null;
}

function parseSummary(summaryStr: string | null): PaperSummary | null {
  if (!summaryStr) return null;
  try {
    return JSON.parse(summaryStr);
  } catch {
    return null;
  }
}

export default function PaperDetail() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const selectPaper = useUIStore((s) => s.selectPaper);
  const { data: paper, isLoading } = usePaper(selectedPaperId);
  const queryClient = useQueryClient();

  const [feedback, setFeedback] = useState<RatingResult | null>(null);
  const [showShareModal, setShowShareModal] = useState(false);
  const [voiceMode, setVoiceMode] = useState<'single' | 'dual'>('single');
  const { data: podcastStatus } = usePodcastStatus(selectedPaperId, voiceMode);
  const generatePodcast = useGeneratePodcast();
  const setTrack = usePlayerStore((s) => s.setTrack);
  const apiBase = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

  const ratingMutation = useMutation({
    mutationFn: async (value: number) => {
      const { data } = await api.post<RatingResult>('/api/v1/ratings', {
        paper_id: selectedPaperId,
        rating: value,
      });
      return data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['ratings'] });
      if (data.follow_up_question && data.follow_up_options) {
        setFeedback(data);
      }
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: async ({ ratingId, option }: { ratingId: string; option: string }) => {
      await api.post(`/api/v1/ratings/${ratingId}/feedback`, null, {
        params: { feedback_type: option },
      });
    },
  });

  if (!selectedPaperId) return null;

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4 p-6">
        <div className="h-4 w-16 rounded bg-bg-elevated" />
        <div className="h-6 w-full rounded bg-bg-elevated" />
        <div className="h-6 w-3/4 rounded bg-bg-elevated" />
        <div className="h-3 w-1/2 rounded bg-bg-elevated" />
        <div className="h-40 w-full rounded bg-bg-elevated" />
      </div>
    );
  }

  if (!paper) return null;

  const summary = parseSummary(paper.summary);
  const scoreColor = getScoreColor(paper.relevance_score);

  return (
    <>
      <div className="flex h-full flex-col overflow-y-auto bg-bg-surface">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border-default bg-bg-surface px-4 py-3">
          <button
            onClick={() => selectPaper(null)}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-sm text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary"
          >
            <ArrowLeft size={16} />
            <span className="md:hidden">Back</span>
          </button>
          <button
            onClick={() => setShowShareModal(true)}
            className="rounded-md p-1.5 text-text-secondary transition hover:bg-bg-elevated hover:text-accent"
          >
            <Share2 size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-6 p-5">
          {/* Meta */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-text-secondary">
            <span>{paper.journal}</span>
            <span>·</span>
            <span>{formatDate(paper.published_date)}</span>
            {paper.early_access && (
              <>
                <span>·</span>
                <span className="text-warning">Early Access</span>
              </>
            )}
          </div>

          {/* Title */}
          <h2 className="font-serif text-xl leading-tight font-semibold text-text-primary">
            {paper.title}
          </h2>

          {/* Authors */}
          <p className="font-mono text-xs text-text-secondary">
            {paper.authors.join(', ')}
          </p>

          {/* DOI */}
          {paper.doi && (
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-mono text-xs text-accent hover:underline"
            >
              {paper.doi}
              <ExternalLink size={11} />
            </a>
          )}

          {/* Relevance Score */}
          {paper.relevance_score !== null && (
            <div className="rounded-lg border border-border-default bg-bg-base p-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-mono text-xs text-text-secondary">Relevance Score</span>
                <span className={cn('font-mono text-2xl font-medium', scoreColor)}>
                  {paper.relevance_score.toFixed(1)}
                  <span className="text-sm text-text-tertiary">/10</span>
                </span>
              </div>
              <div className="mt-2 h-1.5 w-full rounded-full bg-border-default">
                <div
                  className={cn('h-full rounded-full', scoreColor.replace('text-', 'bg-'))}
                  style={{ width: `${(paper.relevance_score / 10) * 100}%` }}
                />
              </div>
              {paper.score_reasoning && (
                <p className="mt-2 text-sm text-text-secondary">{paper.score_reasoning}</p>
              )}
            </div>
          )}

          {/* AI Summary */}
          {summary && (
            <div className="space-y-3">
              <h3 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">
                AI Summary
              </h3>
              <div className="space-y-3 rounded-lg border border-border-default bg-bg-base p-4">
                <div>
                  <p className="mb-1 font-mono text-xs text-accent">Research Gap</p>
                  <p className="text-sm text-text-primary">{summary.research_gap}</p>
                </div>
                <div>
                  <p className="mb-1 font-mono text-xs text-accent">Methodology</p>
                  <p className="text-sm text-text-primary">{summary.methodology}</p>
                </div>
                <div>
                  <p className="mb-1 font-mono text-xs text-accent">Key Findings</p>
                  <p className="text-sm text-text-primary">{summary.key_findings}</p>
                </div>
                <div>
                  <p className="mb-1 font-mono text-xs text-accent">Relevance</p>
                  <p className="text-sm text-text-primary">{summary.relevance_to_energy_group}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-text-tertiary">Suggested:</span>
                  <span className={cn(
                    'rounded-full px-2.5 py-0.5 font-mono text-xs',
                    summary.suggested_action === 'read_fully' && 'bg-success/15 text-success',
                    summary.suggested_action === 'skim' && 'bg-warning/15 text-warning',
                    summary.suggested_action === 'monitor' && 'bg-bg-elevated text-text-secondary',
                  )}>
                    {summary.suggested_action.replace('_', ' ')}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Podcast */}
          <div className="space-y-3">
            <h3 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">
              Podcast
            </h3>
            <div className="rounded-lg border border-border-default bg-bg-base p-4 space-y-3">
              {/* Voice mode selector */}
              <div className="flex gap-2">
                <button
                  onClick={() => setVoiceMode('single')}
                  className={cn(
                    'rounded-lg px-3 py-1.5 font-mono text-xs transition',
                    voiceMode === 'single' ? 'bg-accent text-white' : 'bg-bg-elevated text-text-secondary hover:text-text-primary',
                  )}
                >
                  Single voice
                </button>
                <button
                  onClick={() => setVoiceMode('dual')}
                  className={cn(
                    'rounded-lg px-3 py-1.5 font-mono text-xs transition',
                    voiceMode === 'dual' ? 'bg-accent text-white' : 'bg-bg-elevated text-text-secondary hover:text-text-primary',
                  )}
                >
                  Dual voice
                </button>
              </div>

              {podcastStatus?.status === 'ready' && podcastStatus.podcast ? (
                <button
                  onClick={() => {
                    const url = `${apiBase}${podcastStatus.podcast!.audio_url}`;
                    setTrack(url, paper.title, paper.journal);
                  }}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
                >
                  <Play size={14} />
                  Play {podcastStatus.podcast.duration_seconds ? `(${Math.floor(podcastStatus.podcast.duration_seconds / 60)}m ${podcastStatus.podcast.duration_seconds % 60}s)` : ''}
                </button>
              ) : podcastStatus?.status === 'generating' ? (
                <div className="flex items-center justify-center gap-2 py-3">
                  <Loader2 size={16} className="animate-spin text-accent" />
                  <span className="font-mono text-sm text-text-secondary">Generating podcast...</span>
                </div>
              ) : (
                <button
                  onClick={() => generatePodcast.mutate({ paperId: paper.id, voiceMode })}
                  disabled={generatePodcast.isPending}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-border-default bg-bg-elevated py-2.5 font-mono text-sm text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  {generatePodcast.isPending ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Play size={14} />
                  )}
                  Generate Podcast
                </button>
              )}

              {podcastStatus?.status === 'failed' && (
                <p className="text-center font-mono text-xs text-danger">Generation failed. Try again.</p>
              )}
            </div>
          </div>

          {/* Rating */}
          <div className="space-y-3">
            <h3 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">
              Your Rating
            </h3>
            <div className="rounded-lg border border-border-default bg-bg-base p-4">
              <RatingSlider
                onSubmit={(value) => ratingMutation.mutate(value)}
                loading={ratingMutation.isPending}
              />
              {ratingMutation.isSuccess && !feedback && (
                <p className="mt-2 text-center font-mono text-xs text-success">Rating submitted</p>
              )}
              {ratingMutation.isError && (
                <p className="mt-2 text-center font-mono text-xs text-danger">Failed to submit</p>
              )}
            </div>
          </div>

          {/* PDF upload placeholder */}
          <div className="space-y-3">
            <h3 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">
              Upload Full Text
            </h3>
            <div className="rounded-lg border border-dashed border-border-strong bg-bg-base p-6 text-center">
              <p className="font-mono text-sm text-text-tertiary">
                PDF upload coming in Phase 6
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Feedback dialog */}
      {feedback?.follow_up_question && feedback.follow_up_options && (
        <FeedbackDialog
          question={feedback.follow_up_question}
          options={feedback.follow_up_options}
          onSelect={(option) => {
            feedbackMutation.mutate({ ratingId: feedback.rating_id, option });
          }}
          onDismiss={() => setFeedback(null)}
        />
      )}

      {/* Share modal */}
      {showShareModal && paper && (
        <ShareModal paper={paper} onClose={() => setShowShareModal(false)} />
      )}
    </>
  );
}
