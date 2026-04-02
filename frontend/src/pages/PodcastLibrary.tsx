import { Play, Headphones } from 'lucide-react';
import { usePodcastList } from '@/hooks/usePodcast';
import { usePlayerStore } from '@/stores/playerStore';
import { cn, formatDate } from '@/lib/utils';

export default function PodcastLibrary() {
  const { data: podcasts, isLoading } = usePodcastList();
  const setTrack = usePlayerStore((s) => s.setTrack);
  const currentTrackUrl = usePlayerStore((s) => s.currentTrackUrl);

  const apiBase = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

  if (isLoading) {
    return (
      <div className="p-4">
        <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Podcast Library</h1>
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-border-default bg-bg-surface p-4">
              <div className="h-4 w-3/4 rounded bg-bg-elevated" />
              <div className="mt-2 h-3 w-1/2 rounded bg-bg-elevated" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Podcast Library</h1>

      {!podcasts?.length ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Headphones className="mb-3 text-text-tertiary" size={32} />
          <p className="font-mono text-lg text-text-secondary">No podcasts yet</p>
          <p className="mt-1 font-mono text-sm text-text-tertiary">
            Generate podcasts from paper detail views
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {podcasts.map((podcast) => {
            const fullUrl = `${apiBase}${podcast.audio_url}`;
            const isPlaying = currentTrackUrl === fullUrl;

            return (
              <article
                key={podcast.id}
                className={cn(
                  'group cursor-pointer rounded-xl border border-border-default bg-bg-surface p-4 transition hover:border-border-strong',
                  isPlaying && 'border-accent',
                )}
                onClick={() => setTrack(fullUrl, podcast.paper_title, podcast.paper_journal)}
              >
                <div className="mb-2 flex items-start justify-between">
                  <span className="rounded-md bg-bg-elevated px-2 py-0.5 font-mono text-xs text-text-secondary">
                    {podcast.voice_mode === 'dual' ? 'Dual voice' : 'Single voice'}
                  </span>
                  <button className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-white opacity-0 transition group-hover:opacity-100">
                    <Play size={14} className="ml-0.5" />
                  </button>
                </div>

                <h3 className="mb-1 font-serif text-sm font-semibold text-text-primary line-clamp-2">
                  {podcast.paper_title}
                </h3>

                <p className="font-mono text-xs text-text-secondary">
                  {podcast.paper_journal}
                  {podcast.duration_seconds && ` · ${Math.floor(podcast.duration_seconds / 60)}m ${podcast.duration_seconds % 60}s`}
                  {podcast.generated_at && ` · ${formatDate(podcast.generated_at)}`}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
