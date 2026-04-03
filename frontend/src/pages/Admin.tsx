import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Settings, Users, Activity, Tags, ToggleLeft, ToggleRight, Play, Loader2, Plus, X } from 'lucide-react';
import api from '@/lib/api';
import { cn, formatDate } from '@/lib/utils';

type Tab = 'journals' | 'users' | 'pipeline' | 'keywords';

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
}

export default function Admin() {
  const [tab, setTab] = useState<Tab>('journals');

  const tabs: { key: Tab; label: string; icon: typeof Settings }[] = [
    { key: 'journals', label: 'Journals', icon: Settings },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'pipeline', label: 'Pipeline', icon: Activity },
    { key: 'keywords', label: 'Keywords', icon: Tags },
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

        {tab === 'journals' && <JournalConfigTab />}
        {tab === 'users' && <UserManagementTab />}
        {tab === 'pipeline' && <PipelineStatusTab />}
        {tab === 'keywords' && <GlobalKeywordsTab />}
      </div>
    </div>
  );
}

function JournalConfigTab() {
  const queryClient = useQueryClient();
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

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load journals" />;

  if (!journals?.length) {
    return (
      <EmptyState
        title="No journals configured"
        description="Journals will appear here once added via the API or database."
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {journals.map((j) => (
        <div
          key={j.id}
          className="rounded-2xl border border-border-default bg-bg-surface"
          style={{ padding: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        >
          <div>
            <p className="font-mono font-medium text-text-primary" style={{ fontSize: 14 }}>{j.name}</p>
            <p className="font-mono text-text-tertiary" style={{ fontSize: 12, marginTop: 6 }}>
              {j.publisher} &middot; {j.source_type} &middot; {j.source_identifier}
            </p>
          </div>
          <button
            onClick={() => toggleMutation.mutate({ id: j.id, is_active: !j.is_active })}
            className={cn('transition', j.is_active ? 'text-success' : 'text-text-tertiary')}
            style={{ flexShrink: 0, marginLeft: 16 }}
          >
            {j.is_active ? <ToggleRight size={32} /> : <ToggleLeft size={32} />}
          </button>
        </div>
      ))}
    </div>
  );
}

function UserManagementTab() {
  const { data: users, isLoading, isError } = useQuery<UserItem[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await api.get('/api/v1/users')).data,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load users" />;

  if (!users?.length) {
    return <EmptyState title="No users found" description="Users who sign up will appear here." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {users.map((u) => (
        <div
          key={u.id}
          className="rounded-2xl border border-border-default bg-bg-surface"
          style={{ padding: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        >
          <div>
            <p className="font-mono font-medium text-text-primary" style={{ fontSize: 14 }}>{u.full_name}</p>
            <p className="font-mono text-text-tertiary" style={{ fontSize: 12, marginTop: 6 }}>{u.email}</p>
          </div>
          <span
            className={cn(
              'rounded-full font-mono',
              u.role === 'admin' ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-secondary',
            )}
            style={{ fontSize: 12, padding: '5px 14px', flexShrink: 0 }}
          >
            {u.role}
          </span>
        </div>
      ))}
    </div>
  );
}

function PipelineStatusTab() {
  const queryClient = useQueryClient();
  const { data: runs, isLoading, isError } = useQuery<PipelineRun[]>({
    queryKey: ['admin', 'pipeline'],
    queryFn: async () => (await api.get('/api/v1/admin/pipeline/runs')).data,
  });

  const triggerMutation = useMutation({
    mutationFn: async () => {
      await api.post('/api/v1/admin/pipeline/trigger');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'pipeline'] });
    },
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <button
        onClick={() => triggerMutation.mutate()}
        disabled={triggerMutation.isPending}
        className="flex items-center rounded-2xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
        style={{ gap: 10, padding: '14px 24px', width: 'fit-content' }}
      >
        {triggerMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
        Run Pipeline Now
      </button>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message="Failed to load pipeline runs" />
      ) : !runs?.length ? (
        <EmptyState title="No pipeline runs yet" description="Click 'Run Pipeline Now' to fetch papers." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {runs.map((run) => (
            <div
              key={run.id}
              className="rounded-2xl border border-border-default bg-bg-surface"
              style={{ padding: 20 }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span
                    className={cn(
                      'rounded-full',
                      run.status === 'success' && 'bg-success',
                      run.status === 'failed' && 'bg-danger',
                      run.status === 'running' && 'bg-warning animate-pulse',
                    )}
                    style={{ width: 10, height: 10 }}
                  />
                  <span className="font-mono font-medium text-text-primary capitalize" style={{ fontSize: 14 }}>
                    {run.status}
                  </span>
                </div>
                <span className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>
                  {formatDate(run.started_at)}
                </span>
              </div>
              <div className="font-mono text-text-secondary" style={{ display: 'flex', gap: 24, marginTop: 14, fontSize: 13 }}>
                <span>Discovered: <strong className="text-text-primary">{run.papers_discovered}</strong></span>
                <span>Filtered: <strong className="text-text-primary">{run.papers_filtered}</strong></span>
                <span>Processed: <strong className="text-text-primary">{run.papers_processed}</strong></span>
              </div>
              {run.error_message && (
                <p
                  className="rounded-xl bg-danger/10 font-mono text-danger"
                  style={{ marginTop: 12, padding: '10px 14px', fontSize: 12 }}
                >
                  {run.error_message}
                </p>
              )}
            </div>
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'keywords'] }),
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
