import { ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FeedFilters } from '@/types/feed';

interface FilterBarProps {
  filters: FeedFilters;
  onChange: (filters: Partial<FeedFilters>) => void;
  facets?: { papers: number; news: number };
}

export default function FilterBar({ filters, onChange, facets }: FilterBarProps) {
  const typeOptions: Array<{ value: FeedFilters['type']; label: string; count?: number }> = [
    { value: 'all', label: 'All', count: facets ? facets.papers + facets.news : undefined },
    { value: 'papers', label: 'Papers', count: facets?.papers },
    { value: 'news', label: 'News', count: facets?.news },
  ];

  const sortOptions: Array<{ value: FeedFilters['sort']; label: string }> = [
    { value: 'relevance', label: 'Top' },
    { value: 'date_desc', label: 'New' },
    { value: 'date_asc', label: 'Old' },
  ];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16, overflowX: 'auto', WebkitOverflowScrolling: 'touch', paddingBottom: 4 }} className="scrollbar-none">
      {/* Type chips */}
      {typeOptions.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange({ type: opt.value })}
          className={cn(
            'whitespace-nowrap rounded-lg font-mono text-xs transition',
            filters.type === opt.value
              ? 'bg-accent text-white'
              : 'bg-bg-elevated text-text-secondary hover:text-text-primary',
          )}
          style={{ padding: '6px 12px', flexShrink: 0 }}
        >
          {opt.label}
          {opt.count !== undefined && (
            <span className={cn('ml-1', filters.type === opt.value ? 'text-white/70' : 'text-text-tertiary')}>
              {opt.count}
            </span>
          )}
        </button>
      ))}

      {/* Divider */}
      <div className="bg-border-default" style={{ width: 1, height: 20, flexShrink: 0, margin: '0 4px' }} />

      {/* Sort options */}
      <ArrowUpDown size={13} className="text-text-tertiary" style={{ flexShrink: 0 }} />
      {sortOptions.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange({ sort: opt.value })}
          className={cn(
            'whitespace-nowrap rounded-lg font-mono text-xs transition',
            filters.sort === opt.value
              ? 'bg-bg-elevated text-text-primary'
              : 'text-text-tertiary hover:text-text-secondary',
          )}
          style={{ padding: '6px 10px', flexShrink: 0 }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
