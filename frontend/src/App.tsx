import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';
import Sidebar from '@/components/layout/Sidebar';
import BottomNav from '@/components/layout/BottomNav';
import PodcastPlayer from '@/components/layout/PodcastPlayer';
import Login from '@/pages/Login';
import Feed from '@/pages/Feed';
import SharedWithMe from '@/pages/SharedWithMe';
import MyRatings from '@/pages/MyRatings';
import PodcastLibrary from '@/pages/PodcastLibrary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      retry: 1,
    },
  },
});

function ProtectedRoute() {
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);

  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-bg-base">
        <div className="font-mono text-sm text-text-secondary">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <AppLayout />;
}

function AppLayout() {
  const sidebarExpanded = useUIStore((s) => s.sidebarExpanded);

  return (
    <div className="flex min-h-svh bg-bg-base">
      {/* Sidebar: hidden on mobile */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Main content */}
      <main
        className={cn(
          'flex-1 transition-all duration-200',
          'pb-16 md:pb-0',
          sidebarExpanded ? 'md:ml-60' : 'md:ml-16',
        )}
      >
        <Outlet />
      </main>

      {/* Mobile bottom nav */}
      <BottomNav />

      {/* Podcast player — persists across routes */}
      <PodcastPlayer />
    </div>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex h-full min-h-[60vh] items-center justify-center">
      <p className="font-mono text-text-secondary">{title} — coming soon</p>
    </div>
  );
}

export default function App() {
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Feed />} />
            <Route path="/categories" element={<Placeholder title="Categories" />} />
            <Route path="/shared" element={<SharedWithMe />} />
            <Route path="/podcasts" element={<PodcastLibrary />} />
            <Route path="/ratings" element={<MyRatings />} />
            <Route path="/profile" element={<Placeholder title="Profile" />} />
            <Route path="/admin" element={<Placeholder title="Admin Panel" />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
