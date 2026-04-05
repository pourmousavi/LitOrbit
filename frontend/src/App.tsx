import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { useProfile } from '@/hooks/useProfile';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import ToastContainer from '@/components/ui/Toast';
import Sidebar from '@/components/layout/Sidebar';
import BottomNav from '@/components/layout/BottomNav';
import PodcastPlayer from '@/components/layout/PodcastPlayer';
import Login from '@/pages/Login';
import ResetPassword from '@/pages/ResetPassword';
import UpdatePassword from '@/pages/UpdatePassword';
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

function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)');
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return isDesktop;
}

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

function AdminRoute() {
  const { data: profile, isLoading } = useProfile();
  if (isLoading) return null;
  if (profile?.role !== 'admin') return <Navigate to="/forbidden" replace />;
  return <Admin />;
}

function AppLayout() {
  const sidebarExpanded = useUIStore((s) => s.sidebarExpanded);
  const isDesktop = useIsDesktop();
  const sidebarWidth = sidebarExpanded ? 240 : 64;

  return (
    <div className="min-h-svh bg-bg-base">
      {isDesktop && <Sidebar />}

      <div
        className="min-h-svh transition-all duration-200"
        style={{ marginLeft: isDesktop ? sidebarWidth : 0, paddingBottom: isDesktop ? 0 : 64 }}
      >
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </div>

      {!isDesktop && <BottomNav />}
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
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/update-password" element={<UpdatePassword />} />
          <Route path="/forbidden" element={<Forbidden />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Feed />} />
            <Route path="/categories" element={<Categories />} />
            <Route path="/shared" element={<SharedWithMe />} />
            <Route path="/podcasts" element={<PodcastLibrary />} />
            <Route path="/ratings" element={<MyRatings />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/admin" element={<AdminRoute />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
