import { NavLink, useNavigate } from 'react-router-dom';
import {
  Newspaper,
  LayoutGrid,
  Share2,
  Headphones,
  Star,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/', icon: Newspaper, label: 'Feed' },
  { to: '/categories', icon: LayoutGrid, label: 'Categories' },
  { to: '/shared', icon: Share2, label: 'Shared with Me' },
  { to: '/podcasts', icon: Headphones, label: 'Podcasts' },
  { to: '/ratings', icon: Star, label: 'My Ratings' },
];

export default function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const expanded = useUIStore((s) => s.sidebarExpanded);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-full flex-col border-r border-border-default bg-bg-surface transition-all duration-200',
        expanded ? 'w-60' : 'w-16',
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-border-default px-4">
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
      <nav className="flex-1 space-y-1 px-2 py-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 font-mono text-sm transition',
                isActive
                  ? 'bg-accent-subtle text-accent'
                  : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
                !expanded && 'justify-center px-0',
              )
            }
          >
            <item.icon size={18} />
            {expanded && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* User section */}
      <div className="border-t border-border-default p-2 space-y-1">
        <NavLink
          to="/profile"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 font-mono text-sm transition',
              isActive
                ? 'bg-accent-subtle text-accent'
                : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
              !expanded && 'justify-center px-0',
            )
          }
        >
          <Settings size={18} />
          {expanded && <span>Settings</span>}
        </NavLink>
        <button
          onClick={handleLogout}
          className={cn(
            'flex w-full items-center gap-3 rounded-lg px-3 py-2 font-mono text-sm text-text-secondary transition hover:bg-bg-elevated hover:text-danger',
            !expanded && 'justify-center px-0',
          )}
        >
          <LogOut size={18} />
          {expanded && <span>Sign out</span>}
        </button>
        {expanded && user?.email && (
          <p className="truncate px-3 py-1 text-xs text-text-tertiary">
            {user.email}
          </p>
        )}
      </div>
    </aside>
  );
}
