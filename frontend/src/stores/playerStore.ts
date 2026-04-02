import { create } from 'zustand';

interface PlayerState {
  currentTrackUrl: string | null;
  currentPaperTitle: string | null;
  currentJournal: string | null;
  isPlaying: boolean;
  progress: number;
  duration: number;
  setTrack: (url: string, title: string, journal: string) => void;
  setPlaying: (playing: boolean) => void;
  setProgress: (progress: number) => void;
  setDuration: (duration: number) => void;
  clearTrack: () => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
  currentTrackUrl: null,
  currentPaperTitle: null,
  currentJournal: null,
  isPlaying: false,
  progress: 0,
  duration: 0,

  setTrack: (url, title, journal) =>
    set({ currentTrackUrl: url, currentPaperTitle: title, currentJournal: journal, progress: 0, isPlaying: true }),

  setPlaying: (playing) => set({ isPlaying: playing }),
  setProgress: (progress) => set({ progress }),
  setDuration: (duration) => set({ duration }),
  clearTrack: () =>
    set({ currentTrackUrl: null, currentPaperTitle: null, currentJournal: null, isPlaying: false, progress: 0, duration: 0 }),
}));
