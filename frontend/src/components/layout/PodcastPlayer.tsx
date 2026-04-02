import { useEffect, useRef } from 'react';
import { Howl } from 'howler';
import { Play, Pause, SkipBack, SkipForward, X } from 'lucide-react';
import { usePlayerStore } from '@/stores/playerStore';
import { cn } from '@/lib/utils';

export default function PodcastPlayer() {
  const {
    currentTrackUrl,
    currentPaperTitle,
    currentJournal,
    isPlaying,
    progress,
    duration,
    setPlaying,
    setProgress,
    setDuration,
    clearTrack,
  } = usePlayerStore();

  const howlRef = useRef<Howl | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!currentTrackUrl) return;

    howlRef.current?.unload();
    const howl = new Howl({
      src: [currentTrackUrl],
      html5: true,
      onload: () => setDuration(howl.duration()),
      onend: () => setPlaying(false),
    });
    howlRef.current = howl;
    howl.play();

    return () => {
      cancelAnimationFrame(rafRef.current);
      howl.unload();
    };
  }, [currentTrackUrl, setDuration, setPlaying]);

  useEffect(() => {
    const update = () => {
      if (howlRef.current && isPlaying) {
        setProgress(howlRef.current.seek() as number);
        rafRef.current = requestAnimationFrame(update);
      }
    };
    if (isPlaying) {
      howlRef.current?.play();
      rafRef.current = requestAnimationFrame(update);
    } else {
      howlRef.current?.pause();
      cancelAnimationFrame(rafRef.current);
    }
    return () => cancelAnimationFrame(rafRef.current);
  }, [isPlaying, setProgress]);

  if (!currentTrackUrl) return null;

  const progressPct = duration > 0 ? (progress / duration) * 100 : 0;

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const time = pct * duration;
    howlRef.current?.seek(time);
    setProgress(time);
  };

  const skip = (seconds: number) => {
    if (!howlRef.current) return;
    const current = howlRef.current.seek() as number;
    const newTime = Math.max(0, Math.min(duration, current + seconds));
    howlRef.current.seek(newTime);
    setProgress(newTime);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 border-t border-border-default bg-bg-surface',
        'md:bottom-0 md:left-60',
        'h-[72px] md:h-[72px]',
      )}
      style={{ bottom: window.innerWidth < 768 ? '64px' : '0' }}
    >
      <div className="mx-auto flex h-full max-w-4xl items-center gap-4 px-4">
        {/* Track info */}
        <div className="min-w-0 flex-1">
          <p className="truncate font-serif text-sm text-text-primary">{currentPaperTitle}</p>
          <p className="truncate font-mono text-xs text-text-secondary">{currentJournal}</p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-2">
          <button onClick={() => skip(-30)} className="rounded-full p-1.5 text-text-secondary hover:text-text-primary">
            <SkipBack size={16} />
          </button>
          <button
            onClick={() => setPlaying(!isPlaying)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white hover:bg-accent-hover"
          >
            {isPlaying ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
          </button>
          <button onClick={() => skip(30)} className="rounded-full p-1.5 text-text-secondary hover:text-text-primary">
            <SkipForward size={16} />
          </button>
        </div>

        {/* Progress bar */}
        <div className="hidden flex-1 items-center gap-2 md:flex">
          <span className="font-mono text-xs text-text-tertiary">{formatTime(progress)}</span>
          <div className="relative h-1 flex-1 cursor-pointer rounded-full bg-border-default" onClick={seek}>
            <div
              className="absolute left-0 top-0 h-full rounded-full bg-accent transition-[width]"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <span className="font-mono text-xs text-text-tertiary">{formatTime(duration)}</span>
        </div>

        {/* Close */}
        <button onClick={clearTrack} className="rounded-full p-1.5 text-text-tertiary hover:text-text-primary">
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
