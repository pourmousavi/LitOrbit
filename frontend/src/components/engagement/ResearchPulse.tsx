import { useState, useEffect } from 'react';
import { Flame, Star, Headphones, FolderOpen, Share2, Eye, X, ChevronDown, ChevronUp, Trophy } from 'lucide-react';
import { useEngagement } from '@/hooks/useEngagement';

function getISOWeek(): string {
  const now = new Date();
  const monday = new Date(now);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  return monday.toISOString().slice(0, 10);
}

export default function ResearchPulse() {
  const { data: pulse, isLoading } = useEngagement();
  const [activeTab, setActiveTab] = useState<'my' | 'lab'>('my');
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('litorbit-pulse-collapsed') === 'true';
  });
  const [dismissed, setDismissed] = useState(() => {
    const stored = localStorage.getItem('litorbit-pulse-dismissed');
    return stored === getISOWeek();
  });

  useEffect(() => {
    localStorage.setItem('litorbit-pulse-collapsed', String(collapsed));
  }, [collapsed]);

  if (isLoading || !pulse || dismissed) return null;

  const totalToReview = pulse.weekly_stats.rated + pulse.unreviewed_count;
  const pct = totalToReview > 0 ? Math.round((pulse.weekly_stats.rated / totalToReview) * 100) : 100;
  const myRank = pulse.leaderboard.findIndex((e) => e.is_current_user) + 1;

  const handleDismiss = () => {
    localStorage.setItem('litorbit-pulse-dismissed', getISOWeek());
    setDismissed(true);
  };

  // Collapsed mode — compact summary line
  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="w-full rounded-xl border border-border-default bg-bg-surface font-mono text-sm text-text-secondary transition hover:bg-bg-elevated"
        style={{ padding: '10px 14px', marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>{pulse.weekly_stats.rated}/{totalToReview} rated</span>
          {pulse.streak > 0 && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
              <Flame size={12} style={{ color: '#f97316' }} /> {pulse.streak}
            </span>
          )}
          {myRank > 0 && <span>#{myRank} in lab</span>}
        </span>
        <ChevronDown size={14} />
      </button>
    );
  }

  return (
    <div
      className="rounded-xl border border-border-default bg-bg-surface"
      style={{ marginBottom: 12, overflow: 'hidden' }}
    >
      {/* Header: tabs + controls */}
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px 0' }}
      >
        <div style={{ display: 'flex', gap: 0 }}>
          <button
            onClick={() => setActiveTab('my')}
            className={`font-mono text-xs font-medium transition ${activeTab === 'my' ? 'text-accent' : 'text-text-tertiary hover:text-text-secondary'}`}
            style={{ padding: '6px 12px', borderBottom: activeTab === 'my' ? '2px solid var(--color-accent, #0891b2)' : '2px solid transparent' }}
          >
            My Pulse
          </button>
          <button
            onClick={() => setActiveTab('lab')}
            className={`font-mono text-xs font-medium transition ${activeTab === 'lab' ? 'text-accent' : 'text-text-tertiary hover:text-text-secondary'}`}
            style={{ padding: '6px 12px', borderBottom: activeTab === 'lab' ? '2px solid var(--color-accent, #0891b2)' : '2px solid transparent' }}
          >
            Lab Pulse
          </button>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => setCollapsed(true)}
            className="rounded p-1 text-text-tertiary transition hover:bg-bg-elevated hover:text-text-secondary"
          >
            <ChevronUp size={14} />
          </button>
          <button
            onClick={handleDismiss}
            className="rounded p-1 text-text-tertiary transition hover:bg-bg-elevated hover:text-text-secondary"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '12px 14px 14px' }}>
        {activeTab === 'my' ? (
          <MyPulseTab pulse={pulse} pct={pct} totalToReview={totalToReview} />
        ) : (
          <LabPulseTab pulse={pulse} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// My Pulse Tab
// ---------------------------------------------------------------------------

function MyPulseTab({
  pulse,
  pct,
  totalToReview,
}: {
  pulse: NonNullable<ReturnType<typeof useEngagement>['data']>;
  pct: number;
  totalToReview: number;
}) {
  const barColor = pct >= 75 ? '#22c55e' : pct >= 25 ? '#eab308' : '#ef4444';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Progress bar */}
      <div>
        <div className="font-mono text-xs text-text-secondary" style={{ marginBottom: 4, display: 'flex', justifyContent: 'space-between' }}>
          <span>{pulse.weekly_stats.rated}/{totalToReview} rated</span>
          <span>{pct}%</span>
        </div>
        <div
          style={{ height: 6, borderRadius: 3, background: 'var(--color-bg-elevated, #1e293b)', overflow: 'hidden' }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div style={{ height: '100%', width: `${pct}%`, borderRadius: 3, background: barColor, transition: 'width 0.3s' }} />
        </div>
      </div>

      {/* Streak + Points row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        {pulse.streak > 0 && (
          <span className="font-mono text-xs text-text-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <Flame size={13} style={{ color: '#f97316' }} />
            {pulse.streak}-day streak
            {pulse.streak >= pulse.best_streak && pulse.streak > 1 && (
              <span className="text-accent" style={{ marginLeft: 2 }}>(best!)</span>
            )}
          </span>
        )}
        <span className="font-mono text-xs text-text-tertiary">
          {pulse.weekly_points} pts this week
        </span>
      </div>

      {/* Activity breakdown */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <ActivityStat icon={Star} count={pulse.weekly_stats.rated} label="rated" />
        <ActivityStat icon={Headphones} count={pulse.weekly_stats.podcasts} label="podcasts" />
        <ActivityStat icon={FolderOpen} count={pulse.weekly_stats.collected} label="collected" />
        <ActivityStat icon={Share2} count={pulse.weekly_stats.shared} label="shared" />
        <ActivityStat icon={Eye} count={pulse.weekly_stats.opened} label="opened" />
      </div>

      {/* Piling up warning */}
      {pulse.unreviewed_count > 3 && (
        <div
          className="font-mono text-xs"
          style={{
            padding: '8px 10px',
            borderRadius: 8,
            background: 'rgba(234, 179, 8, 0.1)',
            color: '#eab308',
            border: '1px solid rgba(234, 179, 8, 0.2)',
          }}
        >
          {pulse.unreviewed_count} papers piling up — rate them to improve your recommendations
        </div>
      )}
    </div>
  );
}

function ActivityStat({ icon: Icon, count, label }: { icon: typeof Star; count: number; label: string }) {
  return (
    <span className="font-mono text-xs text-text-tertiary" style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
      <Icon size={12} /> {count} {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Lab Pulse Tab
// ---------------------------------------------------------------------------

function LabPulseTab({ pulse }: { pulse: NonNullable<ReturnType<typeof useEngagement>['data']> }) {
  const labPct = pulse.lab_review_pct;
  const barColor = labPct >= 75 ? '#22c55e' : labPct >= 25 ? '#eab308' : '#ef4444';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Team progress */}
      <div>
        <div className="font-mono text-xs text-text-secondary" style={{ marginBottom: 4, display: 'flex', justifyContent: 'space-between' }}>
          <span>Lab reviewed {pulse.lab_reviewed}/{pulse.lab_total_papers}</span>
          <span>{labPct}%</span>
        </div>
        <div style={{ height: 6, borderRadius: 3, background: 'var(--color-bg-elevated, #1e293b)', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${Math.min(labPct, 100)}%`, borderRadius: 3, background: barColor, transition: 'width 0.3s' }} />
        </div>
      </div>

      {/* Leaderboard */}
      {pulse.leaderboard.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {pulse.leaderboard.map((entry, i) => (
            <div
              key={entry.user_id}
              className="font-mono text-xs"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 8px',
                borderRadius: 6,
                background: entry.is_current_user ? 'var(--color-accent-subtle, rgba(8, 145, 178, 0.1))' : 'transparent',
                color: entry.is_current_user ? 'var(--color-accent, #0891b2)' : undefined,
              }}
              data-testid={entry.is_current_user ? 'leaderboard-current-user' : undefined}
            >
              <span style={{ width: 20, textAlign: 'center', fontWeight: 600 }} className="text-text-secondary">
                {i === 0 ? <Trophy size={12} style={{ color: '#eab308' }} /> : `${i + 1}.`}
              </span>
              <span style={{ flex: 1 }} className={entry.is_current_user ? 'text-accent' : 'text-text-primary'}>
                {entry.full_name}
              </span>
              <span style={{ fontWeight: 600, minWidth: 40, textAlign: 'right' }} className="text-text-secondary">
                {entry.points} pts
              </span>
              <span className="text-text-tertiary" style={{ display: 'flex', gap: 6, marginLeft: 4 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}><Star size={10} />{entry.activity.rated}</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}><Headphones size={10} />{entry.activity.podcasts}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
