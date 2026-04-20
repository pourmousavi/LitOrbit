import { useState, useEffect, useRef, type KeyboardEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, X, Loader2, RotateCcw, Copy, Check, Rss, User, Bell, Mic, Brain, BookOpen, Upload, Search, FileText, AlertCircle, BarChart3, Plug } from 'lucide-react';
import IntegrationsTab from '@/components/settings/IntegrationsTab';
import { useQuery } from '@tanstack/react-query';
import { useProfile, useUpdateProfile } from '@/hooks/useProfile';
import { usePulseSettings } from '@/stores/pulseSettingsStore';
import { useReferencePapers, useUploadReferencePaper, useAddReferencePaperByDOI, useAddReferencePaperManual, useDeleteReferencePaper } from '@/hooks/useReferencePapers';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

const API_BASE = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

type Tab = 'account' | 'references' | 'digest' | 'podcast' | 'scoring' | 'display' | 'integrations';

interface TTSVoice {
  id: string;
  name: string;
  gender: string;
  locale: string;
  locale_name: string;
}

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
          <span style={{ width: 90, flexShrink: 0, textAlign: 'right' }} className="truncate font-mono text-xs text-text-secondary">
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
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => {
    const t = searchParams.get('tab');
    if (t && ['account', 'references', 'digest', 'podcast', 'scoring', 'display', 'integrations'].includes(t)) {
      return t as Tab;
    }
    return 'account';
  });

  const tabs: { key: Tab; label: string; icon: typeof User }[] = [
    { key: 'account', label: 'Account', icon: User },
    { key: 'references', label: 'References', icon: BookOpen },
    { key: 'digest', label: 'Digest', icon: Bell },
    { key: 'podcast', label: 'Podcast', icon: Mic },
    { key: 'scoring', label: 'Scoring', icon: Brain },
    { key: 'display', label: 'Display', icon: BarChart3 },
    { key: 'integrations', label: 'Integrations', icon: Plug },
  ];

  if (isLoading || !profile) {
    return (
      <div className="px-4 pt-8 pb-4 md:px-8 md:pt-10 md:pb-8">
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-6">Settings</h1>
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

  return (
    <div className="px-4 pt-8 pb-4 md:px-8 md:pt-10 md:pb-8">
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-6">Settings</h1>

        {/* Tab bar */}
        <div
          className="rounded-2xl bg-bg-surface scrollbar-none"
          style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: 4, marginBottom: 24 }}
        >
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex items-center whitespace-nowrap rounded-xl font-mono text-sm transition',
                tab === t.key
                  ? 'bg-accent text-white'
                  : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
              )}
              style={{ gap: 6, padding: '8px 14px', flexShrink: 0 }}
            >
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'account' && <AccountTab />}
        {tab === 'references' && <ReferencePapersTab />}
        {tab === 'digest' && <DigestTab />}
        {tab === 'podcast' && <PodcastTab />}
        {tab === 'scoring' && <ScoringTab />}
        {tab === 'display' && <DisplayTab />}
        {tab === 'integrations' && <IntegrationsTab />}
      </div>
    </div>
  );
}


function AccountTab() {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();
  const [newKeyword, setNewKeyword] = useState('');

  if (!profile) return null;

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* User info */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 16 }}>
          Account
        </h2>
        <p className="font-sans text-text-primary" style={{ fontSize: 20 }}>{profile.full_name}</p>
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
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 8 }}>
          Interest Keywords
        </h2>
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 16, lineHeight: 1.6 }}>
          Your personal research interests. These do two things: (1) they're sent to the AI as context when it scores each paper for you, and (2) any paper whose title or abstract mentions one of these keywords is surfaced in your feed even if it didn't pass the embedding similarity filter from your reference papers — so add a keyword for any topic your reference set might miss.
        </p>

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

      {/* Interest Profile Chart */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 12 }}>
          Interest Profile
        </h2>
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20 }}>
          Built from your ratings — positive (green) means more relevant, negative (red) means less
        </p>
        <InterestChart vector={profile.category_weights} />
      </section>
    </div>
  );
}


