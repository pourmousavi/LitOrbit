import { useEffect, useRef } from 'react';
import { Howl } from 'howler';
import { Play, Pause, SkipBack, SkipForward, X } from 'lucide-react';
import { usePlayerStore } from '@/stores/playerStore';
import { useUIStore } from '@/stores/uiStore';

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
  const sidebarExpanded = useUIStore((s) => s.sidebarExpanded);

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
  const sidebarWidth = sidebarExpanded ? 240 : 64;

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
      className="border-t border-border-default bg-bg-surface"
      style={{
        position: 'fixed',
        bottom: window.innerWidth < 768 ? 64 : 0,
        left: window.innerWidth >= 768 ? sidebarWidth : 0,
        right: 0,
        height: 72,
        zIndex: 50,
        transition: 'left 0.2s',
      }}
    >
      <div style={{ maxWidth: 960, margin: '0 auto', height: '100%', display: 'flex', alignItems: 'center', gap: 16, padding: '0 20px' }}>
        {/* Track info */}
        <div style={{ minWidth: 0, flex: 1 }}>
          <p className="truncate font-serif text-text-primary" style={{ fontSize: 14 }}>{currentPaperTitle}</p>
          <p className="truncate font-mono text-text-secondary" style={{ fontSize: 12 }}>{currentJournal}</p>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={() => skip(-30)}
            className="rounded-full text-text-secondary hover:text-text-primary"
            style={{ padding: 6 }}
          >
            <SkipBack size={16} />
          </button>
          <button
            onClick={() => setPlaying(!isPlaying)}
            className="flex items-center justify-center rounded-full bg-accent text-white hover:bg-accent-hover"
            style={{ width: 40, height: 40 }}
          >
            {isPlaying ? <Pause size={16} /> : <Play size={16} style={{ marginLeft: 2 }} />}
          </button>
          <button
            onClick={() => skip(30)}
            className="rounded-full text-text-secondary hover:text-text-primary"
            style={{ padding: 6 }}
          >
            <SkipForward size={16} />
          </button>
        </div>

        {/* Progress bar — desktop only */}
        <div className="hidden md:flex" style={{ flex: 1, alignItems: 'center', gap: 10 }}>
          <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>{formatTime(progress)}</span>
          <div
            className="rounded-full bg-border-default cursor-pointer"
            style={{ position: 'relative', height: 4, flex: 1 }}
            onClick={seek}
          >
            <div
              className="rounded-full bg-accent"
              style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${progressPct}%`, transition: 'width 0.1s' }}
            />
          </div>
          <span className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>{formatTime(duration)}</span>
        </div>

        {/* Close */}
        <button
          onClick={clearTrack}
          className="rounded-lg text-text-tertiary hover:text-text-primary"
          style={{ padding: 6 }}
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
