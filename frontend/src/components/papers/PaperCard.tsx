import { Bookmark, Check, Headphones, Info, LibraryBig, Share2, Star } from 'lucide-react';
import { useScholarLibStore } from '@/stores/scholarLibStore';
import type { Paper } from '@/types';
import { cn, getScoreColor, getScoreBgColor, formatDate } from '@/lib/utils';

const SOURCE_LABELS: Record<string, string> = {
  ieee: 'IEEE Xplore',
  scopus: 'Scopus',
  rss: 'RSS Feed',
  manual: 'Manual Upload',
};

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return 'Unknown';
  const d = new Date(dateStr);
  return d.toLocaleString('en-AU', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

interface PaperCardProps {
  paper: Paper;
  isSelected?: boolean;
  onClick?: () => void;
  onToggleFavorite?: () => void;
  onSendToScholarLib?: () => void;
}

export default function PaperCard({ paper, isSelected, onClick, onToggleFavorite, onSendToScholarLib }: PaperCardProps) {
  const scholarLibConnected = useScholarLibStore((s) => s.status === 'connected');
  const paperSentToScholarLib = useScholarLibStore((s) => s.sentPaperIds.has(paper.id));
  const scoreColor = getScoreColor(paper.relevance_score);
  const scoreBg = getScoreBgColor(paper.relevance_score);

  return (
    <article
      onClick={onClick}
      className={cn(
        'group cursor-pointer rounded-2xl border border-border-default bg-bg-surface transition-all overflow-hidden',
        'hover:border-border-strong',
        isSelected && 'border-accent bg-bg-elevated',
        paper.is_opened && !isSelected && 'opacity-60 hover:opacity-100',
      )}
      style={{ padding: 14 }}
    >
      {/* Top row: journal badge + score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <span className="rounded-lg bg-bg-elevated font-mono text-xs text-text-secondary" style={{ padding: '4px 10px' }}>
            {paper.journal}
          </span>
          {paper.is_opened && (
            <span
              className="flex items-center rounded-lg bg-bg-elevated font-mono text-xs text-text-tertiary"
              style={{ padding: '4px 10px', gap: 4 }}
              title="You've already opened this paper"
            >
              <Check size={11} /> Read
            </span>
          )}
          {paper.early_access && (
            <span className="rounded-lg bg-warning/15 font-mono text-xs text-warning" style={{ padding: '4px 10px' }}>
              Early Access
            </span>
          )}
          <div className="group/info relative" onClick={(e) => e.stopPropagation()}>
            <div className="rounded-lg text-text-tertiary transition hover:text-text-secondary" style={{ padding: 2, cursor: 'default' }}>
              <Info size={14} />
            </div>
            <div
              className="pointer-events-none absolute left-0 top-full z-50 mt-1 rounded-xl border border-border-default bg-bg-surface font-mono text-xs text-text-secondary opacity-0 shadow-lg transition-opacity group-hover/info:pointer-events-auto group-hover/info:opacity-100"
              style={{ padding: '10px 14px', width: 260, lineHeight: 1.7 }}
            >
              <div>Fetched: <strong className="text-text-primary">{formatDateTime(paper.created_at)}</strong></div>
              <div>Source: <strong className="text-text-primary">{SOURCE_LABELS[paper.journal_source] || paper.journal_source}</strong></div>
            </div>
          </div>
        </div>
        {paper.relevance_score !== null ? (
          <span
            className={cn('rounded-xl font-mono text-sm font-semibold', scoreBg, scoreColor)}
            style={{ padding: '6px 12px', flexShrink: 0 }}
          >
            {paper.relevance_score.toFixed(1)}
          </span>
        ) : (
          <span
            className="rounded-xl font-mono text-xs text-text-tertiary bg-bg-elevated"
            style={{ padding: '6px 12px', flexShrink: 0 }}
          >
            Not scored
          </span>
        )}
      </div>

      {/* Title */}
      <h3 className="font-sans font-semibold text-text-primary line-clamp-2" style={{ fontSize: 15, lineHeight: 1.4, marginBottom: 6 }}>
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
        {paper.created_by_name && (
          <>
            {' · '}
            <span>Added by {paper.created_by_name}</span>
          </>
        )}
      </p>

      {/* Abstract preview */}
      {paper.abstract && (
        <p className="text-sm leading-relaxed text-text-secondary line-clamp-3" style={{ marginBottom: 16 }}>
          {paper.abstract}
        </p>
      )}

      {/* Keywords */}
      {paper.keywords && paper.keywords.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <span className="font-mono text-text-tertiary" style={{ fontSize: 11, flexShrink: 0 }}>Keywords:</span>
          {paper.keywords.slice(0, 6).map((kw) => (
            <span
              key={kw}
              className="rounded-full bg-accent/10 font-mono text-xs text-accent"
              style={{ padding: '2px 10px' }}
            >
              {kw}
            </span>
          ))}
          {paper.keywords.length > 6 && (
            <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>+{paper.keywords.length - 6}</span>
          )}
        </div>
      )}

      {/* Collections */}
      {paper.collections && paper.collections.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {paper.collections.map((col) => (
            <span
              key={col.id}
              className="rounded-full font-mono text-xs text-white"
              style={{ padding: '2px 10px', backgroundColor: col.color }}
            >
              {col.name}
            </span>
          ))}
        </div>
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
            className={cn(
              'rounded-lg transition hover:bg-bg-elevated',
              paper.is_favorite ? 'text-accent' : 'text-text-tertiary hover:text-accent',
            )}
            onClick={(e) => { e.stopPropagation(); onToggleFavorite?.(); }}
            title={paper.is_favorite ? 'Remove from favorites' : 'Save for later'}
            style={{ padding: 8 }}
          >
            <Bookmark size={16} fill={paper.is_favorite ? 'currentColor' : 'none'} />
          </button>
          {scholarLibConnected && (
            <button
              onClick={(e) => { e.stopPropagation(); if (!paperSentToScholarLib) onSendToScholarLib?.(); }}
              disabled={paperSentToScholarLib}
              className={cn(
                'rounded-lg transition',
                paperSentToScholarLib
                  ? 'text-success cursor-default'
                  : 'text-text-tertiary hover:bg-bg-elevated hover:text-accent',
              )}
              style={{ padding: 8 }}
              title={paperSentToScholarLib ? 'In ScholarLib' : 'Add to ScholarLib'}
            >
              {paperSentToScholarLib ? <Check size={16} /> : <LibraryBig size={16} />}
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
              paper.user_rating != null ? 'text-warning' : 'text-text-tertiary hover:text-warning',
            )}
            onClick={(e) => { e.stopPropagation(); onClick?.(); }}
            title={paper.user_rating != null ? `Your rating: ${paper.user_rating}/10` : 'Rate'}
            style={{ padding: 8 }}
          >
            <Star size={16} fill={paper.user_rating != null ? 'currentColor' : 'none'} />
          </button>
        </div>
      </div>
    </article>
  );
}
