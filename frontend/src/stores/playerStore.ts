import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface PlayerState {
  currentTrackUrl: string | null;
  currentPaperTitle: string | null;
  currentJournal: string | null;
  isPlaying: boolean;
  progress: number;
  duration: number;
  speed: number;
  volume: number;
  setTrack: (url: string, title: string, journal: string) => void;
  setPlaying: (playing: boolean) => void;
  setProgress: (progress: number) => void;
  setDuration: (duration: number) => void;
  setSpeed: (speed: number) => void;
  setVolume: (volume: number) => void;
  clearTrack: () => void;
}

export const usePlayerStore = create<PlayerState>()(
  persist(
    (set) => ({
      currentTrackUrl: null,
      currentPaperTitle: null,
      currentJournal: null,
      isPlaying: false,
      progress: 0,
      duration: 0,
      speed: 1,
      volume: 1,

      setTrack: (url, title, journal) =>
        set({ currentTrackUrl: url, currentPaperTitle: title, currentJournal: journal, progress: 0, isPlaying: true }),

      setPlaying: (playing) => set({ isPlaying: playing }),
      setProgress: (progress) => set({ progress }),
      setDuration: (duration) => set({ duration }),
      setSpeed: (speed) => set({ speed }),
      setVolume: (volume) => set({ volume }),
      clearTrack: () =>
        set({ currentTrackUrl: null, currentPaperTitle: null, currentJournal: null, isPlaying: false, progress: 0, duration: 0 }),
    }),
    {
      name: 'litorbit-player',
      partialize: (state) => ({ speed: state.speed, volume: state.volume }),
    },
  ),
);
