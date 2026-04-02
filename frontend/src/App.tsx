import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import ToastContainer from '@/components/ui/Toast';
import Sidebar from '@/components/layout/Sidebar';
import BottomNav from '@/components/layout/BottomNav';
import PodcastPlayer from '@/components/layout/PodcastPlayer';
import Login from '@/pages/Login';
import Feed from '@/pages/Feed';
import Categories from '@/pages/Categories';
import SharedWithMe from '@/pages/SharedWithMe';
import MyRatings from '@/pages/MyRatings';
import PodcastLibrary from '@/pages/PodcastLibrary';
import Profile from '@/pages/Profile';
import Admin from '@/pages/Admin';
import NotFound from '@/pages/NotFound';
import Forbidden from '@/pages/Forbidden';

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
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <main
        className={cn(
          'flex-1 transition-all duration-200',
          'pb-16 md:pb-0',
          sidebarExpanded ? 'md:ml-60' : 'md:ml-16',
        )}
      >
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>

      <BottomNav />
      <PodcastPlayer />
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
        <ToastContainer />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forbidden" element={<Forbidden />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Feed />} />
            <Route path="/categories" element={<Categories />} />
            <Route path="/shared" element={<SharedWithMe />} />
            <Route path="/podcasts" element={<PodcastLibrary />} />
            <Route path="/ratings" element={<MyRatings />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/admin" element={<Admin />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
