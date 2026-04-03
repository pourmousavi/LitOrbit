import { useState, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';
import PaperFeed from '@/components/papers/PaperFeed';
import PaperDetail from '@/components/papers/PaperDetail';

export default function Feed() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounce search input by 400ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput.trim()), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Feed column — independently scrollable */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px 24px' }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 20 }} className="font-mono text-text-primary">
            Paper Feed
          </h1>

          {/* Search bar */}
          <div
            className="rounded-2xl border border-border-default bg-bg-surface transition focus-within:border-accent"
            style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', marginBottom: 24 }}
          >
            <Search size={16} className="text-text-tertiary" style={{ flexShrink: 0 }} />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search titles, authors, journals, keywords, DOI..."
              className="font-mono text-sm text-text-primary placeholder-text-tertiary outline-none bg-transparent"
              style={{ flex: 1 }}
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput('')}
                className="text-text-tertiary hover:text-text-primary transition"
                style={{ flexShrink: 0 }}
              >
                <X size={16} />
              </button>
            )}
          </div>

          <PaperFeed search={debouncedSearch || undefined} />
        </div>
      </div>

      {/* Detail panel — independently scrollable */}
      {selectedPaperId && (
        <div
          className="hidden border-l border-border-default bg-bg-surface md:block"
          style={{ width: 420, flexShrink: 0, overflowY: 'auto', height: '100vh' }}
        >
          <PaperDetail />
        </div>
      )}
    </div>
  );
}
