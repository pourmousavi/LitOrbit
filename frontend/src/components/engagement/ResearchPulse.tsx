import { useState } from 'react';
import { Flame, Star, Headphones, FolderOpen, Share2, Eye, ChevronDown, ChevronUp, Trophy, AlertTriangle, Newspaper, ThumbsUp, Bookmark } from 'lucide-react';
import { useEngagement } from '@/hooks/useEngagement';
import { usePulseSettings } from '@/stores/pulseSettingsStore';
import type { PulseData } from '@/types';

function getWeekNumber(): number {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 1);
  const diff = now.getTime() - start.getTime();
  return Math.ceil((diff / 86400000 + start.getDay() + 1) / 7);
}

function pctColor(pct: number): string {
  if (pct >= 75) return 'var(--color-success, #22c55e)';
  if (pct >= 40) return 'var(--color-accent, #0891b2)';
  if (pct >= 15) return '#888';
  return '#555';
}

// SVG ring gauge
function Ring({ pct, size = 96, stroke = 3, color, track = 'var(--color-bg-elevated, #1c1c1c)' }: {
  pct: number; size?: number; stroke?: number; color: string; track?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - Math.min(pct, 100) / 100);
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
        style={{ transition: 'stroke-dashoffset .5s cubic-bezier(.2,.8,.2,1)' }} />
    </svg>
  );
}

// Decorative orbit background
function OrbitBg() {
  return (
    <svg style={{ position: 'absolute', right: -40, top: -40, opacity: 0.18, pointerEvents: 'none' }}
      width="280" height="280" viewBox="0 0 280 280">
      <circle cx="140" cy="140" r="60" fill="none" stroke="var(--color-accent, #0891b2)" strokeWidth="0.5" strokeDasharray="2 4" />
      <circle cx="140" cy="140" r="100" fill="none" stroke="#555" strokeWidth="0.5" strokeDasharray="2 6" />
      <circle cx="140" cy="140" r="130" fill="none" stroke="#555" strokeWidth="0.5" strokeDasharray="1 8" />
    </svg>
  );
}

