import { create } from 'zustand';

export interface PulseSettingsState {
  showPulseCard: boolean;
  showNavBadge: boolean;
  showSidebarStat: boolean;
  showWeeklyToast: boolean;
  /** Hydrate from backend profile data */
  hydrate: (profile: {
    show_pulse_card: boolean;
    show_nav_badge: boolean;
    show_sidebar_stat: boolean;
    show_weekly_toast: boolean;
  }) => void;
  /** Update local state immediately (backend save handled by caller) */
  saveAll: (settings: Pick<PulseSettingsState, 'showPulseCard' | 'showNavBadge' | 'showSidebarStat' | 'showWeeklyToast'>) => void;
}

export const usePulseSettings = create<PulseSettingsState>((set) => ({
  showPulseCard: true,
  showNavBadge: true,
  showSidebarStat: true,
  showWeeklyToast: true,
  hydrate: (profile) => {
    set({
      showPulseCard: profile.show_pulse_card,
      showNavBadge: profile.show_nav_badge,
      showSidebarStat: profile.show_sidebar_stat,
      showWeeklyToast: profile.show_weekly_toast,
    });
  },
  saveAll: (settings) => {
    set(settings);
  },
}));
