import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LayoutGrid } from 'lucide-react';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import PaperFeed from '@/components/papers/PaperFeed';
import type { PapersResponse } from '@/types';

export default function Categories() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Fetch all papers to extract unique categories
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
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Categories</h1>

      {/* Category chips */}
      <div className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedCategory(null)}
          className={cn(
            'rounded-full px-3 py-1.5 font-mono text-xs transition',
            !selectedCategory ? 'bg-accent text-white' : 'bg-bg-surface text-text-secondary hover:text-text-primary border border-border-default',
          )}
        >
          All
        </button>
        {sortedCategories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={cn(
              'rounded-full px-3 py-1.5 font-mono text-xs transition',
              selectedCategory === cat ? 'bg-accent text-white' : 'bg-bg-surface text-text-secondary hover:text-text-primary border border-border-default',
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {sortedCategories.length === 0 && !data ? (
        <div className="flex flex-col items-center justify-center py-20">
          <LayoutGrid className="mb-3 text-text-tertiary" size={32} />
          <p className="font-mono text-lg text-text-secondary">No categories yet</p>
          <p className="mt-1 font-mono text-sm text-text-tertiary">
            Categories are assigned when papers are summarised
          </p>
        </div>
      ) : (
        <PaperFeed category={selectedCategory ?? undefined} />
      )}
    </div>
  );
}
