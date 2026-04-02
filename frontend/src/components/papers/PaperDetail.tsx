import { ArrowLeft, ExternalLink, Share2 } from 'lucide-react';
import { usePaper } from '@/hooks/usePapers';
import { useUIStore } from '@/stores/uiStore';
import { cn, getScoreColor, formatDate } from '@/lib/utils';
import RatingSlider from '@/components/ratings/RatingSlider';
import type { PaperSummary } from '@/types';

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
        <button className="rounded-md p-1.5 text-text-secondary transition hover:bg-bg-elevated hover:text-accent">
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
            {/* Score bar */}
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

        {/* Podcast section placeholder */}
        <div className="space-y-3">
          <h3 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">
            Podcast
          </h3>
          <div className="rounded-lg border border-border-default bg-bg-base p-4">
            <p className="font-mono text-sm text-text-tertiary">Podcast generation coming in Phase 5</p>
          </div>
        </div>

        {/* Rating */}
        <div className="space-y-3">
          <h3 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">
            Your Rating
          </h3>
          <div className="rounded-lg border border-border-default bg-bg-base p-4">
            <RatingSlider onSubmit={() => {}} />
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
  );
}