function DigestTab() {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();
  const { data: limits } = useQuery<{ max_papers_per_digest: number; max_podcasts_per_user_per_month: number }>({
    queryKey: ['user-limits'],
    queryFn: async () => (await api.get('/api/v1/users/limits')).data,
  });
  const maxPapers = limits?.max_papers_per_digest ?? 20;
  const [form, setForm] = useState<{
    email_digest_enabled: boolean;
    digest_frequency: 'daily' | 'weekly';
    digest_day: string;
    digest_podcast_enabled: boolean;
    digest_podcast_voice_mode: 'single' | 'dual';
    digest_top_papers: number | null;
    podcast_digest_enabled: boolean;
    podcast_digest_frequency: 'daily' | 'weekly';
    podcast_digest_day: string;
    podcast_digest_top_papers: number | null;
    podcast_digest_voice_mode: 'single' | 'dual';
    digest_timezone: string;
  } | null>(null);

  useEffect(() => {
    if (profile && !form) {
      setForm({
        email_digest_enabled: profile.email_digest_enabled,
        digest_frequency: profile.digest_frequency,
        digest_day: profile.digest_day,
        digest_podcast_enabled: profile.digest_podcast_enabled,
        digest_podcast_voice_mode: profile.digest_podcast_voice_mode,
        digest_top_papers: profile.digest_top_papers,
        podcast_digest_enabled: profile.podcast_digest_enabled,
        podcast_digest_frequency: profile.podcast_digest_frequency,
        podcast_digest_day: profile.podcast_digest_day,
        podcast_digest_top_papers: profile.podcast_digest_top_papers,
        podcast_digest_voice_mode: profile.podcast_digest_voice_mode,
        digest_timezone: profile.digest_timezone || 'Australia/Adelaide',
      });
    }
  }, [profile]);

  if (!profile || !form) return null;

  const isDirty = (
    form.email_digest_enabled !== profile.email_digest_enabled ||
    form.digest_frequency !== profile.digest_frequency ||
    form.digest_day !== profile.digest_day ||
    form.digest_podcast_enabled !== profile.digest_podcast_enabled ||
    form.digest_podcast_voice_mode !== profile.digest_podcast_voice_mode ||
    form.digest_top_papers !== profile.digest_top_papers ||
    form.podcast_digest_enabled !== profile.podcast_digest_enabled ||
    form.podcast_digest_frequency !== profile.podcast_digest_frequency ||
    form.podcast_digest_day !== profile.podcast_digest_day ||
    form.podcast_digest_top_papers !== profile.podcast_digest_top_papers ||
    form.podcast_digest_voice_mode !== profile.podcast_digest_voice_mode ||
    form.digest_timezone !== (profile.digest_timezone || 'Australia/Adelaide')
  );

  const handleSave = () => {
    updateProfile.mutate(form);
  };

  const handleCancel = () => {
    setForm({
      email_digest_enabled: profile.email_digest_enabled,
      digest_frequency: profile.digest_frequency,
      digest_day: profile.digest_day,
      digest_podcast_enabled: profile.digest_podcast_enabled,
      digest_podcast_voice_mode: profile.digest_podcast_voice_mode,
      digest_top_papers: profile.digest_top_papers,
      podcast_digest_enabled: profile.podcast_digest_enabled,
      podcast_digest_frequency: profile.podcast_digest_frequency,
      podcast_digest_day: profile.podcast_digest_day,
      podcast_digest_top_papers: profile.podcast_digest_top_papers,
      podcast_digest_voice_mode: profile.podcast_digest_voice_mode,
      digest_timezone: profile.digest_timezone || 'Australia/Adelaide',
    });
  };

  const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];

  const timezones = [
    'Australia/Adelaide', 'Australia/Sydney', 'Australia/Melbourne', 'Australia/Brisbane',
    'Australia/Perth', 'Australia/Darwin', 'Australia/Hobart',
    'Pacific/Auckland', 'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Singapore',
    'Asia/Kolkata', 'Europe/London', 'Europe/Berlin', 'Europe/Paris',
    'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
    'UTC',
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* ── Timezone ── */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 20 }}>
          Timezone
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <p className="font-mono text-sm text-text-primary">Your timezone</p>
            <p className="font-mono text-xs text-text-tertiary">Used for digest day-of-week scheduling</p>
          </div>
          <select
            value={form.digest_timezone}
            onChange={(e) => setForm({ ...form, digest_timezone: e.target.value })}
            className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent font-mono"
            style={{ padding: '6px 14px' }}
          >
            {timezones.map((tz) => (
              <option key={tz} value={tz}>{tz.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
      </section>

      {/* ── Email Digest ── */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 20 }}>
          Email Digest
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p className="font-mono text-sm text-text-primary">Email digest</p>
              <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
                Delivers to <span className="text-text-secondary">{profile.email}</span>
              </p>
            </div>
            <button
              onClick={() => setForm({ ...form, email_digest_enabled: !form.email_digest_enabled })}
              className={cn('transition', form.email_digest_enabled ? 'text-success' : 'text-text-tertiary')}
              style={{ fontSize: 28 }}
            >
              {form.email_digest_enabled ? '●' : '○'}
            </button>
          </div>

          {form.email_digest_enabled && (
            <>
              {/* Frequency */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <p className="font-mono text-sm text-text-primary">Frequency</p>
                <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                  {(['daily', 'weekly'] as const).map((freq) => (
                    <button
                      key={freq}
                      onClick={() => setForm({ ...form, digest_frequency: freq })}
                      className={cn(
                        'rounded-lg font-mono text-xs transition',
                        form.digest_frequency === freq ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                      )}
                      style={{ padding: '6px 14px' }}
                    >
                      {freq}
                    </button>
                  ))}
                </div>
              </div>

              {form.digest_frequency === 'weekly' && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <p className="font-mono text-sm text-text-primary">Day</p>
                  <select
                    value={form.digest_day || 'monday'}
                    onChange={(e) => setForm({ ...form, digest_day: e.target.value })}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent font-mono"
                    style={{ padding: '6px 14px' }}
                  >
                    {days.map((day) => (
                      <option key={day} value={day}>{day.charAt(0).toUpperCase() + day.slice(1)}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Papers count */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p className="font-mono text-sm text-text-primary">Papers count</p>
                  <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
                    Max papers per digest (limit {maxPapers})
                  </p>
                </div>
                <input
                  type="number"
                  min={1}
                  max={maxPapers}
                  value={Math.min(form.digest_top_papers ?? (form.digest_frequency === 'daily' ? 3 : maxPapers), maxPapers)}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    setForm({ ...form, digest_top_papers: v ? Math.min(v, maxPapers) : null });
                  }}
                  className="w-16 rounded-xl border border-border-default bg-bg-base text-center font-mono text-sm text-text-primary outline-none focus:border-accent"
                  style={{ padding: '6px 8px' }}
                />
              </div>

              <div className="border-t border-border-default" />

              {/* Include podcast in email */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p className="font-mono text-sm text-text-primary">Include podcast</p>
                  <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
                    Attach an audio summary to the {form.digest_frequency} email
                  </p>
                </div>
                <button
                  onClick={() => setForm({ ...form, digest_podcast_enabled: !form.digest_podcast_enabled })}
                  className={cn('transition', form.digest_podcast_enabled ? 'text-success' : 'text-text-tertiary')}
                  style={{ fontSize: 28 }}
                >
                  {form.digest_podcast_enabled ? '●' : '○'}
                </button>
              </div>

              {form.digest_podcast_enabled && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <p className="font-mono text-sm text-text-primary">Voice mode</p>
                  <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                    {(['single', 'dual'] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setForm({ ...form, digest_podcast_voice_mode: mode })}
                        className={cn(
                          'rounded-lg font-mono text-xs transition',
                          form.digest_podcast_voice_mode === mode ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                        )}
                        style={{ padding: '6px 14px' }}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* ── Podcast Digest ── */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 20 }}>
          Podcast Digest
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p className="font-mono text-sm text-text-primary">Podcast digest</p>
              <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>Standalone podcast in your Podcasts library</p>
            </div>
            <button
              onClick={() => setForm({ ...form, podcast_digest_enabled: !form.podcast_digest_enabled })}
              className={cn('transition', form.podcast_digest_enabled ? 'text-success' : 'text-text-tertiary')}
              style={{ fontSize: 28 }}
            >
              {form.podcast_digest_enabled ? '●' : '○'}
            </button>
          </div>

          {form.podcast_digest_enabled && (
            <>
              {/* Frequency */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <p className="font-mono text-sm text-text-primary">Frequency</p>
                <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                  {(['daily', 'weekly'] as const).map((freq) => (
                    <button
                      key={freq}
                      onClick={() => setForm({ ...form, podcast_digest_frequency: freq })}
                      className={cn(
                        'rounded-lg font-mono text-xs transition',
                        form.podcast_digest_frequency === freq ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                      )}
                      style={{ padding: '6px 14px' }}
                    >
                      {freq}
                    </button>
                  ))}
                </div>
              </div>

              {form.podcast_digest_frequency === 'weekly' && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <p className="font-mono text-sm text-text-primary">Day</p>
                  <select
                    value={form.podcast_digest_day || 'monday'}
                    onChange={(e) => setForm({ ...form, podcast_digest_day: e.target.value })}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent font-mono"
                    style={{ padding: '6px 14px' }}
                  >
                    {days.map((day) => (
                      <option key={day} value={day}>{day.charAt(0).toUpperCase() + day.slice(1)}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Papers count */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p className="font-mono text-sm text-text-primary">Papers count</p>
                  <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
                    Max papers per digest (limit {maxPapers})
                  </p>
                </div>
                <input
                  type="number"
                  min={1}
                  max={maxPapers}
                  value={Math.min(form.podcast_digest_top_papers ?? (form.podcast_digest_frequency === 'daily' ? 3 : maxPapers), maxPapers)}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    setForm({ ...form, podcast_digest_top_papers: v ? Math.min(v, maxPapers) : null });
                  }}
                  className="w-16 rounded-xl border border-border-default bg-bg-base text-center font-mono text-sm text-text-primary outline-none focus:border-accent"
                  style={{ padding: '6px 8px' }}
                />
              </div>

              {/* Voice mode */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <p className="font-mono text-sm text-text-primary">Voice mode</p>
                <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                  {(['single', 'dual'] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setForm({ ...form, podcast_digest_voice_mode: mode })}
                      className={cn(
                        'rounded-lg font-mono text-xs transition',
                        form.podcast_digest_voice_mode === mode ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                      )}
                      style={{ padding: '6px 14px' }}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      {/* Save/Cancel */}
      {isDirty && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={handleSave}
            disabled={updateProfile.isPending}
            className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            style={{ gap: 8, padding: '14px 24px' }}
          >
            {updateProfile.isPending ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
            Save Changes
          </button>
          <button
            onClick={handleCancel}
            className="rounded-2xl font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ padding: '14px 24px' }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}


function PodcastTab() {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();
  const [feedCopied, setFeedCopied] = useState(false);

  const [form, setForm] = useState<{
    podcast_preference: 'single' | 'dual';
    single_voice_id: string;
    dual_voice_alex_id: string;
    dual_voice_sam_id: string;
    single_voice_prompt: string;
    dual_voice_prompt: string;
    podcast_feed_enabled: boolean;
    podcast_feed_title: string;
    podcast_feed_description: string;
    podcast_feed_author: string;
    podcast_feed_cover_url: string;
  } | null>(null);

  const { data: voices } = useQuery<TTSVoice[]>({
    queryKey: ['tts-voices'],
    queryFn: async () => (await api.get('/api/v1/podcasts/voices')).data,
  });

  const defaultSinglePrompt = `Write a 3-4 minute spoken summary of this research paper in a clear, engaging academic podcast style. The listener is a researcher in energy systems. Avoid jargon without explanation. Cover: what problem it solves, how they solved it, what they found, and why it matters. Do not include music cues or sound effects. Write only the spoken words.`;

  const defaultDualPrompt = `Write a conversational podcast script between two hosts discussing this research paper.

Host A (Alex) is the curious interviewer — sets context, asks sharp follow-up questions, plays devil's advocate.
Host B (Sam) is the domain expert — explains methodology, results, and implications clearly and enthusiastically.

Rules:
- Write natural conversational dialogue with contractions and reactions.
- Each turn should be 2-4 sentences. Avoid monologues.
- Never use filler, sound effects, or stage directions.
- Target 5-6 minutes of spoken content.

Format each line exactly as:
ALEX: <dialogue>
SAM: <dialogue>`;

  useEffect(() => {
    if (profile && !form) {
      setForm({
        podcast_preference: profile.podcast_preference,
        single_voice_id: profile.single_voice_id || 'en-AU-WilliamNeural',
        dual_voice_alex_id: profile.dual_voice_alex_id || 'en-US-AndrewNeural',
        dual_voice_sam_id: profile.dual_voice_sam_id || 'en-GB-SoniaNeural',
        single_voice_prompt: profile.single_voice_prompt || defaultSinglePrompt,
        dual_voice_prompt: profile.dual_voice_prompt || defaultDualPrompt,
        podcast_feed_enabled: profile.podcast_feed_enabled,
        podcast_feed_title: profile.podcast_feed_title || '',
        podcast_feed_description: profile.podcast_feed_description || '',
        podcast_feed_author: profile.podcast_feed_author || '',
        podcast_feed_cover_url: profile.podcast_feed_cover_url || '',
      });
    }
  }, [profile]);

  if (!profile || !form) return null;

  const isDirty = (
    form.podcast_preference !== profile.podcast_preference ||
    form.single_voice_id !== (profile.single_voice_id || 'en-AU-WilliamNeural') ||
    form.dual_voice_alex_id !== (profile.dual_voice_alex_id || 'en-US-AndrewNeural') ||
    form.dual_voice_sam_id !== (profile.dual_voice_sam_id || 'en-GB-SoniaNeural') ||
    form.single_voice_prompt !== (profile.single_voice_prompt || defaultSinglePrompt) ||
    form.dual_voice_prompt !== (profile.dual_voice_prompt || defaultDualPrompt) ||
    form.podcast_feed_enabled !== profile.podcast_feed_enabled ||
    form.podcast_feed_title !== (profile.podcast_feed_title || '') ||
    form.podcast_feed_description !== (profile.podcast_feed_description || '') ||
    form.podcast_feed_author !== (profile.podcast_feed_author || '') ||
    form.podcast_feed_cover_url !== (profile.podcast_feed_cover_url || '')
  );

  const handleSave = () => {
    updateProfile.mutate(form);
  };

  const handleCancel = () => {
    setForm({
      podcast_preference: profile.podcast_preference,
      single_voice_id: profile.single_voice_id || 'en-AU-WilliamNeural',
      dual_voice_alex_id: profile.dual_voice_alex_id || 'en-US-AndrewNeural',
      dual_voice_sam_id: profile.dual_voice_sam_id || 'en-GB-SoniaNeural',
      single_voice_prompt: profile.single_voice_prompt || defaultSinglePrompt,
      dual_voice_prompt: profile.dual_voice_prompt || defaultDualPrompt,
      podcast_feed_enabled: profile.podcast_feed_enabled,
      podcast_feed_title: profile.podcast_feed_title || '',
      podcast_feed_description: profile.podcast_feed_description || '',
      podcast_feed_author: profile.podcast_feed_author || '',
      podcast_feed_cover_url: profile.podcast_feed_cover_url || '',
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Voice preferences */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 20 }}>
          Voice Settings
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Default mode */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <p className="font-mono text-sm text-text-primary">Default voice mode</p>
            <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
              {(['single', 'dual'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setForm({ ...form, podcast_preference: mode })}
                  className={cn(
                    'rounded-lg font-mono text-xs transition',
                    form.podcast_preference === mode ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                  )}
                  style={{ padding: '6px 14px' }}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* Single voice */}
          <div>
            <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>Single voice</label>
            <select
              value={form.single_voice_id}
              onChange={(e) => setForm({ ...form, single_voice_id: e.target.value })}
              className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
              style={{ width: '100%', padding: '10px 16px' }}
            >
              {voices?.map((v) => (
                <option key={v.id} value={v.id}>{v.name} — {v.gender}, {v.locale_name}</option>
              ))}
            </select>
          </div>

          {/* Dual voices */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>Alex (interviewer)</label>
              <select
                value={form.dual_voice_alex_id}
                onChange={(e) => setForm({ ...form, dual_voice_alex_id: e.target.value })}
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              >
                {voices?.map((v) => (
                  <option key={v.id} value={v.id}>{v.name} — {v.gender}, {v.locale_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>Sam (expert)</label>
              <select
                value={form.dual_voice_sam_id}
                onChange={(e) => setForm({ ...form, dual_voice_sam_id: e.target.value })}
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              >
                {voices?.map((v) => (
                  <option key={v.id} value={v.id}>{v.name} — {v.gender}, {v.locale_name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </section>

      {/* Prompts */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 20 }}>
          Script Prompts
        </h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <label className="font-mono text-xs font-medium text-text-secondary">Single voice prompt</label>
              <button
                onClick={() => setForm({ ...form, single_voice_prompt: defaultSinglePrompt })}
                className="flex items-center font-mono text-xs text-text-tertiary hover:text-text-secondary"
                style={{ gap: 4 }}
              >
                <RotateCcw size={11} /> Reset
              </button>
            </div>
            <textarea
              value={form.single_voice_prompt}
              onChange={(e) => setForm({ ...form, single_voice_prompt: e.target.value })}
              rows={5}
              className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
              style={{ width: '100%', padding: '12px 16px', resize: 'vertical', lineHeight: 1.6, fontFamily: 'var(--font-mono)' }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <label className="font-mono text-xs font-medium text-text-secondary">Dual voice prompt</label>
              <button
                onClick={() => setForm({ ...form, dual_voice_prompt: defaultDualPrompt })}
                className="flex items-center font-mono text-xs text-text-tertiary hover:text-text-secondary"
                style={{ gap: 4 }}
              >
                <RotateCcw size={11} /> Reset
              </button>
            </div>
            <textarea
              value={form.dual_voice_prompt}
              onChange={(e) => setForm({ ...form, dual_voice_prompt: e.target.value })}
              rows={8}
              className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
              style={{ width: '100%', padding: '12px 16px', resize: 'vertical', lineHeight: 1.6, fontFamily: 'var(--font-mono)' }}
            />
          </div>
        </div>
      </section>

      {/* Podcast Feed */}
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 8 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Rss size={14} /> Podcast Feed
          </span>
        </h2>
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20, lineHeight: 1.6 }}>
          Expose your digest podcasts as an RSS feed. Add the URL to any podcast app.
        </p>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <p className="font-mono text-sm text-text-primary">Enable podcast feed</p>
          <button
            onClick={() => setForm({ ...form, podcast_feed_enabled: !form.podcast_feed_enabled })}
            className={cn('transition', form.podcast_feed_enabled ? 'text-success' : 'text-text-tertiary')}
            style={{ fontSize: 28 }}
          >
            {form.podcast_feed_enabled ? '●' : '○'}
          </button>
        </div>

        {form.podcast_feed_enabled && profile.podcast_feed_token && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>Feed URL</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  readOnly
                  value={`${API_BASE}/api/v1/feed/${profile.podcast_feed_token}.xml`}
                  className="flex-1 rounded-xl border border-border-default bg-bg-base text-xs text-text-secondary outline-none font-mono"
                  style={{ padding: '10px 16px' }}
                  onFocus={(e) => e.target.select()}
                />
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(`${API_BASE}/api/v1/feed/${profile.podcast_feed_token}.xml`);
                    setFeedCopied(true);
                    setTimeout(() => setFeedCopied(false), 2000);
                  }}
                  className="flex items-center gap-2 rounded-xl bg-accent font-mono text-xs text-white hover:bg-accent-hover"
                  style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}
                >
                  {feedCopied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}
                </button>
              </div>
            </div>
            <div>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>Podcast name</label>
              <input
                value={form.podcast_feed_title}
                onChange={(e) => setForm({ ...form, podcast_feed_title: e.target.value })}
                placeholder={`LitOrbit Digest — ${profile.full_name}`}
                className="w-full rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent font-mono"
                style={{ padding: '10px 16px' }}
              />
            </div>
            <div>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>Author</label>
              <input
                value={form.podcast_feed_author}
                onChange={(e) => setForm({ ...form, podcast_feed_author: e.target.value })}
                placeholder={profile.full_name}
                className="w-full rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent font-mono"
                style={{ padding: '10px 16px' }}
              />
            </div>
          </div>
        )}
      </section>

      {/* Save/Cancel */}
      {isDirty && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={handleSave}
            disabled={updateProfile.isPending}
            className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            style={{ gap: 8, padding: '14px 24px' }}
          >
            {updateProfile.isPending ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
            Save Changes
          </button>
          <button
            onClick={handleCancel}
            className="rounded-2xl font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ padding: '14px 24px' }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}


function ScoringTab() {
  const { data: profile } = useProfile();
  const updateProfile = useUpdateProfile();

  const defaultPrompt = `You are a research relevance scoring assistant. You will be given a paper's title, abstract, and keywords, along with a researcher's interest profile. Score the paper's relevance to this specific researcher on a scale of 0.0 to 10.0. Consider how well the paper's topic, methods, and findings align with the researcher's stated interests.

Return ONLY valid JSON in this exact format:
{"score": 7.5, "reasoning": "One sentence explanation of why this score was given."}`;

  const [prompt, setPrompt] = useState('');

  useEffect(() => {
    if (profile) {
      setPrompt(profile.scoring_prompt || defaultPrompt);
    }
  }, [profile?.scoring_prompt]);

  if (!profile) return null;

  const isDirty = prompt !== (profile.scoring_prompt || defaultPrompt);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 8 }}>
          Scoring Prompt
        </h2>
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 16, lineHeight: 1.6 }}>
          This prompt is sent to the AI when scoring papers for your relevance. Customise it to match your research focus.
        </p>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={8}
          className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
          style={{ width: '100%', padding: '12px 16px', resize: 'vertical', lineHeight: 1.6, fontFamily: 'var(--font-mono)' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
          <button
            onClick={() => setPrompt(defaultPrompt)}
            className="flex items-center rounded-xl font-mono text-xs text-text-tertiary transition hover:text-text-secondary"
            style={{ gap: 6, padding: '10px 14px' }}
          >
            <RotateCcw size={13} /> Reset to default
          </button>
        </div>
      </section>

      {/* Save/Cancel */}
      {isDirty && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={() => { updateProfile.mutate({ scoring_prompt: prompt }); }}
            disabled={updateProfile.isPending}
            className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            style={{ gap: 8, padding: '14px 24px' }}
          >
            {updateProfile.isPending ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
            Save Changes
          </button>
          <button
            onClick={() => setPrompt(profile.scoring_prompt || defaultPrompt)}
            className="rounded-2xl font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ padding: '14px 24px' }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}


function ReferencePapersTab() {
  const { data: papers, isLoading } = useReferencePapers();
  const uploadMutation = useUploadReferencePaper();
  const doiMutation = useAddReferencePaperByDOI();
  const manualMutation = useAddReferencePaperManual();
  const deleteMutation = useDeleteReferencePaper();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<'idle' | 'doi' | 'manual'>('idle');
  const [doi, setDoi] = useState('');
  const [manualTitle, setManualTitle] = useState('');
  const [manualAbstract, setManualAbstract] = useState('');

  const count = papers?.length ?? 0;
  const MAX = 20;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const nonPdf = files.filter((f) => !f.name.toLowerCase().endsWith('.pdf'));
    if (nonPdf.length) {
      alert('Only PDF files are accepted.');
      e.target.value = '';
      return;
    }
    if (count + files.length > MAX) {
      alert(`You can only add ${MAX - count} more paper${MAX - count === 1 ? '' : 's'} (limit is ${MAX}).`);
      e.target.value = '';
      return;
    }
    files.forEach((file) => uploadMutation.mutate(file));
    e.target.value = '';
  };

  const handleDoiSubmit = () => {
    const d = doi.trim();
    if (!d) return;
    doiMutation.mutate(d, { onSuccess: () => { setDoi(''); setMode('idle'); } });
  };

  const handleManualSubmit = () => {
    const t = manualTitle.trim();
    if (!t) return;
    manualMutation.mutate(
      { title: t, abstract: manualAbstract.trim() || undefined },
      { onSuccess: () => { setManualTitle(''); setManualAbstract(''); setMode('idle'); } },
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <h2 className="font-mono text-sm font-semibold text-text-primary">
            Reference Papers ({count}/{MAX})
          </h2>
        </div>
        <p className="text-xs text-text-secondary" style={{ lineHeight: 1.6 }}>
          Upload papers that represent your research interests. These are used to find semantically
          similar new papers in your feed, replacing simple keyword matching with intelligent
          relevance scoring.
        </p>
      </div>

      {/* Add paper actions */}
      {count < MAX && (
        <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
          <h3 className="font-mono text-xs font-semibold text-text-secondary" style={{ marginBottom: 16 }}>
            Add Reference Paper
          </h3>

          {mode === 'idle' && (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadMutation.isPending}
                className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-primary hover:border-accent transition"
                style={{ gap: 8, padding: '10px 18px' }}
              >
                {uploadMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                {uploadMutation.isPending ? 'Uploading...' : 'Upload PDF'}
              </button>
              <button
                onClick={() => setMode('doi')}
                className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-primary hover:border-accent transition"
                style={{ gap: 8, padding: '10px 18px' }}
              >
                <Search size={14} /> Lookup by DOI
              </button>
              <button
                onClick={() => setMode('manual')}
                className="flex items-center rounded-xl border border-border-default bg-bg-elevated font-mono text-sm text-text-primary hover:border-accent transition"
                style={{ gap: 8, padding: '10px 18px' }}
              >
                <FileText size={14} /> Enter Manually
              </button>
              <input ref={fileInputRef} type="file" accept=".pdf" multiple className="hidden" onChange={handleFileChange} />
            </div>
          )}

          {mode === 'doi' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <input
                  type="text"
                  value={doi}
                  onChange={(e) => setDoi(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleDoiSubmit()}
                  placeholder="e.g. 10.1016/j.apenergy.2024.123456"
                  className="rounded-xl border border-border-default bg-bg-base font-mono text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent outline-none"
                  style={{ flex: 1, padding: '10px 16px' }}
                />
                <button
                  onClick={handleDoiSubmit}
                  disabled={!doi.trim() || doiMutation.isPending}
                  className="flex items-center gap-2 rounded-xl bg-accent font-mono text-sm text-white hover:bg-accent-hover disabled:opacity-50"
                  style={{ padding: '10px 16px' }}
                >
                  {doiMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                  {doiMutation.isPending ? 'Looking up...' : 'Fetch'}
                </button>
                <button
                  onClick={() => { setMode('idle'); setDoi(''); }}
                  className="rounded-xl font-mono text-sm text-text-secondary hover:text-text-primary"
                  style={{ padding: '10px 16px' }}
                >
                  Cancel
                </button>
              </div>
              {doiMutation.isError && (
                <p className="text-xs text-danger">
                  {(doiMutation.error as any)?.response?.data?.detail || 'DOI lookup failed'}
                </p>
              )}
            </div>
          )}

          {mode === 'manual' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <input
                  type="text"
                  value={manualTitle}
                  onChange={(e) => setManualTitle(e.target.value)}
                  placeholder="Paper title"
                  className="rounded-xl border border-border-default bg-bg-base font-mono text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent outline-none"
                  style={{ flex: 1, padding: '10px 16px' }}
                />
                <button
                  onClick={handleManualSubmit}
                  disabled={!manualTitle.trim() || manualMutation.isPending}
                  className="flex items-center gap-2 rounded-xl bg-accent font-mono text-sm text-white hover:bg-accent-hover disabled:opacity-50"
                  style={{ padding: '10px 16px' }}
                >
                  {manualMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                  {manualMutation.isPending ? 'Adding...' : 'Add Paper'}
                </button>
                <button
                  onClick={() => { setMode('idle'); setManualTitle(''); setManualAbstract(''); }}
                  className="rounded-xl font-mono text-sm text-text-secondary hover:text-text-primary"
                  style={{ padding: '10px 16px' }}
                >
                  Cancel
                </button>
              </div>
              <textarea
                value={manualAbstract}
                onChange={(e) => setManualAbstract(e.target.value)}
                placeholder="Abstract (optional but recommended for better matching)"
                rows={4}
                className="rounded-xl border border-border-default bg-bg-base font-mono text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent outline-none resize-none"
                style={{ padding: '10px 16px' }}
              />
              {manualMutation.isError && (
                <p className="text-xs text-danger">
                  {(manualMutation.error as any)?.response?.data?.detail || 'Failed to add paper'}
                </p>
              )}
            </div>
          )}

          {uploadMutation.isError && (
            <p className="text-xs text-danger" style={{ marginTop: 12 }}>
              {(uploadMutation.error as any)?.response?.data?.detail || 'Upload failed'}
            </p>
          )}
        </div>
      )}

      {/* Paper list */}
      {isLoading ? (
        <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="animate-pulse" style={{ marginBottom: 16 }}>
              <div className="h-4 w-2/3 rounded bg-bg-elevated" />
              <div className="mt-2 h-3 w-full rounded bg-bg-elevated" />
            </div>
          ))}
        </div>
      ) : papers && papers.length > 0 ? (
        <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {papers.map((paper) => (
              <div
                key={paper.id}
                className="rounded-xl border border-border-default bg-bg-base"
                style={{ padding: '14px 18px' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="font-sans font-semibold text-sm text-text-primary" style={{ lineHeight: 1.4 }}>
                      {paper.title}
                    </div>
                    {paper.abstract_preview && (
                      <p className="text-xs text-text-tertiary" style={{ marginTop: 6, lineHeight: 1.5 }}>
                        {paper.abstract_preview}...
                      </p>
                    )}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                      <span className="rounded-md bg-bg-elevated px-2 py-0.5 font-mono text-[10px] text-text-tertiary">
                        {paper.source === 'pdf_upload' ? 'PDF' : paper.source === 'doi_lookup' ? 'DOI' : 'Manual'}
                      </span>
                      {paper.doi && (
                        <span className="font-mono text-[10px] text-text-tertiary">{paper.doi}</span>
                      )}
                      {!paper.has_embedding && (
                        <span className="flex items-center text-[10px] text-warning font-mono" style={{ gap: 3 }}>
                          <AlertCircle size={10} /> Embedding pending
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      if (confirm('Remove this reference paper?')) {
                        deleteMutation.mutate(paper.id);
                      }
                    }}
                    disabled={deleteMutation.isPending}
                    className="text-text-tertiary hover:text-danger transition"
                    style={{ padding: 4, flexShrink: 0 }}
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div
          className="rounded-2xl border border-border-default bg-bg-surface"
          style={{ padding: '40px 24px', textAlign: 'center' }}
        >
          <BookOpen size={32} className="text-text-tertiary" style={{ margin: '0 auto 12px' }} />
          <p className="font-mono text-sm text-text-secondary">No reference papers yet</p>
          <p className="text-xs text-text-tertiary" style={{ marginTop: 4 }}>
            Add papers to improve how we find relevant research for you
          </p>
        </div>
      )}
    </div>
  );
}


function DisplayTab() {
  const settings = usePulseSettings();
  const [draft, setDraft] = useState({
    showPulseCard: settings.showPulseCard,
    showNavBadge: settings.showNavBadge,
    showSidebarStat: settings.showSidebarStat,
    showWeeklyToast: settings.showWeeklyToast,
  });
  const hasChanges =
    draft.showPulseCard !== settings.showPulseCard ||
    draft.showNavBadge !== settings.showNavBadge ||
    draft.showSidebarStat !== settings.showSidebarStat ||
    draft.showWeeklyToast !== settings.showWeeklyToast;

  const handleSave = () => {
    settings.saveAll(draft);
  };

  const handleCancel = () => {
    setDraft({
      showPulseCard: settings.showPulseCard,
      showNavBadge: settings.showNavBadge,
      showSidebarStat: settings.showSidebarStat,
      showWeeklyToast: settings.showWeeklyToast,
    });
  };

  const toggles: { key: keyof typeof draft; label: string; description: string }[] = [
    { key: 'showPulseCard', label: 'Research Pulse card', description: 'Stats card at the top of the Feed page showing your weekly progress and lab leaderboard' },
    { key: 'showNavBadge', label: 'Unreviewed papers badge', description: 'Count badge on the Feed navigation item showing how many papers you haven\'t rated' },
    { key: 'showSidebarStat', label: 'Sidebar status line', description: 'Streak or review status text below the LitOrbit logo in the sidebar' },
    { key: 'showWeeklyToast', label: 'Weekly summary notification', description: 'Toast notification on first visit each week summarizing your previous week\'s activity' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
        <h2 className="font-mono text-sm font-medium text-text-primary" style={{ marginBottom: 4 }}>
          Research Pulse
        </h2>
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20 }}>
          Control which engagement elements are visible across the app
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {toggles.map((t) => (
            <label
              key={t.key}
              style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer' }}
            >
              <input
                type="checkbox"
                checked={draft[t.key]}
                onChange={(e) => setDraft((prev) => ({ ...prev, [t.key]: e.target.checked }))}
                className="mt-0.5 accent-accent"
                style={{ width: 16, height: 16, flexShrink: 0 }}
              />
              <div>
                <span className="font-mono text-sm text-text-primary">{t.label}</span>
                <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
                  {t.description}
                </p>
              </div>
            </label>
          ))}
        </div>

      </div>

      {/* Save/Cancel */}
      {hasChanges && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={handleSave}
            className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
            style={{ gap: 8, padding: '14px 24px' }}
          >
            <Check size={16} />
            Save Changes
          </button>
          <button
            onClick={handleCancel}
            className="rounded-2xl font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ padding: '14px 24px' }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
