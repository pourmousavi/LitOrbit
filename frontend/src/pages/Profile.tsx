import { useState, type KeyboardEvent } from 'react';
import { Plus, X, Loader2 } from 'lucide-react';
import { useProfile, useUpdateProfile } from '@/hooks/useProfile';
import { cn } from '@/lib/utils';

function InterestChart({ vector }: { vector: Record<string, number> }) {
  const entries = Object.entries(vector)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 15);

  if (entries.length === 0) {
    return (
      <p style={{ padding: '24px 0', textAlign: 'center' }} className="font-mono text-sm text-text-tertiary">
        Rate papers to build your interest profile
      </p>
    );
  }

  const maxVal = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {entries.map(([cat, weight]) => (
        <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ width: 130, flexShrink: 0, textAlign: 'right' }} className="truncate font-mono text-xs text-text-secondary">
            {cat}
          </span>
          <div style={{ flex: 1, height: 20, display: 'flex', alignItems: 'center' }}>
            {weight >= 0 ? (
              <div
                className="rounded-r bg-success/60"
                style={{ height: '100%', width: `${(weight / maxVal) * 100}%`, minWidth: weight > 0 ? 3 : 0 }}
              />
            ) : (
              <div style={{ display: 'flex', height: '100%', width: '100%', justifyContent: 'flex-end' }}>
                <div
                  className="rounded-l bg-danger/60"
                  style={{ height: '100%', width: `${(Math.abs(weight) / maxVal) * 100}%`, minWidth: 3 }}
                />
              </div>
            )}
          </div>
          <span style={{ width: 48 }} className={cn('font-mono text-xs', weight >= 0 ? 'text-success' : 'text-danger')}>
            {weight >= 0 ? '+' : ''}{weight.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Profile() {
  const { data: profile, isLoading } = useProfile();
  const updateProfile = useUpdateProfile();
  const [newKeyword, setNewKeyword] = useState('');

  if (isLoading || !profile) {
    return (
      <div style={{ padding: '32px 24px' }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }} className="font-mono text-text-primary">Profile</h1>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
                <div className="h-4 w-1/3 rounded bg-bg-elevated" />
                <div className="mt-4 h-8 w-full rounded bg-bg-elevated" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const addKeyword = () => {
    const kw = newKeyword.trim();
    if (!kw || profile.interest_keywords.includes(kw)) return;
    updateProfile.mutate({ interest_keywords: [...profile.interest_keywords, kw] });
    setNewKeyword('');
  };

  const removeKeyword = (kw: string) => {
    updateProfile.mutate({ interest_keywords: profile.interest_keywords.filter((k) => k !== kw) });
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') addKeyword();
  };

  return (
    <div style={{ padding: '32px 24px' }}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 28 }} className="font-mono text-text-primary">Profile</h1>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* User info */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 16 }}>
              Account
            </h2>
            <p className="font-serif text-text-primary" style={{ fontSize: 20 }}>{profile.full_name}</p>
            <p className="font-mono text-sm text-text-secondary" style={{ marginTop: 4 }}>{profile.email}</p>
            <span
              className={cn(
                'inline-block rounded-full font-mono text-xs',
                profile.role === 'admin' ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-secondary',
              )}
              style={{ marginTop: 12, padding: '4px 14px' }}
            >
              {profile.role}
            </span>
          </section>

          {/* Interest Keywords */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 16 }}>
              Interest Keywords
            </h2>

            <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
              <input
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Add keyword..."
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
                style={{ flex: 1, padding: '10px 16px' }}
              />
              <button
                onClick={addKeyword}
                disabled={!newKeyword.trim()}
                className="flex items-center gap-2 rounded-xl bg-accent font-mono text-sm text-white hover:bg-accent-hover disabled:opacity-50"
                style={{ padding: '10px 16px' }}
              >
                <Plus size={15} /> Add
              </button>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {profile.interest_keywords.length === 0 ? (
                <p className="font-mono text-sm text-text-tertiary">No keywords yet. Add some to improve paper scoring.</p>
              ) : (
                profile.interest_keywords.map((kw) => (
                  <span
                    key={kw}
                    className="flex items-center rounded-full border border-border-default bg-bg-base font-mono text-xs text-text-secondary"
                    style={{ gap: 8, padding: '6px 14px' }}
                  >
                    {kw}
                    <button onClick={() => removeKeyword(kw)} className="text-text-tertiary hover:text-danger">
                      <X size={12} />
                    </button>
                  </span>
                ))
              )}
            </div>
          </section>

          {/* Preferences */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 20 }}>
              Preferences
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Email digest */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p className="font-mono text-sm text-text-primary">Email digest</p>
                  <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>Receive paper recommendations by email</p>
                </div>
                <button
                  onClick={() => updateProfile.mutate({ email_digest_enabled: !profile.email_digest_enabled })}
                  className={cn('transition', profile.email_digest_enabled ? 'text-success' : 'text-text-tertiary')}
                  style={{ fontSize: 28 }}
                >
                  {profile.email_digest_enabled ? '●' : '○'}
                </button>
              </div>

              {/* Digest frequency */}
              {profile.email_digest_enabled && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <p className="font-mono text-sm text-text-primary">Digest frequency</p>
                  <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                    {(['daily', 'weekly'] as const).map((freq) => (
                      <button
                        key={freq}
                        onClick={() => updateProfile.mutate({ digest_frequency: freq })}
                        className={cn(
                          'rounded-lg font-mono text-xs transition',
                          profile.digest_frequency === freq ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                        )}
                        style={{ padding: '6px 14px' }}
                      >
                        {freq}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Podcast voice */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <p className="font-mono text-sm text-text-primary">Default podcast voice</p>
                <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                  {(['single', 'dual'] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => updateProfile.mutate({ podcast_preference: mode })}
                      className={cn(
                        'rounded-lg font-mono text-xs transition',
                        profile.podcast_preference === mode ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                      )}
                      style={{ padding: '6px 14px' }}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* Interest Profile Chart */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 12 }}>
              Interest Profile
            </h2>
            <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20 }}>
              Built from your ratings — positive (green) means more relevant, negative (red) means less
            </p>
            <InterestChart vector={profile.interest_vector} />
          </section>

          {updateProfile.isPending && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '8px 0' }}>
              <Loader2 size={15} className="animate-spin text-accent" />
              <span className="font-mono text-xs text-text-secondary">Saving...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
