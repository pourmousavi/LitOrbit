import { useState, useEffect, type KeyboardEvent } from 'react';
import { Plus, X, Loader2, RotateCcw, Copy, Check, Rss } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useProfile, useUpdateProfile } from '@/hooks/useProfile';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

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
  const [scoringPrompt, setScoringPrompt] = useState('');
  const [promptDirty, setPromptDirty] = useState(false);
  const [singlePrompt, setSinglePrompt] = useState('');
  const [singlePromptDirty, setSinglePromptDirty] = useState(false);
  const [dualPrompt, setDualPrompt] = useState('');
  const [dualPromptDirty, setDualPromptDirty] = useState(false);
  const [feedTitle, setFeedTitle] = useState('');
  const [feedDescription, setFeedDescription] = useState('');
  const [feedAuthor, setFeedAuthor] = useState('');
  const [feedCoverUrl, setFeedCoverUrl] = useState('');
  const [feedDirty, setFeedDirty] = useState(false);
  const [feedCopied, setFeedCopied] = useState(false);

  const { data: voices } = useQuery<TTSVoice[]>({
    queryKey: ['tts-voices'],
    queryFn: async () => (await api.get('/api/v1/podcasts/voices')).data,
  });

  const defaultPrompt = `You are a research relevance scoring assistant. You will be given a paper's title, abstract, and keywords, along with a researcher's interest profile. Score the paper's relevance to this specific researcher on a scale of 0.0 to 10.0. Consider how well the paper's topic, methods, and findings align with the researcher's stated interests.

Return ONLY valid JSON in this exact format:
{"score": 7.5, "reasoning": "One sentence explanation of why this score was given."}`;

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
    if (profile) {
      setScoringPrompt(profile.scoring_prompt || defaultPrompt);
      setPromptDirty(false);
      setSinglePrompt(profile.single_voice_prompt || defaultSinglePrompt);
      setSinglePromptDirty(false);
      setDualPrompt(profile.dual_voice_prompt || defaultDualPrompt);
      setDualPromptDirty(false);
      setFeedTitle(profile.podcast_feed_title || '');
      setFeedDescription(profile.podcast_feed_description || '');
      setFeedAuthor(profile.podcast_feed_author || '');
      setFeedCoverUrl(profile.podcast_feed_cover_url || '');
      setFeedDirty(false);
    }
  }, [profile?.scoring_prompt, profile?.single_voice_prompt, profile?.dual_voice_prompt, profile?.podcast_feed_token]);

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
              Your personal research interests, sent to the AI when scoring papers for you. These shape your relevance scores — different users can have different keywords to get personalised rankings.
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

              {/* Digest podcast toggle */}
              {profile.email_digest_enabled && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <p className="font-mono text-sm text-text-primary">Digest podcast</p>
                    <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>Include an audio summary in your digest</p>
                  </div>
                  <button
                    onClick={() => updateProfile.mutate({ digest_podcast_enabled: !profile.digest_podcast_enabled })}
                    className={cn('transition', profile.digest_podcast_enabled ? 'text-success' : 'text-text-tertiary')}
                    style={{ fontSize: 28 }}
                  >
                    {profile.digest_podcast_enabled ? '●' : '○'}
                  </button>
                </div>
              )}

              {/* Digest podcast voice mode */}
              {profile.email_digest_enabled && profile.digest_podcast_enabled && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <p className="font-mono text-sm text-text-primary">Digest podcast voice</p>
                  <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
                    {(['single', 'dual'] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => updateProfile.mutate({ digest_podcast_voice_mode: mode })}
                        className={cn(
                          'rounded-lg font-mono text-xs transition',
                          profile.digest_podcast_voice_mode === mode ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                        )}
                        style={{ padding: '6px 14px' }}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Digest top papers count */}
              {profile.email_digest_enabled && profile.digest_podcast_enabled && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <p className="font-mono text-sm text-text-primary">Digest papers count</p>
                    <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
                      Papers covered in digest podcast ({profile.digest_frequency === 'daily' ? 'default 3' : 'default 10'})
                    </p>
                  </div>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={profile.digest_top_papers ?? (profile.digest_frequency === 'daily' ? 3 : 10)}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      if (val > 0 && val <= 20) updateProfile.mutate({ digest_top_papers: val });
                    }}
                    className="w-16 rounded-xl border border-border-default bg-bg-base text-center font-mono text-sm text-text-primary outline-none focus:border-accent"
                    style={{ padding: '6px 8px' }}
                  />
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

          {/* Podcast Feed */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 8 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Rss size={14} /> Podcast Feed
              </span>
            </h2>
            <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20, lineHeight: 1.6 }}>
              Expose your digest podcasts as an RSS feed. Add the feed URL to any podcast app
              (Pocket Casts, Overcast, AntennaPod, Apple Podcasts) and new episodes appear automatically.
              The feed is private — only accessible via this unique URL.
            </p>

            {/* Feed toggle */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <p className="font-mono text-sm text-text-primary">Enable podcast feed</p>
                <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>Generate an RSS feed URL for your digest podcasts</p>
              </div>
              <button
                onClick={() => updateProfile.mutate({ podcast_feed_enabled: !profile.podcast_feed_enabled })}
                className={cn('transition', profile.podcast_feed_enabled ? 'text-success' : 'text-text-tertiary')}
                style={{ fontSize: 28 }}
              >
                {profile.podcast_feed_enabled ? '●' : '○'}
              </button>
            </div>

            {profile.podcast_feed_enabled && profile.podcast_feed_token && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Feed URL */}
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Feed URL
                  </label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      readOnly
                      value={`${window.location.origin.replace('://app.', '://api.').replace(':5173', ':8000')}/api/v1/feed/${profile.podcast_feed_token}.xml`}
                      className="flex-1 rounded-xl border border-border-default bg-bg-base text-xs text-text-secondary outline-none font-mono"
                      style={{ padding: '10px 16px' }}
                      onFocus={(e) => e.target.select()}
                    />
                    <button
                      onClick={() => {
                        const url = `${window.location.origin.replace('://app.', '://api.').replace(':5173', ':8000')}/api/v1/feed/${profile.podcast_feed_token}.xml`;
                        navigator.clipboard.writeText(url);
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

                {/* Feed title */}
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Podcast name
                  </label>
                  <input
                    value={feedTitle}
                    onChange={(e) => { setFeedTitle(e.target.value); setFeedDirty(true); }}
                    placeholder={`LitOrbit Digest — ${profile.full_name}`}
                    className="w-full rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent font-mono"
                    style={{ padding: '10px 16px' }}
                  />
                </div>

                {/* Feed description */}
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Description
                  </label>
                  <textarea
                    value={feedDescription}
                    onChange={(e) => { setFeedDescription(e.target.value); setFeedDirty(true); }}
                    placeholder="AI-curated research digest podcasts powered by LitOrbit"
                    rows={2}
                    className="w-full rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent font-mono"
                    style={{ padding: '10px 16px', resize: 'vertical', lineHeight: 1.6 }}
                  />
                </div>

                {/* Feed author */}
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Author
                  </label>
                  <input
                    value={feedAuthor}
                    onChange={(e) => { setFeedAuthor(e.target.value); setFeedDirty(true); }}
                    placeholder={profile.full_name}
                    className="w-full rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent font-mono"
                    style={{ padding: '10px 16px' }}
                  />
                </div>

                {/* Cover art URL */}
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Cover art URL
                  </label>
                  <input
                    value={feedCoverUrl}
                    onChange={(e) => { setFeedCoverUrl(e.target.value); setFeedDirty(true); }}
                    placeholder="https://example.com/cover.png"
                    className="w-full rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent font-mono"
                    style={{ padding: '10px 16px' }}
                  />
                  <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginTop: 4 }}>
                    Square image, minimum 1400x1400px recommended. Leave empty for no cover art.
                  </p>
                </div>

                {/* Save button */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <button
                    onClick={() => {
                      updateProfile.mutate({
                        podcast_feed_title: feedTitle,
                        podcast_feed_description: feedDescription,
                        podcast_feed_author: feedAuthor,
                        podcast_feed_cover_url: feedCoverUrl,
                      });
                      setFeedDirty(false);
                    }}
                    disabled={!feedDirty || updateProfile.isPending}
                    className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                    style={{ padding: '10px 20px' }}
                  >
                    Save Feed Settings
                  </button>
                </div>
              </div>
            )}
          </section>

          {/* Scoring Prompt */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 8 }}>
              Scoring Prompt
            </h2>
            <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 16 }}>
              This prompt is sent to the AI when scoring papers for your relevance. Customise it to match your research focus.
            </p>
            <textarea
              value={scoringPrompt}
              onChange={(e) => { setScoringPrompt(e.target.value); setPromptDirty(true); }}
              rows={8}
              className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
              style={{ width: '100%', padding: '12px 16px', resize: 'vertical', lineHeight: 1.6, fontFamily: 'var(--font-mono)' }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
              <button
                onClick={() => {
                  updateProfile.mutate({ scoring_prompt: scoringPrompt });
                  setPromptDirty(false);
                }}
                disabled={!promptDirty || updateProfile.isPending}
                className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                style={{ padding: '10px 20px' }}
              >
                Save Prompt
              </button>
              <button
                onClick={() => { setScoringPrompt(defaultPrompt); setPromptDirty(true); }}
                className="flex items-center rounded-xl font-mono text-xs text-text-tertiary transition hover:text-text-secondary"
                style={{ gap: 6, padding: '10px 14px' }}
                title="Reset to default"
              >
                <RotateCcw size={13} /> Reset to default
              </button>
            </div>
          </section>

          {/* Podcast Settings */}
          <section className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 24 }}>
            <h2 className="font-mono text-xs font-medium tracking-widest text-text-tertiary uppercase" style={{ marginBottom: 8 }}>
              Podcast Settings
            </h2>
            <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20 }}>
              Customise the prompts and voices used when generating podcasts from papers.
            </p>

            {/* Voice selection */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
              {/* Single voice */}
              <div>
                <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                  Single voice
                </label>
                <select
                  value={profile.single_voice_id || 'en-AU-WilliamNeural'}
                  onChange={(e) => updateProfile.mutate({ single_voice_id: e.target.value })}
                  className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                  style={{ width: '100%', padding: '10px 16px' }}
                >
                  {voices?.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} — {v.gender}, {v.locale_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dual voices */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Dual voice — Alex (interviewer)
                  </label>
                  <select
                    value={profile.dual_voice_alex_id || 'en-US-AndrewNeural'}
                    onChange={(e) => updateProfile.mutate({ dual_voice_alex_id: e.target.value })}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                    style={{ width: '100%', padding: '10px 16px' }}
                  >
                    {voices?.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} — {v.gender}, {v.locale_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                    Dual voice — Sam (expert)
                  </label>
                  <select
                    value={profile.dual_voice_sam_id || 'en-GB-SoniaNeural'}
                    onChange={(e) => updateProfile.mutate({ dual_voice_sam_id: e.target.value })}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                    style={{ width: '100%', padding: '10px 16px' }}
                  >
                    {voices?.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} — {v.gender}, {v.locale_name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {/* Single voice prompt */}
            <div style={{ marginBottom: 24 }}>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                Single voice prompt
              </label>
              <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginBottom: 8 }}>
                Instructions for generating single-voice podcast scripts. Paper title and summary are appended automatically.
              </p>
              <textarea
                value={singlePrompt}
                onChange={(e) => { setSinglePrompt(e.target.value); setSinglePromptDirty(true); }}
                rows={6}
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '12px 16px', resize: 'vertical', lineHeight: 1.6, fontFamily: 'var(--font-mono)' }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
                <button
                  onClick={() => {
                    updateProfile.mutate({ single_voice_prompt: singlePrompt });
                    setSinglePromptDirty(false);
                  }}
                  disabled={!singlePromptDirty || updateProfile.isPending}
                  className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                  style={{ padding: '8px 16px' }}
                >
                  Save
                </button>
                <button
                  onClick={() => { setSinglePrompt(defaultSinglePrompt); setSinglePromptDirty(true); }}
                  className="flex items-center rounded-xl font-mono text-xs text-text-tertiary transition hover:text-text-secondary"
                  style={{ gap: 6, padding: '8px 12px' }}
                >
                  <RotateCcw size={13} /> Reset
                </button>
              </div>
            </div>

            {/* Dual voice prompt */}
            <div>
              <label className="font-mono text-xs font-medium text-text-secondary" style={{ marginBottom: 6, display: 'block' }}>
                Dual voice prompt
              </label>
              <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginBottom: 8 }}>
                Instructions for generating dual-voice (conversation) scripts. Use ALEX: and SAM: prefixes. Paper info is appended automatically.
              </p>
              <textarea
                value={dualPrompt}
                onChange={(e) => { setDualPrompt(e.target.value); setDualPromptDirty(true); }}
                rows={10}
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '12px 16px', resize: 'vertical', lineHeight: 1.6, fontFamily: 'var(--font-mono)' }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
                <button
                  onClick={() => {
                    updateProfile.mutate({ dual_voice_prompt: dualPrompt });
                    setDualPromptDirty(false);
                  }}
                  disabled={!dualPromptDirty || updateProfile.isPending}
                  className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                  style={{ padding: '8px 16px' }}
                >
                  Save
                </button>
                <button
                  onClick={() => { setDualPrompt(defaultDualPrompt); setDualPromptDirty(true); }}
                  className="flex items-center rounded-xl font-mono text-xs text-text-tertiary transition hover:text-text-secondary"
                  style={{ gap: 6, padding: '8px 12px' }}
                >
                  <RotateCcw size={13} /> Reset
                </button>
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
