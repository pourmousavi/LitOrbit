import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Newspaper, FolderOpen, Share2, Headphones, Star, Shield, Settings, LogOut, MoreHorizontal, X } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useProfile } from '@/hooks/useProfile';
import { useEngagement } from '@/hooks/useEngagement';
import { usePulseSettings } from '@/stores/pulseSettingsStore';
import NavBadge from '@/components/engagement/NavBadge';
import { cn } from '@/lib/utils';

const primaryTabs = [
  { to: '/', icon: Newspaper, label: 'Feed' },
  { to: '/categories', icon: FolderOpen, label: 'Collections' },
  { to: '/shared', icon: Share2, label: 'Shared' },
  { to: '/podcasts', icon: Headphones, label: 'Podcasts' },
];

const moreTabs = [
  { to: '/ratings', icon: Star, label: 'Ratings' },
  { to: '/admin', icon: Shield, label: 'Admin', adminOnly: true },
  { to: '/profile', icon: Settings, label: 'Settings' },
];

export default function BottomNav() {
  const [showMore, setShowMore] = useState(false);
  const { data: profile } = useProfile();
  const { data: pulse } = useEngagement();
  const pulseSettings = usePulseSettings();
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const isAdmin = profile?.role === 'admin';

  const visibleMoreTabs = moreTabs.filter((t) => !t.adminOnly || isAdmin);

  const handleLogout = async () => {
    setShowMore(false);
    await logout();
    navigate('/login');
  };

  return (
    <>
      {/* More menu overlay */}
      {showMore && (
        <div
          className="fixed inset-0 z-40 bg-black/60"
          onClick={() => setShowMore(false)}
        />
      )}

      {/* More menu panel */}
      {showMore && (
        <div className="fixed bottom-16 left-0 right-0 z-50 border-t border-border-default bg-bg-surface px-4 py-4">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {visibleMoreTabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                onClick={() => setShowMore(false)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-xl px-4 font-mono text-sm transition',
                    isActive
                      ? 'bg-accent-subtle text-accent'
                      : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
                  )
                }
                style={{ minHeight: 48 }}
              >
                <tab.icon size={18} />
                {tab.label}
              </NavLink>
            ))}
            <div className="border-t border-border-default" style={{ margin: '2px 0' }} />
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-4 font-mono text-sm text-text-secondary transition hover:bg-bg-elevated hover:text-danger"
              style={{ minHeight: 48 }}
            >
              <LogOut size={18} />
              Sign out
            </button>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-16 items-center justify-around border-t border-border-default bg-bg-surface md:hidden">
        {primaryTabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              cn(
                'flex min-w-[44px] flex-col items-center gap-0.5 py-1 text-xs transition',
                isActive ? 'text-accent' : 'text-text-secondary',
              )
            }
          >
            <div style={{ position: 'relative', display: 'inline-flex' }}>
              <tab.icon size={20} />
              {tab.label === 'Feed' && pulseSettings.showNavBadge && pulse && (
                <NavBadge count={pulse.unreviewed_count} />
              )}
            </div>
            <span className="font-mono">{tab.label}</span>
          </NavLink>
        ))}
        <button
          onClick={() => setShowMore(!showMore)}
          className={cn(
            'flex min-w-[44px] flex-col items-center gap-0.5 py-1 text-xs transition',
            showMore ? 'text-accent' : 'text-text-secondary',
          )}
        >
          {showMore ? <X size={20} /> : <MoreHorizontal size={20} />}
          <span className="font-mono">More</span>
        </button>
      </nav>
    </>
  );
}
