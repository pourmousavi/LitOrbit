import { useState, useEffect } from 'react';
import { ArrowLeft, ExternalLink, Share2, Play, Loader2, Trash2, RefreshCw, Download, Plus, X, LibraryBig, Check } from 'lucide-react';
import { useScholarLibStore } from '@/stores/scholarLibStore';
import ScholarLibModal from '@/components/integrations/ScholarLibModal';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usePaper } from '@/hooks/usePapers';
import { usePodcastStatus, useGeneratePodcast, useDeletePodcast } from '@/hooks/usePodcast';
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

  // Reset state when paper changes
  useEffect(() => {
    setFeedback(null);
    ratingMutation.reset();
  }, [selectedPaperId]);

  // Fetch existing rating for this paper
  const { data: existingRating } = useQuery<{ rating: number } | null>({
    queryKey: ['my-rating', selectedPaperId],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/ratings/history');
      const match = data.find((r: any) => r.paper_id === selectedPaperId);
      return match ? { rating: match.rating } : null;
    },
    enabled: !!selectedPaperId,
  });
  const [showShareModal, setShowShareModal] = useState(false);
  const [showScholarLibModal, setShowScholarLibModal] = useState(false);
  const scholarLibConnected = useScholarLibStore((s) => s.status === 'connected');
  const paperSentToScholarLib = useScholarLibStore((s) => selectedPaperId ? s.sentPaperIds.has(selectedPaperId) : false);
  const [voiceMode, setVoiceMode] = useState<'single' | 'dual'>('single');
  const { data: podcastStatus } = usePodcastStatus(selectedPaperId, voiceMode);
  const generatePodcast = useGeneratePodcast();
  const deletePodcast = useDeletePodcast();
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
      queryClient.invalidateQueries({ queryKey: ['my-rating', selectedPaperId] });
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      if (data.follow_up_question && data.follow_up_options) {
        setFeedback(data);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await api.delete(`/api/v1/papers/${selectedPaperId}`);
    },
    onSuccess: () => {
      selectPaper(null);
      queryClient.invalidateQueries({ queryKey: ['papers'] });
    },
    onError: (error: any) => {
      alert(error?.response?.data?.detail || 'Failed to delete paper');
    },
  });

  const rescoreMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/api/v1/papers/${selectedPaperId}/rescore`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper', selectedPaperId] });
      queryClient.invalidateQueries({ queryKey: ['papers'] });
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
      <div className="animate-pulse" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="h-4 rounded bg-bg-elevated" style={{ width: 60 }} />
        <div className="h-6 w-full rounded bg-bg-elevated" />
        <div className="h-6 rounded bg-bg-elevated" style={{ width: '75%' }} />
        <div className="h-3 rounded bg-bg-elevated" style={{ width: '50%' }} />
        <div className="h-40 w-full rounded-xl bg-bg-elevated" />
      </div>
    );
  }

  if (!paper) return null;

  const summary = parseSummary(paper.summary);
  const scoreColor = getScoreColor(paper.relevance_score);

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
            onClick={() => selectPaper(null)}
            className="flex items-center rounded-lg font-mono text-sm text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary"
            style={{ gap: 6, padding: '6px 10px' }}
          >
            <ArrowLeft size={16} />
            <span className="md:hidden">Back</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <button
              onClick={() => rescoreMutation.mutate()}
              disabled={rescoreMutation.isPending}
              className="rounded-lg text-text-secondary transition hover:bg-bg-elevated hover:text-accent"
              style={{ padding: 8 }}
              title="Re-score this paper"
            >
              {rescoreMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            </button>
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
                onClick={() => { if (!paperSentToScholarLib) setShowScholarLibModal(true); }}
                disabled={paperSentToScholarLib}
                className={cn(
                  'rounded-lg transition',
                  paperSentToScholarLib
                    ? 'text-success cursor-default'
                    : 'text-text-secondary hover:bg-bg-elevated hover:text-accent',
                )}
                style={{ padding: 8 }}
                title={paperSentToScholarLib ? 'In ScholarLib' : 'Add to ScholarLib'}
              >
                {paperSentToScholarLib ? <Check size={16} /> : <LibraryBig size={16} />}
              </button>
            )}
            <button
              onClick={() => { if (confirm('Delete this paper?')) deleteMutation.mutate(); }}
              disabled={deleteMutation.isPending}
              className="rounded-lg text-text-secondary transition hover:bg-bg-elevated hover:text-danger"
              style={{ padding: 8 }}
              title="Delete paper"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

            {/* Meta line */}
            <div className="font-mono text-text-secondary" style={{ fontSize: 12, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
              <span>{paper.journal}</span>
              {paper.early_access && (
                <>
                  <span className="text-text-tertiary">&middot;</span>
                  <span className="text-warning">Early Access</span>
                </>
              )}
            </div>

            {/* Title */}
            <h2 className="font-sans font-semibold text-text-primary" style={{ fontSize: 20, lineHeight: 1.35 }}>
              {paper.title}
            </h2>

            {/* Authors */}
            <p className="font-mono text-text-secondary" style={{ fontSize: 12, lineHeight: 1.5 }}>
              {paper.authors.slice(0, 10).join(', ')}
              {paper.authors.length > 10 && ` +${paper.authors.length - 10} more`}
            </p>

            {/* Dates */}
            <div className="font-mono text-text-tertiary" style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {paper.online_date && <span>Online: {formatDate(paper.online_date)}</span>}
              {paper.published_date && <span>Published: {formatDate(paper.published_date)}</span>}
            </div>

            {/* DOI */}
            {paper.doi && (
              <a
                href={`https://doi.org/${paper.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center font-mono text-accent hover:underline"
                style={{ gap: 4, fontSize: 12 }}
              >
                {paper.doi}
                <ExternalLink size={11} />
              </a>
            )}

            {/* Keywords */}
            {paper.keywords && paper.keywords.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
                <span className="font-mono text-text-tertiary" style={{ fontSize: 12, flexShrink: 0 }}>Keywords:</span>
                {paper.keywords.map((kw) => (
                  <span
                    key={kw}
                    className="rounded-full bg-accent/10 font-mono text-xs text-accent"
                    style={{ padding: '3px 12px' }}
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}

            {/* Relevance Score */}
            {paper.relevance_score !== null ? (
              <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>Relevance Score</span>
                  <span className={cn('font-mono font-semibold', scoreColor)} style={{ fontSize: 28 }}>
                    {paper.relevance_score.toFixed(1)}
                    <span className="text-text-tertiary" style={{ fontSize: 14 }}>/10</span>
                  </span>
                </div>
                <div className="rounded-full bg-border-default" style={{ height: 6, overflow: 'hidden' }}>
                  <div
                    className={cn('rounded-full', scoreColor.replace('text-', 'bg-'))}
                    style={{ height: '100%', width: `${(paper.relevance_score / 10) * 100}%`, transition: 'width 0.3s' }}
                  />
                </div>
                {paper.score_reasoning && (
                  <p className="text-text-secondary" style={{ fontSize: 13, marginTop: 12, lineHeight: 1.5 }}>{paper.score_reasoning}</p>
                )}
              </div>
            ) : (
              <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
                <p className="font-mono text-text-secondary" style={{ fontSize: 13, marginBottom: 12 }}>
                  This paper was not scored by the pre-filter. You can manually score it using AI.
                </p>
                <button
                  onClick={() => rescoreMutation.mutate()}
                  disabled={rescoreMutation.isPending}
                  className="flex items-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                  style={{ gap: 8, padding: '10px 20px' }}
                >
                  {rescoreMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
                  Score this paper
                </button>
              </div>
            )}

            {/* Re-score result */}
            {rescoreMutation.isSuccess && rescoreMutation.data && (
              <div className="rounded-2xl border border-success/30 bg-success/5" style={{ padding: 16 }}>
                <p className="font-mono font-medium text-success" style={{ fontSize: 13, marginBottom: 8 }}>Re-score complete</p>
                <div className="font-mono text-text-secondary" style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span>New score: <strong className="text-text-primary">{rescoreMutation.data.max_score}/10</strong></span>
                  <span>Summary {rescoreMutation.data.summary_regenerated ? 'regenerated' : 'unchanged'}</span>
                  {rescoreMutation.data.scores?.map((s: { user: string; score: number; reasoning: string }) => (
                    <span key={s.user} className="text-text-tertiary">{s.reasoning}</span>
                  ))}
                </div>
              </div>
            )}
            {rescoreMutation.isError && (
              <div className="rounded-2xl border border-danger/30 bg-danger/5" style={{ padding: 16 }}>
                <p className="font-mono text-sm text-danger">
                  {(rescoreMutation.error as any)?.response?.data?.detail || 'Re-scoring failed. Try again.'}
                </p>
              </div>
            )}

            {/* AI Summary */}
            {summary && (
              <Section title="AI Summary">
                <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <SummaryBlock label="Research Gap" text={summary.research_gap} />
                  <SummaryBlock label="Methodology" text={summary.methodology} />
                  <SummaryBlock label="Key Findings" text={summary.key_findings} />
                  <SummaryBlock label="Relevance" text={summary.relevance_to_energy_group} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>Suggested:</span>
                    <span className={cn(
                      'rounded-full font-mono',
                      summary.suggested_action === 'read_fully' && 'bg-success/15 text-success',
                      summary.suggested_action === 'skim' && 'bg-warning/15 text-warning',
                      summary.suggested_action === 'monitor' && 'bg-bg-elevated text-text-secondary',
                    )} style={{ fontSize: 12, padding: '4px 12px' }}>
                      {summary.suggested_action.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              </Section>
            )}

            {/* Podcast */}
            <Section title="Podcast">
              <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Voice mode selector */}
                <div style={{ display: 'flex', gap: 8 }}>
                  {(['single', 'dual'] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setVoiceMode(mode)}
                      className={cn(
                        'rounded-xl font-mono text-xs transition',
                        voiceMode === mode ? 'bg-accent text-white' : 'bg-bg-elevated text-text-secondary hover:text-text-primary',
                      )}
                      style={{ padding: '8px 16px' }}
                    >
                      {mode === 'single' ? 'Single voice' : 'Dual voice'}
                    </button>
                  ))}
                </div>

                {podcastStatus?.status === 'ready' && podcastStatus.podcast ? (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => {
                        const url = `${apiBase}${podcastStatus.podcast!.audio_url}`;
                        setTrack(url, paper.title, paper.journal);
                      }}
                      className="flex items-center justify-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
                      style={{ gap: 8, padding: '12px 0', flex: 1 }}
                    >
                      <Play size={15} />
                      Play {podcastStatus.podcast.duration_seconds ? `(${Math.floor(podcastStatus.podcast.duration_seconds / 60)}m ${podcastStatus.podcast.duration_seconds % 60}s)` : ''}
                    </button>
                    <a
                      href={`${apiBase}/api/v1/podcasts/download/${podcastStatus.podcast.id}`}
                      className="flex items-center justify-center rounded-xl border border-border-default bg-bg-elevated text-text-secondary transition hover:border-accent hover:text-accent"
                      style={{ padding: '12px 14px' }}
                      title="Download MP3"
                    >
                      <Download size={16} />
                    </a>
                    <button
                      onClick={() => {
                        if (confirm('Delete this podcast?')) {
                          deletePodcast.mutate(podcastStatus.podcast!.id);
                        }
                      }}
                      disabled={deletePodcast.isPending}
                      className="flex items-center justify-center rounded-xl border border-border-default bg-bg-elevated text-text-secondary transition hover:border-danger hover:text-danger disabled:opacity-50"
                      style={{ padding: '12px 14px' }}
                      title="Delete podcast"
                    >
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
                      Estimated time: ~{podcastStatus.estimated_seconds
                        ? podcastStatus.estimated_seconds < 60
                          ? `${podcastStatus.estimated_seconds}s`
                          : `${Math.floor(podcastStatus.estimated_seconds / 60)}m ${podcastStatus.estimated_seconds % 60}s`
                        : '45s'}. You can navigate away — it runs in the background.
                    </span>
                  </div>
                ) : !paper.summary && !paper.abstract ? (
                  <div className="rounded-xl bg-bg-base border border-border-default" style={{ padding: '12px 16px' }}>
                    <p className="font-mono text-xs text-text-tertiary">
                      This paper needs an AI summary or abstract before a podcast can be generated. Try re-scoring first (refresh icon above).
                    </p>
                  </div>
                ) : (
                  <button
                    onClick={() => generatePodcast.mutate({ paperId: paper.id, voiceMode })}
                    disabled={generatePodcast.isPending}
                    className="flex items-center justify-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                    style={{ gap: 8, padding: '12px 0', width: '100%' }}
                  >
                    {generatePodcast.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                    Generate Podcast
                  </button>
                )}

                {podcastStatus?.status === 'failed' && (
                  <div className="rounded-xl bg-danger/10" style={{ padding: '10px 14px' }}>
                    <p className="font-mono text-xs text-danger">Generation failed.</p>
                    {podcastStatus.error && (
                      <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginTop: 4 }}>
                        {podcastStatus.error.replace('ERROR: ', '')}
                      </p>
                    )}
                  </div>
                )}

                {generatePodcast.isError && (
                  <p className="font-mono text-xs text-danger" style={{ textAlign: 'center' }}>
                    Failed to start generation. Try again.
                  </p>
                )}
              </div>
            </Section>

            {/* Rating */}
            <Section title="Your Rating" key={`rating-${selectedPaperId}`}>
              <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 20 }}>
                {existingRating && (
                  <p className="font-mono text-xs text-text-secondary" style={{ textAlign: 'center', marginBottom: 12 }}>
                    You rated this paper <strong>{existingRating.rating}/10</strong>
                  </p>
                )}
                <RatingSlider
                  key={selectedPaperId}
                  initialValue={existingRating?.rating}
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

            {/* Collections */}
            <Section title="Collections">
              <CollectionAssigner paperId={paper.id} />
            </Section>


            {/* Bottom spacer */}
            <div style={{ height: 24 }} />
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

      {/* ScholarLib modal */}
      {showScholarLibModal && paper && (
        <ScholarLibModal paper={paper} onClose={() => setShowScholarLibModal(false)} />
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

function CollectionAssigner({ paperId }: { paperId: string }) {
  const queryClient = useQueryClient();

  const { data: allCollections } = useQuery({
    queryKey: ['collections'],
    queryFn: async () => (await api.get('/api/v1/collections')).data as { id: string; name: string; color: string }[],
  });

  const { data: paperCollections } = useQuery({
    queryKey: ['paper-collections', paperId],
    queryFn: async () => (await api.get(`/api/v1/collections/paper/${paperId}`)).data as { id: string; name: string; color: string }[],
  });

  const addMutation = useMutation({
    mutationFn: async (collectionId: string) => {
      await api.post(`/api/v1/collections/${collectionId}/papers`, { paper_id: paperId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper-collections', paperId] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      queryClient.invalidateQueries({ queryKey: ['papers'] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (collectionId: string) => {
      await api.delete(`/api/v1/collections/${collectionId}/papers/${paperId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper-collections', paperId] });
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      queryClient.invalidateQueries({ queryKey: ['papers'] });
    },
  });

  const assignedIds = new Set(paperCollections?.map((c) => c.id) || []);
  const unassigned = allCollections?.filter((c) => !assignedIds.has(c.id)) || [];

  return (
    <div className="rounded-2xl border border-border-default bg-bg-base" style={{ padding: 16 }}>
      {/* Current collections */}
      {paperCollections && paperCollections.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: unassigned.length ? 12 : 0 }}>
          {paperCollections.map((col) => (
            <span
              key={col.id}
              className="flex items-center rounded-full font-mono text-xs text-white"
              style={{ gap: 6, padding: '4px 12px', backgroundColor: col.color }}
            >
              {col.name}
              <button
                onClick={() => removeMutation.mutate(col.id)}
                className="opacity-70 hover:opacity-100"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: unassigned.length ? 12 : 0 }}>
          Not in any collection
        </p>
      )}

      {/* Add to collection */}
      {unassigned.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {unassigned.map((col) => (
            <button
              key={col.id}
              onClick={() => addMutation.mutate(col.id)}
              className="flex items-center rounded-full border border-dashed border-border-strong font-mono text-xs text-text-tertiary transition hover:border-accent hover:text-accent"
              style={{ gap: 4, padding: '4px 12px' }}
            >
              <Plus size={11} /> {col.name}
            </button>
          ))}
        </div>
      )}

      {!allCollections?.length && (
        <p className="font-mono text-xs text-text-tertiary">
          No collections yet. Create one from the Collections page.
        </p>
      )}
    </div>
  );
}
