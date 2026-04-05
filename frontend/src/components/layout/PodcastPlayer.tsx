import { useEffect, useRef } from 'react';
import { Howl } from 'howler';
import { Play, Pause, SkipBack, SkipForward, X, Volume2, VolumeX } from 'lucide-react';
import { usePlayerStore } from '@/stores/playerStore';
import { useUIStore } from '@/stores/uiStore';
import api from '@/lib/api';

const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];

export default function PodcastPlayer() {
  const {
    currentTrackUrl,
    currentPaperTitle,
    currentJournal,
    isPlaying,
    progress,
    duration,
    speed,
    volume,
    setPlaying,
    setProgress,
    setDuration,
    setSpeed,
    setVolume,
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
      volume: volume,
      rate: speed,
      onload: () => setDuration(howl.duration()),
      onend: () => setPlaying(false),
    });
    howlRef.current = howl;
    howl.play();

    // Track listen event — extract podcast ID from URL
    const podcastIdMatch = currentTrackUrl.match(/\/audio\/([^/?]+)/);
    if (podcastIdMatch) {
      api.post(`/api/v1/podcasts/${podcastIdMatch[1]}/listen`).catch(() => {});
    }

    return () => {
      cancelAnimationFrame(rafRef.current);
      howl.unload();
    };
  }, [currentTrackUrl]);

  // Sync speed changes
  useEffect(() => {
    if (howlRef.current) howlRef.current.rate(speed);
  }, [speed]);

  // Sync volume changes
  useEffect(() => {
    if (howlRef.current) howlRef.current.volume(volume);
  }, [volume]);

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

  const cycleSpeed = () => {
    const idx = SPEEDS.indexOf(speed);
    const next = SPEEDS[(idx + 1) % SPEEDS.length];
    setSpeed(next);
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
      <div style={{ maxWidth: 1100, margin: '0 auto', height: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '0 16px' }}>
        {/* Track info */}
        <div style={{ minWidth: 0, flex: '0 1 200px' }}>
          <p className="truncate font-sans text-text-primary" style={{ fontSize: 13 }}>{currentPaperTitle}</p>
          <p className="truncate font-mono text-text-secondary" style={{ fontSize: 11 }}>{currentJournal}</p>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            onClick={() => skip(-30)}
            className="rounded-full text-text-secondary hover:text-text-primary"
            style={{ padding: 5 }}
            title="Back 30s"
          >
            <SkipBack size={15} />
          </button>
          <button
            onClick={() => setPlaying(!isPlaying)}
            className="flex items-center justify-center rounded-full bg-accent text-white hover:bg-accent-hover"
            style={{ width: 36, height: 36 }}
          >
            {isPlaying ? <Pause size={15} /> : <Play size={15} style={{ marginLeft: 2 }} />}
          </button>
          <button
            onClick={() => skip(30)}
            className="rounded-full text-text-secondary hover:text-text-primary"
            style={{ padding: 5 }}
            title="Forward 30s"
          >
            <SkipForward size={15} />
          </button>
        </div>

        {/* Progress bar — desktop only */}
        <div className="hidden md:flex" style={{ flex: 1, alignItems: 'center', gap: 8 }}>
          <span className="font-mono text-text-tertiary" style={{ fontSize: 10, flexShrink: 0 }}>{formatTime(progress)}</span>
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
          <span className="font-mono text-text-tertiary" style={{ fontSize: 10, flexShrink: 0 }}>{formatTime(duration)}</span>
        </div>

        {/* Speed control */}
        <button
          onClick={cycleSpeed}
          className="rounded-lg font-mono text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary"
          style={{ padding: '4px 8px', fontSize: 11, flexShrink: 0 }}
          title="Playback speed"
        >
          {speed}x
        </button>

        {/* Volume */}
        <div className="hidden md:flex" style={{ alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <button
            onClick={() => setVolume(volume > 0 ? 0 : 1)}
            className="text-text-secondary hover:text-text-primary"
            style={{ padding: 2 }}
            title={volume > 0 ? 'Mute' : 'Unmute'}
          >
            {volume > 0 ? <Volume2 size={15} /> : <VolumeX size={15} />}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="cursor-pointer appearance-none rounded-full bg-border-default [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent"
            style={{ width: 70, height: 3 }}
          />
        </div>

        {/* Close */}
        <button
          onClick={clearTrack}
          className="rounded-lg text-text-tertiary hover:text-text-primary"
          style={{ padding: 5, flexShrink: 0 }}
        >
          <X size={15} />
        </button>
      </div>
    </div>
  );
}
