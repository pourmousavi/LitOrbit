import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Settings, Users, Activity, Tags, ToggleLeft, ToggleRight, Play, Loader2, Plus, X, Trash2, ChevronDown, HardDrive, Mail, UserPlus, Pencil, Check, Sliders, AlertTriangle, Info, BookOpen } from 'lucide-react';
import api from '@/lib/api';
import { cn, formatDate } from '@/lib/utils';

type Tab = 'journals' | 'users' | 'pipeline' | 'keywords' | 'digest' | 'settings';

interface Journal {
  id: string;
  name: string;
  publisher: string;
  source_type: string;
  source_identifier: string;
  is_active: boolean;
}

interface PipelineRun {
  id: string;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  papers_discovered: number;
  papers_filtered: number;
  papers_processed: number;
  error_message: string | null;
  run_log: Record<string, unknown>[];
}

interface UserItem {
  id: string;
  full_name: string;
  role: string;
  email: string;
  invited_at: string | null;
  accepted_at: string | null;
  last_login_at: string | null;
  login_count: number;
  ratings_count: number;
  podcasts_generated: number;
  podcasts_listened: number;
  collections_count: number;
  shares_sent: number;
  digests_received: number;
  last_active: string | null;
}

interface SystemSettingsData {
  max_podcasts_per_user_per_month: number;
  digest_podcast_enabled_global: boolean;
  max_papers_per_digest: number;
}

interface StorageUsage {
  used_mb: number;
  limit_mb: number;
  file_count: number;
  warning: boolean;
}

interface SystemAlert {
  severity: 'warning' | 'info';
  title: string;
  message: string;
  action?: string;
  count?: number;
}

