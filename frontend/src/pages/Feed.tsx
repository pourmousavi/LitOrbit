import { useState, useEffect } from 'react';
import { Search, X, Plus, Link, Loader2, ArrowUpDown, Bookmark } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '@/stores/uiStore';
import { usePapers } from '@/hooks/usePapers';
import { useFeed } from '@/hooks/useFeed';
import { useEngagement } from '@/hooks/useEngagement';
import PaperFeed from '@/components/papers/PaperFeed';
import PaperDetail from '@/components/papers/PaperDetail';
import NewsDetail from '@/components/feed/NewsDetail';
import UnifiedFeedList from '@/components/feed/UnifiedFeedList';
import ResearchPulse from '@/components/engagement/ResearchPulse';
import { usePulseSettings } from '@/stores/pulseSettingsStore';
import { toast } from '@/components/ui/Toast';
import { cn } from '@/lib/utils';
import api from '@/lib/api';
import type { FeedFilters } from '@/types/feed';

type FeedType = 'all' | 'papers' | 'news';

export default function Feed() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const selectedNewsId = useUIStore((s) => s.selectedNewsId);
  const [feedType, setFeedType] = useState<FeedType>('papers');
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [showDoiInput, setShowDoiInput] = useState(false);
  const [doi, setDoi] = useState('');
  const [sort, setSort] = useState('score');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const queryClient = useQueryClient();

  // Paper count (for "Papers" tab badge)
  const { data: papersData } = usePapers({ search: debouncedSearch || undefined, sort, favorites: favoritesOnly });
  const totalPapers = papersData?.pages?.[0]?.total ?? null;

  // Unified feed filters
  const unifiedSort = sort === 'score' ? 'relevance' : sort === 'newest' ? 'date_desc' : sort === 'oldest' ? 'date_asc' : 'relevance';
  const feedFilters: Partial<FeedFilters> = {
    type: feedType,
    sort: unifiedSort as FeedFilters['sort'],
    search: debouncedSearch || null,
  };
  const feedQuery = useFeed(feedFilters, feedType !== 'papers');
  const facets = feedQuery.data?.pages?.[0]?.facets?.by_type;

  const { data: pulse } = useEngagement();
  const { showWeeklyToast } = usePulseSettings();

  // Weekly summary toast
  useEffect(() => {
    if (!pulse || !showWeeklyToast) return;
    const now = new Date();
    const monday = new Date(now);
    monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
    const weekKey = monday.toISOString().slice(0, 10);
    const shown = localStorage.getItem('litorbit-weekly-summary-shown');
    if (shown !== weekKey && pulse.last_week_rated > 0) {
      toast('info', `Last week: ${pulse.last_week_rated} papers rated, ${pulse.last_week_points} pts`);
      localStorage.setItem('litorbit-weekly-summary-shown', weekKey);
    }
  }, [pulse, showWeeklyToast]);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput.trim()), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const doiMutation = useMutation({
    mutationFn: async (doiValue: string) => {
      const { data } = await api.post('/api/v1/papers/doi-lookup', { doi: doiValue });
      return data as { status: string; paper_id: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
      setDoi('');
      setShowDoiInput(false);
      setShowAddMenu(false);
    },
  });

  const feedTitle = feedType === 'papers' ? 'Paper Feed' : feedType === 'news' ? 'News Feed' : 'Feed';

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Feed column */}
      <div className="flex-1 overflow-y-auto px-4 pt-8 pb-4 md:px-8 md:pt-10 md:pb-8">
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <div className="mb-6" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <h1 style={{ fontWeight: 600, display: 'flex', alignItems: 'baseline', gap: 8, minWidth: 0 }} className="font-mono text-text-primary text-xl">
              {feedTitle}
              {feedType === 'papers' && totalPapers !== null && (
                <span className="font-mono text-text-tertiary" style={{ fontSize: 12, fontWeight: 400 }}>
                  {totalPapers.toLocaleString()}
                </span>
              )}
            </h1>

            {/* Add Paper button — only show in papers mode */}
            {feedType !== 'news' && (
              <div style={{ position: 'relative', flexShrink: 0 }}>
                <button
                  onClick={() => { setShowAddMenu(!showAddMenu); setShowDoiInput(false); }}
                  className="flex items-center rounded-xl bg-accent font-mono text-xs font-medium text-white transition hover:bg-accent-hover md:text-sm"
                  style={{ gap: 6, padding: '8px 12px' }}
                >
                  <Plus size={15} /> <span className="hidden md:inline">Add Paper</span><span className="md:hidden">Add</span>
                </button>

                {showAddMenu && (
                  <div
                    className="rounded-xl border border-border-default bg-bg-surface shadow-lg"
                    style={{ position: 'absolute', right: 0, top: '100%', marginTop: 8, width: 'min(280px, calc(100vw - 40px))', zIndex: 50 }}
                  >
                    {!showDoiInput ? (
                      <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <button
                          onClick={() => setShowDoiInput(true)}
                          className="flex items-center rounded-lg font-mono text-sm text-text-primary transition hover:bg-bg-elevated"
                          style={{ gap: 10, padding: '10px 12px', width: '100%', textAlign: 'left' }}
                        >
                          <Link size={16} />
                          <div>
                            <div>Lookup by DOI</div>
                            <div className="text-text-tertiary" style={{ fontSize: 11 }}>Fetch open access PDF automatically</div>
                          </div>
                        </button>
                      </div>
                    ) : (
                      <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <input
                          value={doi}
                          onChange={(e) => setDoi(e.target.value)}
                          placeholder="e.g. 10.1016/j.apenergy.2024.123456"
                          className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
                          style={{ padding: '8px 12px', width: '100%' }}
                          autoFocus
                          onKeyDown={(e) => { if (e.key === 'Enter' && doi.trim()) doiMutation.mutate(doi.trim()); }}
                        />
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            onClick={() => doiMutation.mutate(doi.trim())}
                            disabled={!doi.trim() || doiMutation.isPending}
                            className="flex items-center rounded-lg bg-accent font-mono text-xs text-white hover:bg-accent-hover disabled:opacity-50"
                            style={{ gap: 6, padding: '8px 14px' }}
                          >
                            {doiMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Link size={13} />}
                            Fetch
                          </button>
                          <button
                            onClick={() => setShowDoiInput(false)}
                            className="rounded-lg font-mono text-xs text-text-secondary hover:text-text-primary"
                            style={{ padding: '8px 14px' }}
                          >
                            Back
                          </button>
                        </div>
                        {doiMutation.isError && (
                          <p className="font-mono text-danger" style={{ fontSize: 11 }}>
                            {(doiMutation.error as any)?.response?.data?.detail || 'Failed to fetch DOI'}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <ResearchPulse />

          {/* Search bar */}
          <div
            className="rounded-2xl border border-border-default bg-bg-surface transition focus-within:border-accent"
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', marginBottom: 16 }}
          >
            <Search size={16} className="text-text-tertiary" style={{ flexShrink: 0 }} />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={feedType === 'news' ? 'Search news titles...' : 'Search titles, authors, journals, keywords, DOI...'}
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

          {/* Type filter + sort options */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 16, overflowX: 'auto', WebkitOverflowScrolling: 'touch', paddingBottom: 4 }} className="scrollbar-none">
            {/* Type chips */}
            {([
              ['all', 'All'],
              ['papers', 'Papers'],
              ['news', 'News'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setFeedType(value)}
                className={cn(
                  'whitespace-nowrap rounded-lg font-mono text-xs transition',
                  feedType === value
                    ? 'bg-accent text-white'
                    : 'bg-bg-elevated text-text-secondary hover:text-text-primary',
                )}
                style={{ padding: '6px 12px', flexShrink: 0 }}
              >
                {label}
                {value === 'papers' && totalPapers !== null && <span className={cn('ml-1', feedType === value ? 'text-white/70' : 'text-text-tertiary')}>{totalPapers}</span>}
                {value === 'news' && facets && <span className={cn('ml-1', feedType === value ? 'text-white/70' : 'text-text-tertiary')}>{facets.news}</span>}
                {value === 'all' && totalPapers !== null && <span className={cn('ml-1', feedType === value ? 'text-white/70' : 'text-text-tertiary')}>{totalPapers + (facets?.news ?? 0)}</span>}
              </button>
            ))}

            {/* Divider */}
            <div className="bg-border-default" style={{ width: 1, height: 20, flexShrink: 0, margin: '0 4px' }} />

            {/* Sort options */}
            <ArrowUpDown size={13} className="text-text-tertiary" style={{ flexShrink: 0 }} />
            {(feedType === 'papers' ? [
              ['score', 'Top'],
              ['newest', 'New'],
              ['published', 'Published'],
              ['oldest', 'Old'],
            ] as const : [
              ['score', 'Top'],
              ['newest', 'New'],
              ['oldest', 'Old'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setSort(value)}
                className={cn(
                  'whitespace-nowrap rounded-lg font-mono text-xs transition',
                  sort === value
                    ? 'bg-bg-elevated text-text-primary'
                    : 'text-text-tertiary hover:text-text-secondary',
                )}
                style={{ padding: '6px 10px', flexShrink: 0 }}
              >
                {label}
              </button>
            ))}

            {/* Favorites filter — papers only */}
            {feedType !== 'news' && (
              <button
                onClick={() => setFavoritesOnly((v) => !v)}
                className={cn(
                  'flex items-center whitespace-nowrap rounded-lg font-mono text-xs transition',
                  favoritesOnly
                    ? 'bg-accent text-white'
                    : 'text-text-tertiary hover:text-text-secondary',
                )}
                style={{ padding: '6px 10px', gap: 4, flexShrink: 0 }}
                title="Show only favorites"
              >
                <Bookmark size={12} fill={favoritesOnly ? 'currentColor' : 'none'} />
                Favs
              </button>
            )}
          </div>

          {/* Feed content — papers mode uses existing PaperFeed, others use unified */}
          {feedType === 'papers' ? (
            <PaperFeed search={debouncedSearch || undefined} sort={sort} favorites={favoritesOnly} />
          ) : (
            <UnifiedFeedList filters={feedFilters} />
          )}
        </div>
      </div>

      {/* Detail panel — sidebar on desktop, full-screen overlay on mobile */}
      {selectedPaperId && (
        <>
          <div
            className="fixed inset-0 z-50 overflow-y-auto bg-bg-base md:hidden"
            style={{ paddingBottom: 64 }}
          >
            <PaperDetail />
          </div>
          <div
            className="hidden border-l border-border-default bg-bg-surface md:block"
            style={{ width: 420, flexShrink: 0, overflowY: 'auto', height: '100vh' }}
          >
            <PaperDetail />
          </div>
        </>
      )}
      {selectedNewsId && !selectedPaperId && (
        <>
          <div
            className="fixed inset-0 z-50 overflow-y-auto bg-bg-base md:hidden"
            style={{ paddingBottom: 64 }}
          >
            <NewsDetail />
          </div>
          <div
            className="hidden border-l border-border-default bg-bg-surface md:block"
            style={{ width: 420, flexShrink: 0, overflowY: 'auto', height: '100vh' }}
          >
            <NewsDetail />
          </div>
        </>
      )}
    </div>
  );
}