export default function ResearchPulse() {
  const { data: pulse, isLoading, isError } = useEngagement();
  const { showPulseCard } = usePulseSettings();
  const [tab, setTab] = useState<'my' | 'lab'>('my');

  if (!showPulseCard || isLoading || isError || !pulse) return null;

  const total = pulse.weekly_stats.rated + pulse.unreviewed_count;
  const pct = total > 0 ? Math.round((pulse.weekly_stats.rated / total) * 100) : 100;

  return (
    <div style={{ marginBottom: 12, borderRadius: 12, border: '1px solid var(--color-border-default, #2a2a2a)',
      background: 'var(--color-bg-surface, #141414)', overflow: 'hidden', position: 'relative' }}>
      <OrbitBg />

      {/* Tab header */}
      <div style={{ position: 'relative', padding: '16px 18px', display: 'flex', gap: 8,
        alignItems: 'center', borderBottom: '1px solid var(--color-border-default, #2a2a2a)' }}>
        {(['my', 'lab'] as const).map((k) => (
          <button key={k} onClick={() => setTab(k)}
            className="font-mono"
            style={{
              fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase',
              padding: '5px 10px', borderRadius: 999,
              background: tab === k ? 'var(--color-bg-elevated, #1c1c1c)' : 'transparent',
              color: tab === k ? 'var(--color-text-primary, #f0f0f0)' : '#555',
              border: tab === k ? '1px solid rgba(8,145,178,0.4)' : '1px solid transparent',
            }}>
            {k === 'my' ? 'My Pulse' : 'Lab Pulse'}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <span className="font-mono" style={{ fontSize: 10, color: '#555', letterSpacing: '0.12em',
          fontVariantNumeric: 'tabular-nums' }}>
          WK {getWeekNumber()}
        </span>
      </div>

      {/* Content */}
      <div style={{ position: 'relative', padding: '22px 20px 20px' }}>
        {tab === 'my'
          ? <MyOrbit pulse={pulse} pct={pct} total={total} />
          : <LabOrbit pulse={pulse} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// My Pulse
// ---------------------------------------------------------------------------

function MyOrbit({ pulse, pct, total }: { pulse: PulseData; pct: number; total: number }) {
  const bar = pctColor(pct);
  const newsTotal = (pulse.weekly_stats.news_viewed || 0)
    + (pulse.weekly_stats.news_rated || 0)
    + (pulse.weekly_stats.news_starred || 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Ring + headline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <Ring pct={pct} color={bar} />
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 28, lineHeight: 1, color: 'var(--color-text-primary, #f0f0f0)',
              fontWeight: 400, fontVariantNumeric: 'tabular-nums' }}>
              {pct}<span style={{ fontSize: 14, color: '#555' }}>%</span>
            </span>
            <span className="font-mono" style={{ fontSize: 9, color: '#555', letterSpacing: '0.1em', marginTop: 2 }}>
              RATED
            </span>
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="font-mono" style={{ fontSize: 10, color: '#555', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            This week
          </span>
          <div style={{ fontSize: 26, color: 'var(--color-text-primary, #f0f0f0)', lineHeight: 1.05,
            fontWeight: 400, fontVariantNumeric: 'tabular-nums' }}>
            {pulse.weekly_stats.rated}<span style={{ color: '#555', fontSize: 18 }}> of {total}</span>
          </div>
          <span className="font-mono" style={{ fontSize: 11, color: '#888' }}>
            <span style={{ color: 'var(--color-text-primary, #f0f0f0)', fontVariantNumeric: 'tabular-nums' }}>
              {pulse.weekly_points}
            </span> pts earned
          </span>
        </div>
      </div>

      {/* Streak strip */}
      <StreakStrip streak={pulse.streak} best={pulse.best_streak} />

      {/* Paper activity sparklets */}
      <div>
        <span className="font-mono" style={{ fontSize: 9, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6, display: 'block' }}>
          Papers
        </span>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          <Sparklet label="rated" v={pulse.weekly_stats.rated} Icon={Star} />
          <Sparklet label="podcasts" v={pulse.weekly_stats.podcasts} Icon={Headphones} />
          <Sparklet label="collected" v={pulse.weekly_stats.collected} Icon={FolderOpen} />
          <Sparklet label="shared" v={pulse.weekly_stats.shared} Icon={Share2} />
          <Sparklet label="opened" v={pulse.weekly_stats.opened} Icon={Eye} />
        </div>
      </div>

      {/* News activity sparklets */}
      {newsTotal > 0 && (
        <div>
          <span className="font-mono" style={{ fontSize: 9, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6, display: 'block' }}>
            News
          </span>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <Sparklet label="read" v={pulse.weekly_stats.news_viewed || 0} Icon={Newspaper} accent="#f59e0b" />
            <Sparklet label="rated" v={pulse.weekly_stats.news_rated || 0} Icon={ThumbsUp} accent="#f59e0b" />
            <Sparklet label="starred" v={pulse.weekly_stats.news_starred || 0} Icon={Bookmark} accent="#f59e0b" />
          </div>
        </div>
      )}

      {/* Nudge */}
      {pulse.unreviewed_count > 3 && (
        <div style={{ padding: '12px 14px', borderRadius: 10,
          background: 'linear-gradient(90deg, rgba(245,158,11,0.08), transparent)',
          border: '1px solid rgba(245,158,11,0.18)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <AlertTriangle size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <span className="font-mono" style={{ fontSize: 11, color: '#888', flex: 1 }}>
            <span style={{ color: '#f59e0b', fontVariantNumeric: 'tabular-nums' }}>{pulse.unreviewed_count}</span> unrated —
            your recommendations are getting stale
          </span>
        </div>
      )}
    </div>
  );
}

function Sparklet({ label, v, Icon, accent }: { label: string; v: number; Icon: typeof Star; accent?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 48 }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: accent || '#555' }}>
        <Icon size={10} />
        <span className="font-mono" style={{ fontSize: 9, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{label}</span>
      </div>
      <span style={{ fontSize: 16, color: 'var(--color-text-primary, #f0f0f0)', fontWeight: 400,
        lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
    </div>
  );
}

function StreakStrip({ streak, best }: { streak: number; best: number }) {
  const days = Array(14).fill(false).map((_, i) => i >= 14 - streak);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
      borderRadius: 8, background: 'var(--color-bg-elevated, #1c1c1c)',
      border: '1px solid var(--color-border-default, #2a2a2a)' }}>
      <Flame size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />
      <span className="font-mono" style={{ fontSize: 12, color: 'var(--color-text-primary, #f0f0f0)',
        minWidth: 62, fontVariantNumeric: 'tabular-nums' }}>
        {streak}<span style={{ color: '#555' }}>-day streak</span>
      </span>
      <div style={{ display: 'flex', gap: 3, flex: 1, minWidth: 0 }}>
        {days.map((on, i) => (
          <div key={i} style={{ flex: 1, height: 10, borderRadius: 2,
            background: on ? '#f59e0b' : '#232323',
            opacity: on ? (0.4 + (i / days.length) * 0.6) : 1 }} />
        ))}
      </div>
      <span className="font-mono" style={{ fontSize: 10, color: '#555', minWidth: 48, textAlign: 'right',
        fontVariantNumeric: 'tabular-nums' }}>
        best {best}d
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Lab Pulse
// ---------------------------------------------------------------------------

function LabOrbit({ pulse }: { pulse: PulseData }) {
  const pct = pulse.lab_review_pct;
  const bar = pctColor(pct);
  const top3 = pulse.leaderboard.slice(0, 3);
  const rest = pulse.leaderboard.slice(3);
  const [expanded, setExpanded] = useState(false);
  const accent = 'var(--color-accent, #0891b2)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Ring + headline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <Ring pct={pct} color={bar} />
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 28, lineHeight: 1, color: 'var(--color-text-primary, #f0f0f0)',
              fontWeight: 400, fontVariantNumeric: 'tabular-nums' }}>
              {pct}<span style={{ fontSize: 14, color: '#555' }}>%</span>
            </span>
            <span className="font-mono" style={{ fontSize: 9, color: '#555', letterSpacing: '0.1em', marginTop: 2 }}>
              LAB
            </span>
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="font-mono" style={{ fontSize: 10, color: '#555', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            Team progress
          </span>
          <div style={{ fontSize: 26, color: 'var(--color-text-primary, #f0f0f0)', lineHeight: 1.05,
            fontVariantNumeric: 'tabular-nums' }}>
            {pulse.lab_reviewed}<span style={{ color: '#555', fontSize: 18 }}> of {pulse.lab_total_papers}</span>
          </div>
          <span className="font-mono" style={{ fontSize: 11, color: '#888' }}>
            across <span style={{ color: 'var(--color-text-primary, #f0f0f0)', fontVariantNumeric: 'tabular-nums' }}>
              {pulse.leaderboard.length}
            </span> members
          </span>
        </div>
      </div>

      {/* Podium — top 3 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        {top3.map((e, i) => {
          const newsTotal = (e.activity.news_viewed || 0) + (e.activity.news_rated || 0) + (e.activity.news_starred || 0);
          return (
            <div key={e.user_id} style={{ padding: '10px 12px', borderRadius: 8,
              background: e.is_current_user ? 'rgba(8,145,178,0.09)' : 'var(--color-bg-elevated, #1c1c1c)',
              border: e.is_current_user ? '1px solid rgba(8,145,178,0.33)' : '1px solid var(--color-border-default, #2a2a2a)',
              display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="font-mono" style={{ fontSize: 10, color: '#555', fontVariantNumeric: 'tabular-nums' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                {i === 0 && <Trophy size={11} style={{ color: '#f59e0b' }} />}
                <span style={{ flex: 1 }} />
                <span className="font-mono" style={{ fontSize: 11, fontVariantNumeric: 'tabular-nums',
                  color: e.is_current_user ? accent : 'var(--color-text-primary, #f0f0f0)' }}>
                  {e.points}<span style={{ color: '#555' }}>pts</span>
                </span>
              </div>
              <span className="font-mono" style={{ fontSize: 11,
                color: e.is_current_user ? accent : 'var(--color-text-primary, #f0f0f0)',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {e.full_name}
              </span>
              {/* Compact breakdown */}
              <div className="font-mono" style={{ fontSize: 9, color: '#555', display: 'flex', gap: 6 }}>
                <span>{e.activity.rated}r</span>
                {newsTotal > 0 && <span style={{ color: '#f59e0b' }}>{newsTotal}n</span>}
              </div>
            </div>
          );
        })}
      </div>

      {/* Expandable rest */}
      {rest.length > 0 && (
        <button onClick={() => setExpanded(!expanded)}
          className="font-mono"
          style={{ alignSelf: 'flex-start', fontSize: 10, color: '#555', letterSpacing: '0.1em',
            textTransform: 'uppercase', display: 'inline-flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
          {expanded ? 'Hide' : 'Show'} all {pulse.leaderboard.length} members
          {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        </button>
      )}
      {expanded && rest.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1,
          background: 'var(--color-border-default, #2a2a2a)', borderRadius: 6, overflow: 'hidden',
          border: '1px solid var(--color-border-default, #2a2a2a)' }}>
          {rest.map((e, i) => {
            const newsTotal = (e.activity.news_viewed || 0) + (e.activity.news_rated || 0) + (e.activity.news_starred || 0);
            return (
              <div key={e.user_id} style={{ padding: '8px 12px', background: 'var(--color-bg-surface, #141414)',
                display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="font-mono" style={{ fontSize: 10, color: '#555', width: 18,
                  fontVariantNumeric: 'tabular-nums' }}>
                  {String(i + 4).padStart(2, '0')}
                </span>
                <span className="font-mono" style={{ flex: 1, fontSize: 11, color: 'var(--color-text-primary, #f0f0f0)' }}>
                  {e.full_name}
                </span>
                {newsTotal > 0 && (
                  <span className="font-mono" style={{ fontSize: 9, color: '#f59e0b', fontVariantNumeric: 'tabular-nums' }}>
                    {newsTotal}n
                  </span>
                )}
                <span className="font-mono" style={{ fontSize: 11, color: '#888', fontVariantNumeric: 'tabular-nums' }}>
                  {e.points}<span style={{ color: '#555' }}>pts</span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