export default function Admin() {
  const [tab, setTab] = useState<Tab>('journals');
  const queryClient = useQueryClient();
  const { data: kbStats } = useQuery<{
    total_papers: number;
    scored_papers: number;
    total_runs: number;
    successful_runs: number;
    last_fetch: string | null;
  }>({
    queryKey: ['admin', 'kb-stats'],
    queryFn: async () => (await api.get('/api/v1/admin/kb-stats')).data,
    staleTime: 60000,
  });
  const { data: storage } = useQuery<StorageUsage>({
    queryKey: ['admin', 'storage'],
    queryFn: async () => (await api.get('/api/v1/admin/storage-usage')).data,
    staleTime: 60000,
  });
  const { data: alerts } = useQuery<SystemAlert[]>({
    queryKey: ['admin', 'alerts'],
    queryFn: async () => (await api.get('/api/v1/admin/alerts')).data,
    staleTime: 60000,
  });
  const backfillMutation = useMutation({
    mutationFn: async () => (await api.post('/api/v1/admin/backfill-embeddings')).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'alerts'] });
    },
  });

  const tabs: { key: Tab; label: string; icon: typeof Settings }[] = [
    { key: 'journals', label: 'Journals', icon: Settings },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'pipeline', label: 'Fetch Papers', icon: Activity },
    { key: 'keywords', label: 'Platform Scope', icon: Tags },
    { key: 'digest', label: 'Digest', icon: Mail },
    { key: 'settings', label: 'Limits', icon: Sliders },
  ];

  return (
    <div style={{ padding: '32px 24px' }}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }} className="font-mono text-text-primary">
          Admin Panel
        </h1>

        {/* Tab bar */}
        <div
          className="rounded-2xl bg-bg-surface"
          style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: 6, marginBottom: 32 }}
        >
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex items-center rounded-xl font-mono text-sm transition',
                tab === t.key
                  ? 'bg-accent text-white'
                  : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
              )}
              style={{ gap: 8, padding: '10px 18px' }}
            >
              <t.icon size={15} />
              {t.label}
            </button>
          ))}
        </div>

        {/* Knowledge base stats — Fetch Papers tab only */}
        {tab === 'pipeline' && kbStats && (
          <div
            className="rounded-2xl border border-border-default bg-bg-surface font-mono"
            style={{ padding: '14px 20px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 12 }}
          >
            <BookOpen size={16} className="text-text-tertiary" style={{ flexShrink: 0 }} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, flex: 1 }}>
              <span className="text-xs text-text-secondary">
                Papers: <strong className="text-text-primary">{kbStats.total_papers}</strong>
              </span>
              <span className="text-xs text-text-secondary">
                Scored: <strong className="text-text-primary">{kbStats.scored_papers}</strong>
              </span>
              <span className="text-xs text-text-secondary">
                Fetches: <strong className="text-text-primary">{kbStats.successful_runs}</strong>/{kbStats.total_runs}
              </span>
              {kbStats.last_fetch && (
                <span className="text-xs text-text-secondary">
                  Last: <strong className="text-text-primary">{formatDate(kbStats.last_fetch)}</strong>
                </span>
              )}
            </div>
          </div>
        )}

        {/* Storage usage — Digest tab only */}
        {tab === 'digest' && storage && storage.used_mb > 0 && (
          <div
            className={cn(
              'rounded-2xl border font-mono',
              storage.warning ? 'border-warning/40 bg-warning/5' : 'border-border-default bg-bg-surface',
            )}
            style={{ padding: '12px 20px', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12 }}
          >
            <HardDrive size={16} className={storage.warning ? 'text-warning' : 'text-text-tertiary'} />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className={cn('text-xs', storage.warning ? 'text-warning' : 'text-text-secondary')}>
                  Podcast storage: {storage.used_mb} MB / {storage.limit_mb} MB ({storage.file_count} files)
                </span>
                {storage.warning && (
                  <span className="text-xs text-warning font-medium">
                    — Approaching limit! Consider deleting old podcasts.
                  </span>
                )}
              </div>
              <div className="rounded-full bg-border-default" style={{ height: 3, marginTop: 6, overflow: 'hidden' }}>
                <div
                  className={cn('rounded-full', storage.warning ? 'bg-warning' : 'bg-accent')}
                  style={{ height: '100%', width: `${Math.min(100, (storage.used_mb / storage.limit_mb) * 100)}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Embedding alerts — Fetch Papers tab only */}
        {tab === 'pipeline' && alerts && alerts.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
            {alerts.map((alert, i) => (
              <div
                key={i}
                className={cn(
                  'rounded-2xl border font-mono',
                  alert.severity === 'warning'
                    ? 'border-warning/40 bg-warning/5'
                    : 'border-accent/30 bg-accent/5',
                )}
                style={{ padding: '14px 20px' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  {alert.severity === 'warning' ? (
                    <AlertTriangle size={16} className="text-warning" style={{ marginTop: 2, flexShrink: 0 }} />
                  ) : (
                    <Info size={16} className="text-accent" style={{ marginTop: 2, flexShrink: 0 }} />
                  )}
                  <div style={{ flex: 1 }}>
                    <div className={cn('text-sm font-medium', alert.severity === 'warning' ? 'text-warning' : 'text-accent')}>
                      {alert.title}
                    </div>
                    <div className="text-xs text-text-secondary" style={{ marginTop: 4, lineHeight: 1.5 }}>
                      {alert.message}
                    </div>
                    {alert.action === 'backfill-embeddings' && (
                      <button
                        onClick={() => backfillMutation.mutate()}
                        disabled={backfillMutation.isPending}
                        className="text-xs text-accent hover:text-accent-hover transition font-medium"
                        style={{ marginTop: 8, padding: '4px 0' }}
                      >
                        {backfillMutation.isPending ? (
                          <span className="flex items-center" style={{ gap: 6 }}>
                            <Loader2 size={12} className="animate-spin" /> Running backfill...
                          </span>
                        ) : backfillMutation.isSuccess ? (
                          'Backfill triggered — check back in a few minutes'
                        ) : (
                          'Run Backfill Now'
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === 'journals' && <JournalConfigTab />}
        {tab === 'users' && <UserManagementTab />}
        {tab === 'pipeline' && <PipelineStatusTab />}
        {tab === 'keywords' && <GlobalKeywordsTab />}
        {tab === 'digest' && <DigestTab />}
        {tab === 'settings' && <UsageLimitsTab />}
      </div>
    </div>
  );
}

function JournalConfigTab() {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({ name: '', publisher: '', source_type: 'scopus_api', source_identifier: '' });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ name: '', publisher: '', source_type: 'scopus_api', source_identifier: '' });

  const { data: journals, isLoading, isError } = useQuery<Journal[]>({
    queryKey: ['admin', 'journals'],
    queryFn: async () => (await api.get('/api/v1/admin/journals')).data,
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      await api.patch(`/api/v1/admin/journals/${id}`, { is_active });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'journals'] }),
  });

  const addMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      await api.post('/api/v1/admin/journals', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'journals'] });
      setForm({ name: '', publisher: '', source_type: 'scopus_api', source_identifier: '' });
      setShowAddForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/v1/admin/journals/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'journals'] }),
  });

  const editMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: typeof editForm }) => {
      await api.patch(`/api/v1/admin/journals/${id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'journals'] });
      setEditingId(null);
    },
  });

  const startEdit = (j: Journal) => {
    setEditingId(j.id);
    setEditForm({
      name: j.name,
      publisher: j.publisher,
      source_type: j.source_type,
      source_identifier: j.source_identifier,
    });
  };

  const cancelEdit = () => setEditingId(null);

  const editActiveHint = (() => {
    const hints: Record<string, string> = {
      ieee_api: 'Publication number (e.g. 59)',
      scopus_api: 'ISSN (e.g. ISSN:0306-2619)',
      rss: 'Full RSS URL',
    };
    return hints[editForm.source_type] || '';
  })();

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load journals" />;

  const sourceTypes = [
    { value: 'ieee_api', label: 'IEEE Xplore', hint: 'Publication number (e.g. 61)' },
    { value: 'scopus_api', label: 'Scopus', hint: 'ISSN (e.g. ISSN:0306-2619)' },
    { value: 'rss', label: 'RSS Feed', hint: 'Full RSS URL' },
  ];
  const activeHint = sourceTypes.find((s) => s.value === form.source_type)?.hint || '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Add button / form */}
      {!showAddForm ? (
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
          style={{ gap: 10, padding: '14px 24px', width: 'fit-content' }}
        >
          <Plus size={16} /> Add Journal
        </button>
      ) : (
        <div className="rounded-2xl border border-accent/30 bg-bg-surface" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h3 className="font-mono font-medium text-text-primary" style={{ fontSize: 15 }}>Add New Journal</h3>
            <button onClick={() => setShowAddForm(false)} className="text-text-tertiary hover:text-text-primary">
              <X size={18} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Journal Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Applied Energy"
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              />
            </div>

            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Publisher</label>
              <input
                value={form.publisher}
                onChange={(e) => setForm({ ...form, publisher: e.target.value })}
                placeholder="e.g. elsevier, ieee, nature"
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              />
            </div>

            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Source Type</label>
              <div className="relative">
                <select
                  value={form.source_type}
                  onChange={(e) => setForm({ ...form, source_type: e.target.value })}
                  className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent appearance-none"
                  style={{ width: '100%', padding: '10px 16px', paddingRight: 40 }}
                >
                  {sourceTypes.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
                <ChevronDown size={16} className="text-text-tertiary" style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
              </div>
            </div>

            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Source Identifier</label>
              <input
                value={form.source_identifier}
                onChange={(e) => setForm({ ...form, source_identifier: e.target.value })}
                placeholder={activeHint}
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              />
              <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginTop: 6 }}>{activeHint}</p>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button
                onClick={() => addMutation.mutate(form)}
                disabled={!form.name || !form.publisher || !form.source_identifier || addMutation.isPending}
                className="flex items-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                style={{ gap: 8, padding: '10px 20px' }}
              >
                {addMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                Add Journal
              </button>
              <button
                onClick={() => setShowAddForm(false)}
                className="rounded-xl font-mono text-sm text-text-secondary hover:text-text-primary"
                style={{ padding: '10px 20px' }}
              >
                Cancel
              </button>
            </div>

            {addMutation.isError && (
              <p className="font-mono text-danger" style={{ fontSize: 12 }}>Failed to add journal. Try again.</p>
            )}
          </div>
        </div>
      )}

      {/* Journal list */}
      {!journals?.length && !showAddForm ? (
        <EmptyState
          title="No journals configured"
          description="Add journals to start discovering papers."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {journals?.map((j) => editingId === j.id ? (
            <div
              key={j.id}
              className="rounded-2xl border border-accent/30 bg-bg-surface"
              style={{ padding: 20 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Journal Name</label>
                  <input
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                    style={{ width: '100%', padding: '10px 16px' }}
                  />
                </div>

                <div>
                  <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Publisher</label>
                  <input
                    value={editForm.publisher}
                    onChange={(e) => setEditForm({ ...editForm, publisher: e.target.value })}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                    style={{ width: '100%', padding: '10px 16px' }}
                  />
                </div>

                <div>
                  <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Source Type</label>
                  <div className="relative">
                    <select
                      value={editForm.source_type}
                      onChange={(e) => setEditForm({ ...editForm, source_type: e.target.value })}
                      className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent appearance-none"
                      style={{ width: '100%', padding: '10px 16px', paddingRight: 40 }}
                    >
                      {sourceTypes.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="text-text-tertiary" style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                  </div>
                </div>

                <div>
                  <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Source Identifier</label>
                  <input
                    value={editForm.source_identifier}
                    onChange={(e) => setEditForm({ ...editForm, source_identifier: e.target.value })}
                    placeholder={editActiveHint}
                    className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                    style={{ width: '100%', padding: '10px 16px' }}
                  />
                  <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginTop: 6 }}>{editActiveHint}</p>
                </div>

                <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                  <button
                    onClick={() => editMutation.mutate({ id: j.id, data: editForm })}
                    disabled={!editForm.name || !editForm.publisher || !editForm.source_identifier || editMutation.isPending}
                    className="flex items-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                    style={{ gap: 8, padding: '10px 20px' }}
                  >
                    {editMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    Save
                  </button>
                  <button
                    onClick={cancelEdit}
                    className="rounded-xl font-mono text-sm text-text-secondary hover:text-text-primary"
                    style={{ padding: '10px 20px' }}
                  >
                    Cancel
                  </button>
                </div>

                {editMutation.isError && (
                  <p className="font-mono text-danger" style={{ fontSize: 12 }}>Failed to update journal. Try again.</p>
                )}
              </div>
            </div>
          ) : (
            <div
              key={j.id}
              className="rounded-2xl border border-border-default bg-bg-surface"
              style={{ padding: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <p className="font-mono font-medium text-text-primary" style={{ fontSize: 14 }}>{j.name}</p>
                <p className="font-mono text-text-tertiary" style={{ fontSize: 12, marginTop: 6 }}>
                  {j.publisher} &middot; {j.source_type.replace('_', ' ')} &middot; {j.source_identifier}
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                <button
                  onClick={() => toggleMutation.mutate({ id: j.id, is_active: !j.is_active })}
                  className={cn('transition', j.is_active ? 'text-success' : 'text-text-tertiary')}
                  title={j.is_active ? 'Active — click to disable' : 'Disabled — click to enable'}
                >
                  {j.is_active ? <ToggleRight size={32} /> : <ToggleLeft size={32} />}
                </button>
                <button
                  onClick={() => startEdit(j)}
                  className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-text-primary"
                  title="Edit journal"
                  style={{ padding: 6 }}
                >
                  <Pencil size={16} />
                </button>
                <button
                  onClick={() => { if (confirm(`Remove "${j.name}"?`)) deleteMutation.mutate(j.id); }}
                  className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-danger"
                  title="Remove journal"
                  style={{ padding: 6 }}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UserManagementTab() {
  const queryClient = useQueryClient();
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: '', full_name: '', role: 'researcher' });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ full_name: '', role: '' });

  const { data: users, isLoading, isError } = useQuery<UserItem[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await api.get('/api/v1/admin/users/stats')).data,
  });

  const inviteMutation = useMutation({
    mutationFn: async (data: typeof inviteForm) => {
      const resp = await api.post('/api/v1/admin/users/invite', data);
      return resp.data as { id: string; status: string; email: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setInviteForm({ email: '', full_name: '', role: 'researcher' });
      setShowInviteForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, ...data }: { id: string; full_name?: string; role?: string }) => {
      await api.patch(`/api/v1/admin/users/${id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/v1/admin/users/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] }),
  });

  const startEditing = (u: UserItem) => {
    setEditingId(u.id);
    setEditForm({ full_name: u.full_name, role: u.role });
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load users" />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Invite button / form */}
      {!showInviteForm ? (
        <button
          onClick={() => setShowInviteForm(true)}
          className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
          style={{ gap: 10, padding: '14px 24px', width: 'fit-content' }}
        >
          <UserPlus size={16} /> Invite User
        </button>
      ) : (
        <div className="rounded-2xl border border-accent/30 bg-bg-surface" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h3 className="font-mono font-medium text-text-primary" style={{ fontSize: 15 }}>Invite New User</h3>
            <button onClick={() => setShowInviteForm(false)} className="text-text-tertiary hover:text-text-primary">
              <X size={18} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Full Name</label>
              <input
                value={inviteForm.full_name}
                onChange={(e) => setInviteForm({ ...inviteForm, full_name: e.target.value })}
                placeholder="e.g. Jane Smith"
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              />
            </div>

            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Email</label>
              <input
                type="email"
                value={inviteForm.email}
                onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                placeholder="jane@university.edu.au"
                className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '10px 16px' }}
              />
            </div>

            <div>
              <label className="font-mono text-xs text-text-secondary" style={{ display: 'block', marginBottom: 6 }}>Role</label>
              <div className="relative">
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}
                  className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent appearance-none"
                  style={{ width: '100%', padding: '10px 16px', paddingRight: 40 }}
                >
                  <option value="researcher">Researcher</option>
                  <option value="admin">Admin</option>
                </select>
                <ChevronDown size={16} className="text-text-tertiary" style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <button
                onClick={() => inviteMutation.mutate(inviteForm)}
                disabled={!inviteForm.full_name || !inviteForm.email || inviteMutation.isPending}
                className="flex items-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
                style={{ gap: 8, padding: '10px 20px' }}
              >
                {inviteMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
                Send Invite
              </button>
              <button
                onClick={() => setShowInviteForm(false)}
                className="rounded-xl font-mono text-sm text-text-secondary hover:text-text-primary"
                style={{ padding: '10px 20px' }}
              >
                Cancel
              </button>
            </div>

            {inviteMutation.isError && (
              <p className="font-mono text-danger" style={{ fontSize: 12 }}>
                {(inviteMutation.error as any)?.response?.data?.detail || 'Failed to invite user. Try again.'}
              </p>
            )}
            {inviteMutation.isSuccess && (
              <p className="font-mono text-success" style={{ fontSize: 12 }}>
                Invite sent to {inviteMutation.data?.email}
              </p>
            )}
          </div>
        </div>
      )}

      {/* User list */}
      {!users?.length && !showInviteForm ? (
        <EmptyState title="No users found" description="Invite your first team member above." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {users?.map((u) => (
            <div
              key={u.id}
              className="rounded-2xl border border-border-default bg-bg-surface"
              style={{ padding: 20 }}
            >
              {editingId === u.id ? (
                /* Inline edit mode */
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <input
                    value={editForm.full_name}
                    onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                    className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                    style={{ padding: '8px 12px' }}
                  />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <select
                      value={editForm.role}
                      onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                      className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent appearance-none"
                      style={{ padding: '8px 12px', paddingRight: 32 }}
                    >
                      <option value="researcher">Researcher</option>
                      <option value="admin">Admin</option>
                    </select>
                    <button
                      onClick={() => updateMutation.mutate({ id: u.id, full_name: editForm.full_name, role: editForm.role })}
                      disabled={updateMutation.isPending}
                      className="rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50"
                      style={{ padding: '8px 12px' }}
                    >
                      {updateMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="rounded-lg text-text-tertiary hover:text-text-primary"
                      style={{ padding: '8px 12px' }}
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              ) : (
                /* Display mode */
                <>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <p className="font-mono font-medium text-text-primary" style={{ fontSize: 14 }}>{u.full_name}</p>
                      <p className="font-mono text-text-tertiary" style={{ fontSize: 12, marginTop: 4 }}>{u.email}</p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <span
                        className={cn(
                          'rounded-full font-mono',
                          u.role === 'admin' ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-secondary',
                        )}
                        style={{ fontSize: 12, padding: '5px 14px' }}
                      >
                        {u.role}
                      </span>
                      <button
                        onClick={() => startEditing(u)}
                        className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-text-primary"
                        title="Edit user"
                        style={{ padding: 6 }}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        onClick={() => { if (confirm(`Remove "${u.full_name}" from LitOrbit? This cannot be undone.`)) deleteMutation.mutate(u.id); }}
                        disabled={deleteMutation.isPending}
                        className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-danger"
                        title="Remove user"
                        style={{ padding: 6 }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>

                  {/* Activity stats */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
                    <StatBadge label="Invited" value={u.invited_at ? new Date(u.invited_at).toLocaleDateString() : '—'} />
                    <StatBadge label="Accepted" value={u.accepted_at ? new Date(u.accepted_at).toLocaleDateString() : 'Pending'} highlight={!u.accepted_at} />
                    <StatBadge label="Last login" value={u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'} />
                    <StatBadge label="Logins" value={String(u.login_count)} />
                    <StatBadge label="Ratings" value={String(u.ratings_count)} />
                    <StatBadge label="Podcasts" value={String(u.podcasts_generated)} />
                    <StatBadge label="Listens" value={String(u.podcasts_listened)} />
                    <StatBadge label="Collections" value={String(u.collections_count)} />
                    <StatBadge label="Shares" value={String(u.shares_sent)} />
                    <StatBadge label="Digests" value={String(u.digests_received)} />
                  </div>
                  {u.last_active && (
                    <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginTop: 8 }}>
                      Last active: {new Date(u.last_active).toLocaleDateString()}
                    </p>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatElapsed(start: string | null, end: string | null): string {
  if (!start) return '';
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const sec = Math.floor((e - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

const STEP_LABELS: Record<string, string> = {
  discovery: 'Connecting to journal sources',
  raw_papers: 'Papers discovered',
  dedup: 'Removing duplicates',
  saved: 'Saving new papers',
  prefilter: 'Filtering by relevance keywords',
  scoring: 'AI scoring for your interests',
  summarisation: 'Generating AI summaries',
};

function RunAccordion({ run, rescoreMutation, deleteBatchMutation }: {
  run: PipelineRun;
  rescoreMutation: ReturnType<typeof useMutation<{ papers_count: number; scores_deleted: number }, Error, string>>;
  deleteBatchMutation: ReturnType<typeof useMutation<{ papers_deleted: number }, Error, string>>;
}) {
  const isDeleted = run.status === 'deleted';
  const isRunning = run.status === 'running';
  const [expanded, setExpanded] = useState(!isDeleted);

  // Tick every second while running so the elapsed timer updates live
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  return (
    <div
      className={cn(
        'rounded-2xl border',
        run.status === 'running' ? 'border-warning/40 bg-bg-surface' :
        isDeleted ? 'border-dashed border-border-default bg-bg-base' :
        'border-border-default bg-bg-surface',
      )}
    >
      {/* Accordion header — always visible, clickable */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left"
        style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            className={cn(
              'rounded-full',
              run.status === 'success' && 'bg-success',
              run.status === 'failed' && 'bg-danger',
              run.status === 'deleted' && 'bg-text-tertiary',
              run.status === 'running' && 'bg-warning animate-pulse',
            )}
            style={{ width: 10, height: 10, flexShrink: 0 }}
          />
          <span className={cn('font-mono font-medium capitalize', isDeleted ? 'text-text-tertiary' : 'text-text-primary')} style={{ fontSize: 14 }}>
            {run.status === 'running' ? 'Fetching papers...' : isDeleted ? 'Deleted' : run.status}
          </span>
          {isDeleted && (
            <span className="font-mono text-xs text-text-tertiary">
              — {run.error_message || `${run.papers_processed} papers removed`}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="font-mono text-text-tertiary" style={{ fontSize: 12, textAlign: 'right' }}>
            <div>{formatDate(run.started_at)}</div>
            {run.started_at && (
              <div style={{ marginTop: 2 }}>
                {run.status === 'running' ? 'Elapsed' : 'Duration'}: {formatElapsed(run.started_at, run.completed_at)}
              </div>
            )}
          </div>
          <ChevronDown
            size={16}
            className={cn('text-text-tertiary transition-transform', expanded && 'rotate-180')}
          />
        </div>
      </button>

      {/* Accordion body */}
      {expanded && (
        <div style={{ padding: '0 20px 16px' }}>
          {/* Running progress indicator */}
          {run.status === 'running' && (
            <div>
              <div className="rounded-full bg-border-default" style={{ height: 4, overflow: 'hidden' }}>
                <div
                  className="bg-warning animate-pulse rounded-full"
                  style={{ height: '100%', width: '60%', transition: 'width 0.5s' }}
                />
              </div>
              <div className="font-mono text-text-secondary" style={{ marginTop: 10, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Loader2 size={13} className="animate-spin text-warning" />
                {run.papers_discovered > 0
                  ? `Found ${run.papers_discovered} papers so far, processing...`
                  : 'Connecting to journal sources and fetching papers...'}
              </div>
            </div>
          )}

          {/* Stats row */}
          {run.status !== 'running' && (
            <div className={cn('font-mono text-text-secondary', isDeleted && 'line-through')} style={{ display: 'flex', flexWrap: 'wrap', gap: 20, fontSize: 13 }}>
              <span>Discovered: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.papers_discovered}</strong></span>
              <span>New: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.papers_filtered}</strong></span>
              <span>Processed: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.papers_processed}</strong></span>
            </div>
          )}

          {/* Step-by-step log */}
          {run.run_log && run.run_log.length > 0 && <RunLogSteps log={run.run_log} />}

          {/* Error / info message */}
          {run.error_message && (
            <p
              className={cn(
                'rounded-xl font-mono',
                isDeleted ? 'bg-bg-base text-text-tertiary' : 'bg-danger/10 text-danger',
              )}
              style={{ marginTop: 12, padding: '10px 14px', fontSize: 12 }}
            >
              {run.error_message}
            </p>
          )}

          {/* Per-run actions */}
          {run.status === 'success' && (
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <button
                onClick={() => { if (confirm(`Re-score ${run.papers_processed} papers from this batch?`)) rescoreMutation.mutate(run.id); }}
                disabled={rescoreMutation.isPending}
                className="flex items-center rounded-xl border border-border-default font-mono text-xs text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                style={{ gap: 6, padding: '8px 14px' }}
              >
                {rescoreMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Activity size={13} />}
                Re-score
              </button>
              <button
                onClick={() => { if (confirm(`Delete all ${run.papers_processed} papers from this batch? This cannot be undone.`)) deleteBatchMutation.mutate(run.id); }}
                disabled={deleteBatchMutation.isPending}
                className="flex items-center rounded-xl border border-border-default font-mono text-xs text-text-secondary transition hover:border-danger hover:text-danger disabled:opacity-50"
                style={{ gap: 6, padding: '8px 14px' }}
              >
                {deleteBatchMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                Delete batch
              </button>
              {rescoreMutation.isSuccess && rescoreMutation.variables === run.id && (
                <span className="font-mono text-success" style={{ fontSize: 11 }}>
                  Re-scoring {rescoreMutation.data?.papers_count} papers...
                </span>
              )}
              {deleteBatchMutation.isSuccess && deleteBatchMutation.variables === run.id && (
                <span className="font-mono text-success" style={{ fontSize: 11 }}>
                  Deleted {deleteBatchMutation.data?.papers_deleted} papers
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RunLogSteps({ log }: { log: Record<string, unknown>[] }) {
  if (!log?.length) return null;
  return (
    <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {log.map((entry, i) => {
        const step = entry.step as string;
        const label = STEP_LABELS[step] || step;
        const details = Object.entries(entry)
          .filter(([k]) => k !== 'step')
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ');
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className="text-success" style={{ fontSize: 14, flexShrink: 0 }}>✓</span>
            <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>
              {label}
              {details && <span className="text-text-tertiary"> — {details}</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function PipelineStatusTab() {
  const queryClient = useQueryClient();
  const { data: runs, isLoading, isError } = useQuery<PipelineRun[]>({
    queryKey: ['admin', 'pipeline'],
    queryFn: async () => (await api.get('/api/v1/admin/pipeline/runs')).data,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasRunning = data?.some((r) => r.status === 'running');
      return hasRunning ? 3000 : false;
    },
  });

  const isRunning = runs?.some((r) => r.status === 'running');

  const triggerMutation = useMutation({
    mutationFn: async () => {
      await api.post('/api/v1/admin/pipeline/trigger');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'pipeline'] });
    },
  });

  const deleteBatchMutation = useMutation({
    mutationFn: async (runId: string) => {
      const { data } = await api.delete(`/api/v1/admin/pipeline/runs/${runId}/papers`);
      return data as { papers_deleted: number };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'pipeline'] });
      queryClient.invalidateQueries({ queryKey: ['papers'] });
    },
  });

  const rescoreMutation = useMutation({
    mutationFn: async (runId: string) => {
      const { data } = await api.post(`/api/v1/admin/rescore/${runId}`);
      return data as { papers_count: number; scores_deleted: number };
    },
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <button
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending || !!isRunning}
          className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          style={{ gap: 10, padding: '14px 24px' }}
        >
          {triggerMutation.isPending || isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {isRunning ? 'Fetching...' : 'Fetch Papers Now'}
        </button>
        {isRunning && (
          <span className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>
            Auto-refreshing every 3s
          </span>
        )}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message="Failed to load fetch history" />
      ) : !runs?.length ? (
        <EmptyState title="No fetch runs yet" description="Click 'Fetch Papers Now' to discover new papers from your journals." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {runs.map((run) => (
            <RunAccordion key={run.id} run={run} rescoreMutation={rescoreMutation} deleteBatchMutation={deleteBatchMutation} />
          ))}
        </div>
      )}
    </div>
  );
}

function GlobalKeywordsTab() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery<{ keywords: string[] }>({
    queryKey: ['admin', 'keywords'],
    queryFn: async () => (await api.get('/api/v1/admin/keywords')).data,
  });

  const [newKeyword, setNewKeyword] = useState('');

  const updateMutation = useMutation({
    mutationFn: async (keywords: string[]) => {
      await api.put('/api/v1/admin/keywords', { keywords });
    },
    onMutate: async (keywords: string[]) => {
      await queryClient.cancelQueries({ queryKey: ['admin', 'keywords'] });
      const previous = queryClient.getQueryData<{ keywords: string[] }>(['admin', 'keywords']);
      queryClient.setQueryData(['admin', 'keywords'], { keywords });
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(['admin', 'keywords'], ctx.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['admin', 'keywords'] }),
  });

  const addKeyword = () => {
    if (!newKeyword.trim() || !data) return;
    const updated = [...data.keywords, newKeyword.trim()];
    updateMutation.mutate(updated);
    setNewKeyword('');
  };

  const removeKeyword = (kw: string) => {
    if (!data) return;
    updateMutation.mutate(data.keywords.filter((k) => k !== kw));
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load keywords" />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <p className="font-mono text-xs text-text-tertiary" style={{ lineHeight: 1.6 }}>
        <strong>Platform scope keywords</strong> — the hard topical boundary for LitOrbit. A discovered paper must match at least one of these in its title or abstract to enter <em>any</em> user's pipeline. This is the global on-topic gate, not a per-user preference: it defines what LitOrbit is <em>about</em>, and saves API cost by discarding out-of-domain papers before scoring. Edits persist across restarts.
      </p>
      <div style={{ display: 'flex', gap: 12 }}>
        <input
          value={newKeyword}
          onChange={(e) => setNewKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
          placeholder="Add keyword..."
          className="rounded-2xl border border-border-default bg-bg-surface text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
          style={{ flex: 1, padding: '12px 18px' }}
        />
        <button
          onClick={addKeyword}
          className="flex items-center rounded-2xl bg-accent font-mono text-sm text-white hover:bg-accent-hover"
          style={{ gap: 8, padding: '12px 20px' }}
        >
          <Plus size={16} /> Add
        </button>
      </div>

      {!data?.keywords.length ? (
        <EmptyState title="No keywords yet" description="Add keywords to help filter and score papers." />
      ) : (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {data.keywords.map((kw) => (
              <span
                key={kw}
                className="flex items-center rounded-full border border-border-default bg-bg-surface font-mono text-text-secondary"
                style={{ gap: 10, padding: '8px 16px', fontSize: 13 }}
              >
                {kw}
                <button onClick={() => removeKeyword(kw)} className="text-text-tertiary hover:text-danger">
                  <X size={14} />
                </button>
              </span>
            ))}
          </div>
          <p className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>
            {data.keywords.length} keywords configured
          </p>
        </>
      )}
    </div>
  );
}

interface DigestRunItem {
  id: string;
  frequency: string;
  run_type: string;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  users_total: number;
  users_sent: number;
  users_skipped: number;
  users_failed: number;
  error_message: string | null;
  run_log: Record<string, unknown>[];
}

const DIGEST_STEP_LABELS: Record<string, string> = {
  querying_users: 'Finding eligible users',
  users_found: 'Users identified',
  processing_user: 'Processing user',
  user_sent: 'Digest sent',
  user_partial: 'Email failed (podcast saved)',
  user_podcast_failed: 'Podcast generation failed',
  user_skipped: 'Skipped (no papers)',
  user_skipped_duplicate: 'Skipped (already sent today)',
  user_failed: 'Failed to send',
  user_error: 'Error',
  completed: 'Completed',
};

function DigestRunAccordion({ run }: { run: DigestRunItem }) {
  const defaultExpanded = run.status === 'running';
  const isRunning = run.status === 'running';
  const [expanded, setExpanded] = useState(defaultExpanded);

  // Tick every second while running so the elapsed timer updates live
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  return (
    <div
      className={cn(
        'rounded-2xl border',
        run.status === 'running' ? 'border-warning/40 bg-bg-surface' :
        run.status === 'failed' ? 'border-danger/30 bg-bg-surface' :
        run.status === 'partial' ? 'border-warning/30 bg-bg-surface' :
        'border-border-default bg-bg-surface',
      )}
    >
      {/* Accordion header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left"
        style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            className={cn(
              'rounded-full',
              run.status === 'success' && 'bg-success',
              run.status === 'partial' && 'bg-warning',
              run.status === 'failed' && 'bg-danger',
              run.status === 'running' && 'bg-warning animate-pulse',
            )}
            style={{ width: 10, height: 10, flexShrink: 0 }}
          />
          <span className="font-mono font-medium capitalize text-text-primary" style={{ fontSize: 14 }}>
            {run.status === 'running' ? 'Running digest...' : run.status === 'partial' ? 'Partial Success' : run.status}
          </span>
          <span className={cn(
            'rounded-full font-mono',
            (run.run_type || 'email') === 'podcast' ? 'bg-purple-500/15 text-purple-400' : 'bg-accent/15 text-accent',
          )} style={{ fontSize: 11, padding: '2px 10px' }}>
            {(run.run_type || 'email') === 'podcast' ? 'Podcast' : 'Email'}
          </span>
          <span className="rounded-full bg-bg-elevated font-mono text-text-tertiary" style={{ fontSize: 11, padding: '2px 10px' }}>
            {run.frequency}
          </span>
          {!expanded && run.status !== 'running' && run.users_total > 0 && (
            <span className="font-mono text-xs text-text-tertiary">
              — {run.users_sent} sent, {run.users_total} users
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="font-mono text-text-tertiary" style={{ fontSize: 12, textAlign: 'right' }}>
            <div>{formatDate(run.started_at)}</div>
            {run.started_at && (
              <div style={{ marginTop: 2 }}>
                {run.status === 'running' ? 'Elapsed' : 'Duration'}: {formatElapsed(run.started_at, run.completed_at)}
              </div>
            )}
          </div>
          <ChevronDown
            size={16}
            className={cn('text-text-tertiary transition-transform', expanded && 'rotate-180')}
          />
        </div>
      </button>

      {/* Accordion body */}
      {expanded && (
        <div style={{ padding: '0 20px 16px' }}>
          {/* Running progress */}
          {run.status === 'running' && (
            <div>
              <div className="rounded-full bg-border-default" style={{ height: 4, overflow: 'hidden' }}>
                <div
                  className="bg-warning rounded-full transition-all"
                  style={{
                    height: '100%',
                    width: run.users_total > 0
                      ? `${Math.max(5, ((run.users_sent + run.users_skipped + run.users_failed) / run.users_total) * 100)}%`
                      : '10%',
                    ...(run.users_total === 0 ? { animation: 'pulse 2s infinite' } : {}),
                  }}
                />
              </div>
              <div className="font-mono text-text-secondary" style={{ marginTop: 10, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Loader2 size={13} className="animate-spin text-warning" />
                {run.users_total > 0
                  ? `Processing ${run.users_sent + run.users_skipped + run.users_failed} / ${run.users_total} users...`
                  : 'Initialising...'}
              </div>
            </div>
          )}

          {/* Stats row */}
          {run.status !== 'running' && run.users_total > 0 && (
            <div className="font-mono text-text-secondary" style={{ display: 'flex', flexWrap: 'wrap', gap: 20, fontSize: 13 }}>
              <span>Users: <strong className="text-text-primary">{run.users_total}</strong></span>
              <span>Sent: <strong className="text-success">{run.users_sent}</strong></span>
              {run.users_skipped > 0 && <span>Skipped: <strong className="text-text-tertiary">{run.users_skipped}</strong></span>}
              {run.users_failed > 0 && <span>Failed: <strong className="text-danger">{run.users_failed}</strong></span>}
            </div>
          )}

          {/* Step log */}
          {run.run_log && run.run_log.length > 0 && <DigestRunLogSteps log={run.run_log} />}

          {/* Error */}
          {run.error_message && (
            <p className="rounded-xl bg-danger/10 font-mono text-danger" style={{ marginTop: 12, padding: '10px 14px', fontSize: 12 }}>
              {run.error_message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DigestRunLogSteps({ log }: { log: Record<string, unknown>[] }) {
  if (!log?.length) return null;
  return (
    <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {log.map((entry, i) => {
        const step = entry.step as string;
        const label = DIGEST_STEP_LABELS[step] || step;
        const isProcessing = step === 'processing_user';
        const isWarning = step === 'user_partial' || step === 'user_podcast_failed' || (step === 'completed' && (entry.email_failed || entry.skipped));
        const isError = step === 'user_error' || step === 'user_failed';
        const details: string[] = [];
        if (entry.user) details.push(entry.user as string);
        if (entry.index) details.push(`${entry.index}/${entry.total}`);
        if (entry.papers !== undefined) details.push(`${entry.papers} papers`);
        if (entry.podcast) details.push('+ podcast');
        if (entry.email_failed) details.push('email failed');
        if (entry.eligible !== undefined) details.push(`${entry.eligible} eligible`);
        if (entry.skipped_day) details.push(`${entry.skipped_day} skipped (wrong day)`);
        if (entry.sent !== undefined && entry.total !== undefined) details.push(`${entry.sent}/${entry.total} sent`);
        if (step === 'completed' && entry.email_failed) details.push(`${entry.email_failed} email failed`);
        if (step === 'completed' && entry.skipped) details.push(`${entry.skipped} skipped`);
        if (entry.error) details.push(entry.error as string);
        if (entry.error_detail) details.push(entry.error_detail as string);
        if (entry.detail) details.push(entry.detail as string);
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span className={isProcessing ? 'text-warning' : isError ? 'text-danger' : isWarning ? 'text-warning' : 'text-success'} style={{ fontSize: 14, flexShrink: 0 }}>
              {isProcessing ? '◦' : isError ? '✗' : isWarning ? '⚠' : '✓'}
            </span>
            <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>
              {label}
              {details.length > 0 && <span className="text-text-tertiary"> — {details.join(', ')}</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function DigestTab() {
  const queryClient = useQueryClient();
  const [frequency, setFrequency] = useState<'weekly' | 'daily'>('weekly');

  const { data: runs, isLoading } = useQuery<DigestRunItem[]>({
    queryKey: ['admin', 'digest-runs'],
    queryFn: async () => (await api.get('/api/v1/admin/digest/runs')).data,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasRunning = data?.some((r) => r.status === 'running');
      return hasRunning ? 3000 : false;
    },
  });

  const isRunning = runs?.some((r) => r.status === 'running');

  const triggerMutation = useMutation({
    mutationFn: async ({ freq, product }: { freq: string; product: string }) => {
      const { data } = await api.post('/api/v1/admin/digest/trigger', { frequency: freq, product });
      return data as { status: string; frequency: string; product: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'digest-runs'] });
    },
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <p className="font-mono text-xs text-text-tertiary" style={{ lineHeight: 1.6 }}>
        Manually trigger email digests and standalone podcast digests for all eligible users.
        Each user receives personalised content based on their own interest profile and settings.
        This is the same process that runs automatically after the daily pipeline.
        Manual triggers ignore the day-of-week setting.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        {/* Frequency selector */}
        <div className="flex rounded-xl bg-bg-base" style={{ padding: 4, gap: 4 }}>
          {(['daily', 'weekly'] as const).map((freq) => (
            <button
              key={freq}
              onClick={() => setFrequency(freq)}
              className={cn(
                'rounded-lg font-mono text-xs transition',
                frequency === freq ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
              )}
              style={{ padding: '6px 14px' }}
            >
              {freq}
            </button>
          ))}
        </div>

        {/* Trigger buttons */}
        <button
          onClick={() => triggerMutation.mutate({ freq: frequency, product: 'email' })}
          disabled={triggerMutation.isPending || !!isRunning}
          className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          style={{ gap: 8, padding: '12px 20px' }}
        >
          {triggerMutation.isPending || isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {isRunning ? 'Running...' : `Email digest (${frequency})`}
        </button>
        <button
          onClick={() => triggerMutation.mutate({ freq: frequency, product: 'podcast' })}
          disabled={triggerMutation.isPending || !!isRunning}
          className="flex items-center rounded-2xl bg-purple-600 font-mono text-sm font-medium text-white transition hover:bg-purple-700 disabled:opacity-50"
          style={{ gap: 8, padding: '12px 20px' }}
        >
          {triggerMutation.isPending || isRunning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {isRunning ? 'Running...' : `Podcast digest (${frequency})`}
        </button>

        {isRunning && (
          <span className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>
            Auto-refreshing every 3s
          </span>
        )}
      </div>

      {/* Digest run history */}
      {isLoading ? (
        <LoadingState />
      ) : !runs?.length ? (
        <EmptyState title="No digest runs yet" description="Click the button above to send your first digest." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {runs.map((run) => (
            <DigestRunAccordion key={run.id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatBadge({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <span
      className={cn(
        'rounded-lg font-mono',
        highlight ? 'bg-warning/10 text-warning' : 'bg-bg-elevated text-text-tertiary',
      )}
      style={{ fontSize: 11, padding: '4px 10px' }}
    >
      {label}: <span className={highlight ? 'text-warning' : 'text-text-secondary'}>{value}</span>
    </span>
  );
}


function UsageLimitsTab() {
  const queryClient = useQueryClient();

  const { data: settings, isLoading } = useQuery<SystemSettingsData>({
    queryKey: ['admin', 'settings'],
    queryFn: async () => (await api.get('/api/v1/admin/settings')).data,
  });

  const [form, setForm] = useState<SystemSettingsData | null>(null);

  // Sync form with fetched data
  const activeForm = form || settings;

  const saveMutation = useMutation({
    mutationFn: async (data: Partial<SystemSettingsData>) => {
      await api.put('/api/v1/admin/settings', data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'settings'] });
      setForm(null);
    },
  });

  if (isLoading || !activeForm) return <LoadingState />;

  const hasChanges = form !== null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <p className="font-mono text-xs text-text-tertiary" style={{ lineHeight: 1.6 }}>
        Control costs by limiting AI-powered features. These limits apply to all users.
      </p>

      {/* Podcast generation limit */}
      <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
        <label className="font-mono text-sm text-text-primary font-medium" style={{ display: 'block', marginBottom: 6 }}>
          Max podcasts per user per month
        </label>
        <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginBottom: 12 }}>
          Each on-demand podcast uses one Claude API call. Set to 0 to disable podcast generation entirely.
        </p>
        <input
          type="number"
          min={0}
          value={activeForm.max_podcasts_per_user_per_month}
          onChange={(e) => setForm({ ...activeForm, max_podcasts_per_user_per_month: parseInt(e.target.value) || 0 })}
          className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
          style={{ width: 120, padding: '10px 16px' }}
        />
      </div>

      {/* Digest podcast toggle */}
      <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <label className="font-mono text-sm text-text-primary font-medium" style={{ display: 'block', marginBottom: 6 }}>
              Digest podcasts
            </label>
            <p className="font-mono text-text-tertiary" style={{ fontSize: 11 }}>
              Master switch for digest podcast generation. Each digest podcast uses one Claude API call per user.
            </p>
          </div>
          <button
            onClick={() => setForm({ ...activeForm, digest_podcast_enabled_global: !activeForm.digest_podcast_enabled_global })}
            className={cn('transition', activeForm.digest_podcast_enabled_global ? 'text-success' : 'text-text-tertiary')}
          >
            {activeForm.digest_podcast_enabled_global ? <ToggleRight size={32} /> : <ToggleLeft size={32} />}
          </button>
        </div>
      </div>

      {/* Max papers per digest */}
      <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
        <label className="font-mono text-sm text-text-primary font-medium" style={{ display: 'block', marginBottom: 6 }}>
          Max papers per digest
        </label>
        <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginBottom: 12 }}>
          Caps how many papers are included in each digest email and podcast. More papers = longer podcast script = more tokens.
        </p>
        <input
          type="number"
          min={1}
          max={20}
          value={activeForm.max_papers_per_digest}
          onChange={(e) => setForm({ ...activeForm, max_papers_per_digest: parseInt(e.target.value) || 1 })}
          className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
          style={{ width: 120, padding: '10px 16px' }}
        />
      </div>

      {/* Save button */}
      {hasChanges && (
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={() => saveMutation.mutate(form)}
            disabled={saveMutation.isPending}
            className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
            style={{ gap: 8, padding: '14px 24px' }}
          >
            {saveMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
            Save Changes
          </button>
          <button
            onClick={() => setForm(null)}
            className="rounded-2xl font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ padding: '14px 24px' }}
          >
            Cancel
          </button>
        </div>
      )}

      {saveMutation.isError && (
        <p className="font-mono text-danger" style={{ fontSize: 12 }}>Failed to save settings. Try again.</p>
      )}
    </div>
  );
}


function LoadingState() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '64px 0' }}>
      <Loader2 size={24} className="animate-spin text-text-tertiary" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 64 }}>
      <p className="font-mono text-danger" style={{ fontSize: 14 }}>{message}</p>
      <button
        onClick={() => window.location.reload()}
        className="rounded-xl bg-bg-elevated font-mono text-sm text-text-secondary hover:text-text-primary"
        style={{ marginTop: 14, padding: '10px 20px' }}
      >
        Retry
      </button>
    </div>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 64 }}>
      <p className="font-mono text-text-secondary" style={{ fontSize: 16 }}>{title}</p>
      <p className="font-mono text-text-tertiary" style={{ marginTop: 6, fontSize: 14 }}>{description}</p>
    </div>
  );
}
