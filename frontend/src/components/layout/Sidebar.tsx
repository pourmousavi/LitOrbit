import { NavLink, useNavigate } from 'react-router-dom';
import {
  Newspaper,
  FolderOpen,
  Share2,
  Headphones,
  Star,
  Shield,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeft,
  Flame,
  Check,
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { useProfile } from '@/hooks/useProfile';
import { useEngagement } from '@/hooks/useEngagement';
import { usePulseSettings } from '@/stores/pulseSettingsStore';
import NavBadge from '@/components/engagement/NavBadge';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/', icon: Newspaper, label: 'Feed' },
  { to: '/categories', icon: FolderOpen, label: 'Collections' },
  { to: '/shared', icon: Share2, label: 'Shared' },
  { to: '/podcasts', icon: Headphones, label: 'Podcasts' },
  { to: '/ratings', icon: Star, label: 'Ratings' },
  { to: '/admin', icon: Shield, label: 'Admin', adminOnly: true },
];

export default function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const { data: profile } = useProfile();
  const { data: pulse } = useEngagement();
  const pulseSettings = usePulseSettings();
  const expanded = useUIStore((s) => s.sidebarExpanded);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const navigate = useNavigate();
  const isAdmin = profile?.role === 'admin';
  const visibleItems = navItems.filter((item) => !item.adminOnly || isAdmin);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside
      style={{ width: expanded ? 240 : 64 }}
      className="fixed left-0 top-0 z-40 flex h-full flex-col border-r border-border-default bg-bg-surface transition-all duration-200"
    >
      {/* Header */}
      <div
        className="shrink-0 border-b border-border-default"
        style={{ padding: expanded ? '12px 12px' : '12px 0', display: 'flex', flexDirection: 'column', gap: 4,
          alignItems: expanded ? 'stretch' : 'center', minHeight: 56, justifyContent: 'center' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: expanded ? 'space-between' : 'center' }}>
          {expanded && (
            <span className="font-mono" style={{ fontSize: 17, fontWeight: 500, color: 'var(--color-text-primary, #f0f0f0)',
              letterSpacing: '-0.01em' }}>
              LitOrbit
            </span>
          )}
          <button
            onClick={toggleSidebar}
            className="rounded-md p-1.5 text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary"
          >
            {expanded ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
        </div>
        {expanded && pulseSettings.showSidebarStat && pulse && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 0,
            background: 'var(--color-bg-elevated, #1c1c1c)', borderRadius: 5, padding: '3px 6px',
            border: '1px solid var(--color-border-default, #2a2a2a)' }}>
            <span className="font-mono" style={{ fontSize: 10, color: 'var(--color-text-primary, #f0f0f0)',
              display: 'inline-flex', alignItems: 'center', gap: 3, fontVariantNumeric: 'tabular-nums' }}>
              <Flame size={9} style={{ color: '#f59e0b' }} />{pulse.streak}d
            </span>
            <span style={{ width: 1, height: 9, background: 'var(--color-border-default, #2a2a2a)', margin: '0 6px' }} />
            <span className="font-mono" style={{ fontSize: 10, color: 'var(--color-text-primary, #f0f0f0)',
              fontVariantNumeric: 'tabular-nums' }}>
              {pulse.weekly_points}<span style={{ color: '#555' }}>pts</span>
            </span>
            <span style={{ width: 1, height: 9, background: 'var(--color-border-default, #2a2a2a)', margin: '0 6px' }} />
            <span className="font-mono" style={{ fontSize: 10, fontVariantNumeric: 'tabular-nums',
              color: pulse.unreviewed_count > 0 ? 'var(--color-accent, #0891b2)' : 'var(--color-success, #22c55e)' }}>
              {pulse.unreviewed_count > 0 ? pulse.unreviewed_count : <Check size={11} />}
            </span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3" style={{ padding: '12px 8px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center rounded-lg font-mono text-sm transition',
                  isActive
                    ? 'bg-accent-subtle text-accent'
                    : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
                )
              }
              style={{
                gap: expanded ? 12 : 0,
                justifyContent: expanded ? 'flex-start' : 'center',
                padding: expanded ? '10px 12px' : '10px 0',
              }}
            >
              <item.icon size={18} style={{ flexShrink: 0 }} />
              {expanded && <span style={{ flex: 1 }}>{item.label}</span>}
              {expanded && item.label === 'Feed' && pulseSettings.showNavBadge && pulse && (
                <NavBadge count={pulse.unreviewed_count} />
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* User section */}
      <div className="shrink-0 border-t border-border-default" style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <NavLink
          to="/profile"
          className={({ isActive }) =>
            cn(
              'flex items-center rounded-lg font-mono text-sm transition',
              isActive
                ? 'bg-accent-subtle text-accent'
                : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
            )
          }
          style={{
            gap: expanded ? 12 : 0,
            justifyContent: expanded ? 'flex-start' : 'center',
            padding: expanded ? '10px 12px' : '10px 0',
          }}
        >
          <Settings size={18} style={{ flexShrink: 0 }} />
          {expanded && <span>Settings</span>}
        </NavLink>
        <button
          onClick={handleLogout}
          className="flex w-full items-center rounded-lg font-mono text-sm text-text-secondary transition hover:bg-bg-elevated hover:text-danger"
          style={{
            gap: expanded ? 12 : 0,
            justifyContent: expanded ? 'flex-start' : 'center',
            padding: expanded ? '10px 12px' : '10px 0',
          }}
        >
          <LogOut size={18} style={{ flexShrink: 0 }} />
          {expanded && <span>Sign out</span>}
        </button>
        {expanded && (profile?.email || user?.email) && (
          <p className="truncate text-xs text-text-tertiary" style={{ padding: '4px 12px' }}>
            {profile?.email || user?.email}
          </p>
        )}
      </div>
    </aside>
  );
}
