import { NavLink } from 'react-router-dom';
import { Newspaper, FolderOpen, Share2, Headphones, User } from 'lucide-react';
import { cn } from '@/lib/utils';

const tabs = [
  { to: '/', icon: Newspaper, label: 'Feed' },
  { to: '/categories', icon: FolderOpen, label: 'Collections' },
  { to: '/shared', icon: Share2, label: 'Shared' },
  { to: '/podcasts', icon: Headphones, label: 'Podcasts' },
  { to: '/profile', icon: User, label: 'Profile' },
];

export default function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex h-16 items-center justify-around border-t border-border-default bg-bg-surface md:hidden">
      {tabs.map((tab) => (
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
          <tab.icon size={20} />
          <span className="font-mono">{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
