import { Headphones, Share2, Star } from 'lucide-react';
import type { Paper } from '@/types';
import { cn, getScoreColor, getScoreBgColor, formatDate } from '@/lib/utils';

interface PaperCardProps {
  paper: Paper;
  isSelected?: boolean;
  onClick?: () => void;
}

export default function PaperCard({ paper, isSelected, onClick }: PaperCardProps) {
  const scoreColor = getScoreColor(paper.relevance_score);
  const scoreBg = getScoreBgColor(paper.relevance_score);

  return (
    <article
      onClick={onClick}
      className={cn(
        'group cursor-pointer rounded-xl border border-border-default bg-bg-surface p-4 transition-all',
        'hover:border-border-strong hover:border-l-accent hover:border-l-2',
        isSelected && 'border-accent border-l-accent border-l-2 bg-bg-elevated',
      )}
    >
      {/* Top row: journal badge + score */}
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-bg-elevated px-2 py-0.5 font-mono text-xs text-text-secondary">
            {paper.journal}
          </span>
          {paper.early_access && (
            <span className="rounded-md bg-warning/15 px-2 py-0.5 font-mono text-xs text-warning">
              Early Access
            </span>
          )}
        </div>
        {paper.relevance_score !== null && (
          <span
            className={cn(
              'shrink-0 rounded-lg px-2.5 py-1 font-mono text-sm font-medium',
              scoreBg,
              scoreColor,
            )}
          >
            {paper.relevance_score.toFixed(1)}
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="mb-1.5 font-serif text-base leading-snug font-semibold text-text-primary line-clamp-2">
        {paper.title}
      </h3>

      {/* Authors + Date */}
      <p className="mb-2 font-mono text-xs text-text-secondary">
        {paper.authors.slice(0, 3).join(', ')}
        {paper.authors.length > 3 && ` +${paper.authors.length - 3}`}
        {paper.published_date && ` · ${formatDate(paper.published_date)}`}
        {paper.doi && (
          <>
            {' · '}
            <a
              href={`https://doi.org/${paper.doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              DOI
            </a>
          </>
        )}
      </p>

      {/* Abstract preview */}
      {paper.abstract && (
        <p className="mb-3 text-sm leading-relaxed text-text-secondary line-clamp-3">
          {paper.abstract}
        </p>
      )}

      {/* Bottom row: categories + actions */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {paper.categories.slice(0, 3).map((cat) => (
            <span
              key={cat}
              className="rounded-full bg-bg-elevated px-2 py-0.5 font-mono text-xs text-text-tertiary"
            >
              {cat}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <button
            className="rounded-md p-1.5 text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
            onClick={(e) => { e.stopPropagation(); }}
            title="Play podcast"
          >
            <Headphones size={15} />
          </button>
          <button
            className="rounded-md p-1.5 text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
            onClick={(e) => { e.stopPropagation(); }}
            title="Share"
          >
            <Share2 size={15} />
          </button>
          <button
            className="rounded-md p-1.5 text-text-tertiary transition hover:bg-bg-elevated hover:text-warning"
            onClick={(e) => { e.stopPropagation(); }}
            title="Rate"
          >
            <Star size={15} />
          </button>
        </div>
      </div>
    </article>
  );
}
