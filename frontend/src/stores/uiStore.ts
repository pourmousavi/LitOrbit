import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarExpanded: boolean;
  selectedPaperId: string | null;
  toggleSidebar: () => void;
  setSidebarExpanded: (expanded: boolean) => void;
  selectPaper: (id: string | null) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarExpanded: true,
      selectedPaperId: null,

      toggleSidebar: () => set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),
      setSidebarExpanded: (expanded) => set({ sidebarExpanded: expanded }),
      selectPaper: (id) => set({ selectedPaperId: id }),
    }),
    {
      name: 'litorbit-ui',
      partialize: (state) => ({ sidebarExpanded: state.sidebarExpanded }),
    },
  ),
);
