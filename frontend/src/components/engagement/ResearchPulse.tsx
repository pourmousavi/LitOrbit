import { useState } from 'react';
import { Zap, ChevronDown, ChevronUp, Flame, Star, Headphones, FolderOpen, Share2, Eye, Bookmark, AlertTriangle } from 'lucide-react';
import { useEngagement } from '@/hooks/useEngagement';
import { usePulseSettings } from '@/stores/pulseSettingsStore';
import type { PulseData } from '@/types';

/**
 * PulseBanner — compact full-width banner pinned above the feed.
 *
 * Layout: accent stripe | rank + points | weekly sparkline | top-3 leaderboard
 * Click expands to full detail (streak, sparklets, full leaderboard).
 */
export default function ResearchPulse() {
  const { data: pulse, isLoading, isError } = useEngagement();
  const { showPulseCard } = usePulseSettings();
  const [expanded, setExpanded] = useState(false);

  if (!showPulseCard || isLoading || isError || !pulse) return null;

  const myRank = pulse.leaderboard.findIndex((e) => e.is_current_user) + 1;
  const totalMembers = pulse.leaderboard.length;
  const top3 = pulse.leaderboard.slice(0, 3);
  const medalEmoji = ['', '', ''];
  const changeVsLastWeek = pulse.weekly_points - pulse.last_week_points;

  return (
    <div
      style={{ marginBottom: 12, borderRadius: 12, overflow: 'hidden', position: 'relative',
        border: '1px solid var(--color-border-default, #2a2a2a)',
        background: 'var(--color-bg-surface, #141414)' }}
    >
      {/* Accent stripe */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
        background: 'linear-gradient(180deg, #f59e0b, var(--color-accent, #0891b2))' }} />

      {/* Banner row — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{ width: '100%', textAlign: 'left', padding: '14px 16px 14px 20px',
          display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer',
          background: 'none', border: 'none', color: 'inherit' }}
      >
        {/* Rank + points */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <Zap size={16} style={{ color: '#f59e0b' }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span className="font-mono" style={{ fontSize: 13, color: 'var(--color-text-primary, #f0f0f0)',
              fontWeight: 600, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
              #{myRank} of {totalMembers}
            </span>
            <span className="font-mono" style={{ fontSize: 11, color: '#888', lineHeight: 1,
              fontVariantNumeric: 'tabular-nums' }}>
              {changeVsLastWeek >= 0 ? '+' : ''}{changeVsLastWeek} pts this week
            </span>
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 28, background: 'var(--color-border-default, #2a2a2a)', flexShrink: 0 }} />

        {/* Weekly sparkline */}
        <Sparkline points={pulse.weekly_points} streak={pulse.streak} />

        {/* Divider */}
        <div className="hidden md:block" style={{ width: 1, height: 28, background: 'var(--color-border-default, #2a2a2a)', flexShrink: 0 }} />

        {/* Mini leaderboard — desktop only */}
        <div className="hidden md:flex" style={{ gap: 16, flex: 1, justifyContent: 'flex-end', alignItems: 'center' }}>
          {top3.map((entry, i) => (
            <span key={entry.user_id} className="font-mono" style={{
              fontSize: 11, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
              color: entry.is_current_user ? 'var(--color-accent, #0891b2)' : '#888',
              fontWeight: entry.is_current_user ? 600 : 400,
            }}>
              {medalEmoji[i]} {entry.full_name.split(' ')[0]} ({entry.points})
            </span>
          ))}
        </div>

        {/* Expand chevron */}
        <div style={{ flexShrink: 0, color: '#555' }}>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && <PulseDetail pulse={pulse} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sparkline — 7 dots representing daily activity this week
// ---------------------------------------------------------------------------

function Sparkline({ points, streak }: { points: number; streak: number }) {
  // Simple visual: 7 dots for each day, filled based on streak
  const days = 7;
  const streakDays = Math.min(streak, days);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end' }}>
        {Array.from({ length: days }).map((_, i) => {
          const active = i >= days - streakDays;
          const height = active ? 8 + Math.random() * 12 : 4;
          return (
            <div key={i} style={{
              width: 6, height, borderRadius: 2,
              background: active ? 'var(--color-accent, #0891b2)' : '#2a2a2a',
              transition: 'height 0.3s ease',
            }} />
          );
        })}
      </div>
      <span className="font-mono" style={{ fontSize: 12, color: 'var(--color-text-primary, #f0f0f0)',
        fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
        {points}<span style={{ color: '#555', fontWeight: 400 }}> pts</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expanded detail — streak, activity sparklets, full leaderboard
// ---------------------------------------------------------------------------

function PulseDetail({ pulse }: { pulse: PulseData }) {
  const rest = pulse.leaderboard.slice(3);
  const [showAll, setShowAll] = useState(false);

  return (
    <div style={{ padding: '0 20px 20px', borderTop: '1px solid var(--color-border-default, #2a2a2a)',
      display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 16 }}>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Flame size={14} style={{ color: '#f59e0b' }} />
          <span className="font-mono" style={{ fontSize: 12, color: 'var(--color-text-primary, #f0f0f0)',
            fontVariantNumeric: 'tabular-nums' }}>
            {pulse.streak}<span style={{ color: '#555' }}>d streak</span>
          </span>
          <span className="font-mono" style={{ fontSize: 10, color: '#555', fontVariantNumeric: 'tabular-nums' }}>
            (best {pulse.best_streak}d)
          </span>
        </div>
        <span className="font-mono" style={{ fontSize: 12, color: '#888' }}>
          <span style={{ color: 'var(--color-text-primary, #f0f0f0)', fontVariantNumeric: 'tabular-nums' }}>
            {pulse.weekly_stats.rated + (pulse.weekly_stats.news_rated || 0)}
          </span> rated
          <span style={{ color: '#555' }}> / </span>
          <span style={{ color: 'var(--color-text-primary, #f0f0f0)', fontVariantNumeric: 'tabular-nums' }}>
            {pulse.weekly_stats.opened + (pulse.weekly_stats.news_viewed || 0)}
          </span> opened
        </span>
      </div>

      {/* Activity sparklets */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <MiniStat label="rated" v={pulse.weekly_stats.rated + (pulse.weekly_stats.news_rated || 0)} Icon={Star} />
        <MiniStat label="opened" v={pulse.weekly_stats.opened + (pulse.weekly_stats.news_viewed || 0)} Icon={Eye} />
        <MiniStat label="starred" v={(pulse.weekly_stats.news_starred || 0)} Icon={Bookmark} />
        <MiniStat label="podcasts" v={pulse.weekly_stats.podcasts} Icon={Headphones} />
        <MiniStat label="collected" v={pulse.weekly_stats.collected} Icon={FolderOpen} />
        <MiniStat label="shared" v={pulse.weekly_stats.shared} Icon={Share2} />
      </div>

      {/* Nudge */}
      {pulse.unreviewed_count > 3 && (
        <div style={{ padding: '10px 12px', borderRadius: 8,
          background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)',
          display: 'flex', alignItems: 'center', gap: 10 }}>
          <AlertTriangle size={13} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <span className="font-mono" style={{ fontSize: 11, color: '#888' }}>
            <span style={{ color: '#f59e0b' }}>{pulse.unreviewed_count}</span> unrated papers
          </span>
        </div>
      )}

      {/* Full leaderboard */}
      <div>
        <span className="font-mono" style={{ fontSize: 9, color: '#555', letterSpacing: '0.12em',
          textTransform: 'uppercase', marginBottom: 8, display: 'block' }}>
          Leaderboard
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1,
          background: 'var(--color-border-default, #2a2a2a)', borderRadius: 8, overflow: 'hidden',
          border: '1px solid var(--color-border-default, #2a2a2a)' }}>
          {pulse.leaderboard.slice(0, showAll ? undefined : 3).map((e, i) => (
            <div key={e.user_id} style={{ padding: '8px 12px', background: 'var(--color-bg-surface, #141414)',
              display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="font-mono" style={{ fontSize: 10, width: 18, color: '#555',
                fontVariantNumeric: 'tabular-nums' }}>
                {i === 0 ? '' : i === 1 ? '' : i === 2 ? '' : String(i + 1).padStart(2, '0')}
              </span>
              <span className="font-mono" style={{ flex: 1, fontSize: 11,
                color: e.is_current_user ? 'var(--color-accent, #0891b2)' : 'var(--color-text-primary, #f0f0f0)',
                fontWeight: e.is_current_user ? 600 : 400 }}>
                {e.full_name}
              </span>
              <span className="font-mono" style={{ fontSize: 11, fontVariantNumeric: 'tabular-nums',
                color: e.is_current_user ? 'var(--color-accent, #0891b2)' : '#888' }}>
                {e.points}<span style={{ color: '#555' }}> pts</span>
              </span>
            </div>
          ))}
        </div>
        {rest.length > 0 && (
          <button onClick={() => setShowAll(!showAll)} className="font-mono"
            style={{ fontSize: 10, color: '#555', marginTop: 6, letterSpacing: '0.08em',
              textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 4 }}>
            {showAll ? 'Show less' : `Show all ${pulse.leaderboard.length}`}
            {showAll ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          </button>
        )}
      </div>
    </div>
  );
}

function MiniStat({ label, v, Icon }: { label: string; v: number; Icon: typeof Star }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <Icon size={11} style={{ color: '#555' }} />
      <span className="font-mono" style={{ fontSize: 11, color: 'var(--color-text-primary, #f0f0f0)',
        fontVariantNumeric: 'tabular-nums' }}>
        {v}
      </span>
      <span className="font-mono" style={{ fontSize: 9, color: '#555', letterSpacing: '0.04em' }}>
        {label}
      </span>
    </div>
  );
}
