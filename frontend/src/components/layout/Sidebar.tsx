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
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { useProfile } from '@/hooks/useProfile';
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
        className="flex h-14 shrink-0 items-center border-b border-border-default"
        style={{ justifyContent: expanded ? 'space-between' : 'center', padding: '0 12px' }}
      >
        {expanded && (
          <span className="font-mono text-lg font-medium text-text-primary">LitOrbit</span>
        )}
        <button
          onClick={toggleSidebar}
          className="rounded-md p-1.5 text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary"
        >
          {expanded ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
        </button>
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
              {expanded && <span>{item.label}</span>}
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
        {expanded && user?.email && (
          <p className="truncate text-xs text-text-tertiary" style={{ padding: '4px 12px' }}>
            {user.email}
          </p>
        )}
      </div>
    </aside>
  );
}
