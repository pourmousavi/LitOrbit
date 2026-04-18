import { create } from 'zustand';

export interface PulseSettingsState {
  showPulseCard: boolean;
  showNavBadge: boolean;
  showSidebarStat: boolean;
  showWeeklyToast: boolean;
  saveAll: (settings: Pick<PulseSettingsState, 'showPulseCard' | 'showNavBadge' | 'showSidebarStat' | 'showWeeklyToast'>) => void;
}

const STORAGE_KEY = 'litorbit-pulse-settings';

function loadSettings() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
}

const defaults = loadSettings();

export const usePulseSettings = create<PulseSettingsState>((set) => ({
  showPulseCard: defaults.showPulseCard ?? true,
  showNavBadge: defaults.showNavBadge ?? true,
  showSidebarStat: defaults.showSidebarStat ?? true,
  showWeeklyToast: defaults.showWeeklyToast ?? true,
  saveAll: (settings) => {
    set(settings);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  },
}));
