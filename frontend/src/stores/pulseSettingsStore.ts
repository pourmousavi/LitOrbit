import { create } from 'zustand';

interface PulseSettings {
  showPulseCard: boolean;
  showNavBadge: boolean;
  showSidebarStat: boolean;
  showWeeklyToast: boolean;
  setShowPulseCard: (v: boolean) => void;
  setShowNavBadge: (v: boolean) => void;
  setShowSidebarStat: (v: boolean) => void;
  setShowWeeklyToast: (v: boolean) => void;
}

const STORAGE_KEY = 'litorbit-pulse-settings';

function loadSettings(): Partial<PulseSettings> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
}

function saveSettings(state: PulseSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    showPulseCard: state.showPulseCard,
    showNavBadge: state.showNavBadge,
    showSidebarStat: state.showSidebarStat,
    showWeeklyToast: state.showWeeklyToast,
  }));
}

const defaults = loadSettings();

export const usePulseSettings = create<PulseSettings>((set, get) => ({
  showPulseCard: defaults.showPulseCard ?? true,
  showNavBadge: defaults.showNavBadge ?? true,
  showSidebarStat: defaults.showSidebarStat ?? true,
  showWeeklyToast: defaults.showWeeklyToast ?? true,
  setShowPulseCard: (v) => { set({ showPulseCard: v }); saveSettings({ ...get(), showPulseCard: v }); },
  setShowNavBadge: (v) => { set({ showNavBadge: v }); saveSettings({ ...get(), showNavBadge: v }); },
  setShowSidebarStat: (v) => { set({ showSidebarStat: v }); saveSettings({ ...get(), showSidebarStat: v }); },
  setShowWeeklyToast: (v) => { set({ showWeeklyToast: v }); saveSettings({ ...get(), showWeeklyToast: v }); },
}));
