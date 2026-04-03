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
        'group cursor-pointer rounded-2xl border border-border-default bg-bg-surface transition-all',
        'hover:border-border-strong',
        isSelected && 'border-accent bg-bg-elevated',
      )}
      style={{ padding: 20 }}
    >
      {/* Top row: journal badge + score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <span className="rounded-lg bg-bg-elevated font-mono text-xs text-text-secondary" style={{ padding: '4px 10px' }}>
            {paper.journal}
          </span>
          {paper.early_access && (
            <span className="rounded-lg bg-warning/15 font-mono text-xs text-warning" style={{ padding: '4px 10px' }}>
              Early Access
            </span>
          )}
        </div>
        {paper.relevance_score !== null && (
          <span
            className={cn('rounded-xl font-mono text-sm font-semibold', scoreBg, scoreColor)}
            style={{ padding: '6px 12px', flexShrink: 0 }}
          >
            {paper.relevance_score.toFixed(1)}
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="font-sans font-semibold text-text-primary line-clamp-2" style={{ fontSize: 16, lineHeight: 1.45, marginBottom: 8 }}>
        {paper.title}
      </h3>

      {/* Authors */}
      <p className="font-mono text-xs text-text-secondary" style={{ marginBottom: 8, lineHeight: 1.5 }}>
        {paper.authors.slice(0, 10).join(', ')}
        {paper.authors.length > 10 && ` +${paper.authors.length - 10} more`}
      </p>

      {/* Dates + DOI */}
      <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 12 }}>
        {paper.online_date && <>Online: {formatDate(paper.online_date)}</>}
        {paper.online_date && paper.published_date && ' · '}
        {paper.published_date && <>Published: {formatDate(paper.published_date)}</>}
        {!paper.online_date && !paper.published_date && 'Date not available'}
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
        <p className="text-sm leading-relaxed text-text-secondary line-clamp-3" style={{ marginBottom: 16 }}>
          {paper.abstract}
        </p>
      )}

      {/* Bottom row: categories + actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {paper.categories.slice(0, 3).map((cat) => (
            <span
              key={cat}
              className="rounded-full bg-bg-elevated font-mono text-xs text-text-tertiary"
              style={{ padding: '3px 10px' }}
            >
              {cat}
            </span>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
            onClick={(e) => { e.stopPropagation(); }}
            title="Play podcast"
            style={{ padding: 8 }}
          >
            <Headphones size={16} />
          </button>
          <button
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-accent"
            onClick={(e) => { e.stopPropagation(); }}
            title="Share"
            style={{ padding: 8 }}
          >
            <Share2 size={16} />
          </button>
          <button
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-warning"
            onClick={(e) => { e.stopPropagation(); }}
            title="Rate"
            style={{ padding: 8 }}
          >
            <Star size={16} />
          </button>
        </div>
      </div>
    </article>
  );
}
