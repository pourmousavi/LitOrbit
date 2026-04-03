import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LayoutGrid } from 'lucide-react';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import PaperFeed from '@/components/papers/PaperFeed';
import type { PapersResponse } from '@/types';

export default function Categories() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const { data } = useQuery<PapersResponse>({
    queryKey: ['papers', 'categories-extract'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/papers', { params: { per_page: 100 } });
      return data;
    },
  });

  const categories = new Set<string>();
  data?.papers.forEach((p) => p.categories.forEach((c) => categories.add(c)));
  const sortedCategories = Array.from(categories).sort();

  return (
    <div style={{ padding: '32px 24px' }}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }} className="font-mono text-text-primary">
          Categories
        </h1>

        {/* Category chips */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 28 }}>
          <button
            onClick={() => setSelectedCategory(null)}
            className={cn(
              'rounded-full font-mono text-sm transition',
              !selectedCategory
                ? 'bg-accent text-white'
                : 'bg-bg-surface text-text-secondary hover:text-text-primary border border-border-default',
            )}
            style={{ padding: '8px 16px' }}
          >
            All
          </button>
          {sortedCategories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={cn(
                'rounded-full font-mono text-sm transition',
                selectedCategory === cat
                  ? 'bg-accent text-white'
                  : 'bg-bg-surface text-text-secondary hover:text-text-primary border border-border-default',
              )}
              style={{ padding: '8px 16px' }}
            >
              {cat}
            </button>
          ))}
        </div>

        {sortedCategories.length === 0 && !data ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
            <LayoutGrid className="text-text-tertiary" size={40} />
            <p style={{ marginTop: 16, fontSize: 18 }} className="font-mono text-text-secondary">No categories yet</p>
            <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
              Categories are assigned when papers are summarised
            </p>
          </div>
        ) : (
          <PaperFeed category={selectedCategory ?? undefined} />
        )}
      </div>
    </div>
  );
}
