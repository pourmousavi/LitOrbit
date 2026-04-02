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
      <p className="py-6 text-center font-mono text-sm text-text-tertiary">
        Rate papers to build your interest profile
      </p>
    );
  }

  const maxVal = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.1);

  return (
    <div className="space-y-2">
      {entries.map(([cat, weight]) => (
        <div key={cat} className="flex items-center gap-3">
          <span className="w-32 shrink-0 truncate text-right font-mono text-xs text-text-secondary">
            {cat}
          </span>
          <div className="flex h-4 flex-1 items-center">
            {weight >= 0 ? (
              <div
                className="h-full rounded-r bg-success/60"
                style={{ width: `${(weight / maxVal) * 100}%`, minWidth: weight > 0 ? '2px' : '0' }}
              />
            ) : (
              <div className="flex h-full w-full justify-end">
                <div
                  className="h-full rounded-l bg-danger/60"
                  style={{ width: `${(Math.abs(weight) / maxVal) * 100}%`, minWidth: '2px' }}
                />
              </div>
            )}
          </div>
          <span className={cn(
            'w-10 font-mono text-xs',
            weight >= 0 ? 'text-success' : 'text-danger',
          )}>
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
      <div className="mx-auto max-w-2xl p-4">
        <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Profile</h1>
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-border-default bg-bg-surface p-4">
              <div className="h-4 w-1/3 rounded bg-bg-elevated" />
              <div className="mt-3 h-8 w-full rounded bg-bg-elevated" />
            </div>
          ))}
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
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-6 font-mono text-lg font-medium text-text-primary">Profile</h1>

      <div className="space-y-6">
        {/* User info */}
        <section className="rounded-xl border border-border-default bg-bg-surface p-5">
          <h2 className="mb-3 font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">Account</h2>
          <p className="font-serif text-lg text-text-primary">{profile.full_name}</p>
          <p className="font-mono text-sm text-text-secondary">{profile.email}</p>
          <span className={cn(
            'mt-2 inline-block rounded-full px-2.5 py-0.5 font-mono text-xs',
            profile.role === 'admin' ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-secondary',
          )}>
            {profile.role}
          </span>
        </section>

        {/* Interest Keywords */}
        <section className="rounded-xl border border-border-default bg-bg-surface p-5">
          <h2 className="mb-3 font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">Interest Keywords</h2>

          <div className="mb-3 flex gap-2">
            <input
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Add keyword..."
              className="flex-1 rounded-lg border border-border-default bg-bg-base px-3 py-2 text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
            />
            <button
              onClick={addKeyword}
              disabled={!newKeyword.trim()}
              className="flex items-center gap-1 rounded-lg bg-accent px-3 py-2 font-mono text-sm text-white hover:bg-accent-hover disabled:opacity-50"
            >
              <Plus size={14} />
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {profile.interest_keywords.length === 0 ? (
              <p className="font-mono text-sm text-text-tertiary">No keywords yet. Add some to improve paper scoring.</p>
            ) : (
              profile.interest_keywords.map((kw) => (
                <span
                  key={kw}
                  className="flex items-center gap-1.5 rounded-full bg-bg-base px-3 py-1.5 font-mono text-xs text-text-secondary"
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
        <section className="rounded-xl border border-border-default bg-bg-surface p-5">
          <h2 className="mb-4 font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">Preferences</h2>

          <div className="space-y-4">
            {/* Email digest */}
            <div className="flex items-center justify-between">
              <div>
                <p className="font-mono text-sm text-text-primary">Email digest</p>
                <p className="font-mono text-xs text-text-tertiary">Receive paper recommendations by email</p>
              </div>
              <button
                onClick={() => updateProfile.mutate({ email_digest_enabled: !profile.email_digest_enabled })}
                className={cn('text-2xl transition', profile.email_digest_enabled ? 'text-success' : 'text-text-tertiary')}
              >
                {profile.email_digest_enabled ? '●' : '○'}
              </button>
            </div>

            {/* Digest frequency */}
            {profile.email_digest_enabled && (
              <div className="flex items-center justify-between">
                <p className="font-mono text-sm text-text-primary">Digest frequency</p>
                <div className="flex gap-1 rounded-lg bg-bg-base p-1">
                  {(['daily', 'weekly'] as const).map((freq) => (
                    <button
                      key={freq}
                      onClick={() => updateProfile.mutate({ digest_frequency: freq })}
                      className={cn(
                        'rounded-md px-3 py-1 font-mono text-xs transition',
                        profile.digest_frequency === freq ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                      )}
                    >
                      {freq}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Podcast voice */}
            <div className="flex items-center justify-between">
              <p className="font-mono text-sm text-text-primary">Default podcast voice</p>
              <div className="flex gap-1 rounded-lg bg-bg-base p-1">
                {(['single', 'dual'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => updateProfile.mutate({ podcast_preference: mode })}
                    className={cn(
                      'rounded-md px-3 py-1 font-mono text-xs transition',
                      profile.podcast_preference === mode ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                    )}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Interest Profile Chart */}
        <section className="rounded-xl border border-border-default bg-bg-surface p-5">
          <h2 className="mb-4 font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase">Interest Profile</h2>
          <p className="mb-4 font-mono text-xs text-text-tertiary">
            Built from your ratings — positive (green) means more relevant, negative (red) means less
          </p>
          <InterestChart vector={profile.interest_vector} />
        </section>

        {updateProfile.isPending && (
          <div className="flex items-center justify-center gap-2 py-2">
            <Loader2 size={14} className="animate-spin text-accent" />
            <span className="font-mono text-xs text-text-secondary">Saving...</span>
          </div>
        )}
      </div>
    </div>
  );
}
