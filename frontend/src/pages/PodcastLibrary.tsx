import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Play, Headphones, Trash2, Radio, Search, X, ArrowUpDown } from 'lucide-react';
import { usePodcastList, useDeletePodcast } from '@/hooks/usePodcast';
import { usePlayerStore } from '@/stores/playerStore';
import { cn, formatDate } from '@/lib/utils';

export default function PodcastLibrary() {
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [voiceFilter, setVoiceFilter] = useState<string>('');
  const [sort, setSort] = useState('newest');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput.trim()), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const { data: allPodcasts, isLoading } = usePodcastList();

  const podcasts = useMemo(() => {
    if (!allPodcasts) return undefined;
    let filtered = allPodcasts;

    if (typeFilter) {
      filtered = filtered.filter((p) => p.podcast_type === typeFilter);
    }
    if (voiceFilter) {
      filtered = filtered.filter((p) => p.voice_mode === voiceFilter);
    }
    if (debouncedSearch) {
      const term = debouncedSearch.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.paper_title?.toLowerCase().includes(term) ||
          p.paper_journal?.toLowerCase().includes(term),
      );
    }

    const sorted = [...filtered];
    if (sort === 'oldest') {
      sorted.sort((a, b) => (a.generated_at || '').localeCompare(b.generated_at || ''));
    } else if (sort === 'longest') {
      sorted.sort((a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0));
    } else if (sort === 'shortest') {
      sorted.sort((a, b) => (a.duration_seconds || 0) - (b.duration_seconds || 0));
    } else {
      sorted.sort((a, b) => (b.generated_at || '').localeCompare(a.generated_at || ''));
    }
    return sorted;
  }, [allPodcasts, typeFilter, voiceFilter, debouncedSearch, sort]);
  const deletePodcast = useDeletePodcast();
  const setTrack = usePlayerStore((s) => s.setTrack);
  const currentTrackUrl = usePlayerStore((s) => s.currentTrackUrl);
  const [searchParams, setSearchParams] = useSearchParams();

  const apiBase = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

  // Auto-play from ?play=<podcast_id> (used by digest email links)
  useEffect(() => {
    const playId = searchParams.get('play');
    if (playId && podcasts) {
      const target = podcasts.find((p) => p.id === playId);
      if (target) {
        const fullUrl = `${apiBase}${target.audio_url}`;
        setTrack(fullUrl, target.paper_title, target.paper_journal);
        setSearchParams({}, { replace: true });
      }
    }
  }, [searchParams, podcasts]);

  if (isLoading) {
    return (
      <div style={{ padding: '32px 24px' }}>
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }} className="font-mono text-text-primary">
            Podcast Library
          </h1>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
                <div className="h-5 w-3/4 rounded bg-bg-elevated" />
                <div className="mt-3 h-4 w-1/2 rounded bg-bg-elevated" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '32px 24px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }} className="font-mono text-text-primary">
          Podcast Library
        </h1>

        {/* Search bar */}
        <div
          className="rounded-2xl border border-border-default bg-bg-surface transition focus-within:border-accent"
          style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', marginBottom: 16 }}
        >
          <Search size={16} className="text-text-tertiary" style={{ flexShrink: 0 }} />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search podcast titles, journals..."
            className="font-mono text-sm text-text-primary placeholder-text-tertiary outline-none bg-transparent"
            style={{ flex: 1 }}
          />
          {searchInput && (
            <button onClick={() => setSearchInput('')} className="text-text-tertiary hover:text-text-primary transition" style={{ flexShrink: 0 }}>
              <X size={16} />
            </button>
          )}
        </div>

        {/* Filters + sort */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 16, marginBottom: 20 }}>
          {/* Type filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {([['', 'All'], ['paper', 'Paper'], ['digest', 'Digest']] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setTypeFilter(value)}
                className={`rounded-lg font-mono text-xs transition ${
                  typeFilter === value ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary'
                }`}
                style={{ padding: '6px 12px' }}
              >
                {label}
              </button>
            ))}
          </div>

          <span className="text-text-tertiary" style={{ fontSize: 10 }}>|</span>

          {/* Voice filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {([['', 'All'], ['single', 'Single'], ['dual', 'Dual']] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setVoiceFilter(value)}
                className={`rounded-lg font-mono text-xs transition ${
                  voiceFilter === value ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary'
                }`}
                style={{ padding: '6px 12px' }}
              >
                {label}
              </button>
            ))}
          </div>

          <span className="text-text-tertiary" style={{ fontSize: 10 }}>|</span>

          {/* Sort */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <ArrowUpDown size={13} className="text-text-tertiary" />
            {([['newest', 'Newest'], ['oldest', 'Oldest'], ['longest', 'Longest'], ['shortest', 'Shortest']] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setSort(value)}
                className={`rounded-lg font-mono text-xs transition ${
                  sort === value ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary'
                }`}
                style={{ padding: '6px 12px' }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {!podcasts?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
            <Headphones className="text-text-tertiary" size={40} />
            <p style={{ marginTop: 16, fontSize: 18 }} className="font-mono text-text-secondary">No podcasts yet</p>
            <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
              Generate podcasts from paper detail views
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
            {podcasts.map((podcast) => {
              const fullUrl = `${apiBase}${podcast.audio_url}`;
              const isPlaying = currentTrackUrl === fullUrl;
              const isDigest = podcast.podcast_type === 'digest';

              return (
                <article
                  key={podcast.id}
                  className={cn(
                    'group cursor-pointer rounded-2xl border border-border-default bg-bg-surface transition hover:border-border-strong',
                    isPlaying && 'border-accent',
                    isDigest && !isPlaying && 'border-purple-500/30',
                  )}
                  style={{ padding: 20 }}
                  onClick={() => setTrack(fullUrl, podcast.paper_title, podcast.paper_journal)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                    {isDigest ? (
                      <span className="flex items-center gap-1.5 rounded-lg bg-purple-500/15 font-mono text-xs text-purple-400" style={{ padding: '4px 10px' }}>
                        <Radio size={12} /> Digest
                      </span>
                    ) : (
                      <span className="rounded-lg bg-bg-elevated font-mono text-xs text-text-secondary" style={{ padding: '4px 10px' }}>
                        {podcast.voice_mode === 'dual' ? 'Dual voice' : 'Single voice'}
                      </span>
                    )}
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm('Delete this podcast?')) {
                            deletePodcast.mutate(podcast.id);
                          }
                        }}
                        className="flex items-center justify-center rounded-full bg-bg-elevated text-text-tertiary opacity-0 transition hover:bg-danger/15 hover:text-danger group-hover:opacity-100"
                        style={{ width: 36, height: 36 }}
                        title="Delete podcast"
                      >
                        <Trash2 size={14} />
                      </button>
                      <button
                        className="flex items-center justify-center rounded-full bg-accent text-white opacity-0 transition group-hover:opacity-100"
                        style={{ width: 36, height: 36 }}
                      >
                        <Play size={14} style={{ marginLeft: 2 }} />
                      </button>
                    </div>
                  </div>

                  <h3 className="font-sans font-semibold text-text-primary line-clamp-2" style={{ fontSize: 15, lineHeight: 1.4 }}>
                    {podcast.paper_title}
                  </h3>

                  {podcast.collections && podcast.collections.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                      {podcast.collections.map((col) => (
                        <span
                          key={col.id}
                          className="rounded-full font-mono text-xs text-white"
                          style={{ padding: '2px 8px', backgroundColor: col.color, fontSize: 11 }}
                        >
                          {col.name}
                        </span>
                      ))}
                    </div>
                  )}

                  <p className="font-mono text-xs text-text-secondary" style={{ marginTop: 8 }}>
                    {podcast.paper_journal}
                    {podcast.duration_seconds && ` · ${Math.floor(podcast.duration_seconds / 60)}m ${podcast.duration_seconds % 60}s`}
                    {podcast.generated_at && ` · ${formatDate(podcast.generated_at)}`}
                    {podcast.created_by_name && ` · by ${podcast.created_by_name}`}
                  </p>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
