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
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 font-mono text-xl font-medium text-text-primary">Admin Panel</h1>

      {/* Tab bar */}
      <div className="mb-8 flex flex-wrap gap-2 rounded-xl bg-bg-surface p-1.5">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2.5 font-mono text-sm transition',
              tab === t.key
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
            )}
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {journals.map((j) => (
        <div key={j.id} className="flex items-center justify-between rounded-xl border border-border-default bg-bg-surface p-4">
          <div>
            <p className="font-mono text-sm font-medium text-text-primary">{j.name}</p>
            <p className="mt-1 font-mono text-xs text-text-tertiary">
              {j.publisher} &middot; {j.source_type} &middot; {j.source_identifier}
            </p>
          </div>
          <button
            onClick={() => toggleMutation.mutate({ id: j.id, is_active: !j.is_active })}
            className={cn('transition', j.is_active ? 'text-success' : 'text-text-tertiary')}
          >
            {j.is_active ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {users.map((u) => (
        <div key={u.id} className="flex items-center justify-between rounded-xl border border-border-default bg-bg-surface p-4">
          <div>
            <p className="font-mono text-sm font-medium text-text-primary">{u.full_name}</p>
            <p className="mt-1 font-mono text-xs text-text-tertiary">{u.email}</p>
          </div>
          <span className={cn(
            'rounded-full px-3 py-1 font-mono text-xs',
            u.role === 'admin' ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-secondary',
          )}>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <button
        onClick={() => triggerMutation.mutate()}
        disabled={triggerMutation.isPending}
        className="flex w-fit items-center gap-2 rounded-xl bg-accent px-5 py-3 font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
      >
        {triggerMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
        Run Pipeline Now
      </button>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message="Failed to load pipeline runs" />
      ) : !runs?.length ? (
        <EmptyState title="No pipeline runs yet" description="Click 'Run Pipeline Now' to fetch papers." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {runs.map((run) => (
            <div key={run.id} className="rounded-xl border border-border-default bg-bg-surface p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={cn(
                    'h-2.5 w-2.5 rounded-full',
                    run.status === 'success' && 'bg-success',
                    run.status === 'failed' && 'bg-danger',
                    run.status === 'running' && 'bg-warning animate-pulse',
                  )} />
                  <span className="font-mono text-sm font-medium text-text-primary capitalize">{run.status}</span>
                </div>
                <span className="font-mono text-xs text-text-tertiary">
                  {formatDate(run.started_at)}
                </span>
              </div>
              <div className="mt-3 flex gap-6 font-mono text-xs text-text-secondary">
                <span>Discovered: <strong className="text-text-primary">{run.papers_discovered}</strong></span>
                <span>Filtered: <strong className="text-text-primary">{run.papers_filtered}</strong></span>
                <span>Processed: <strong className="text-text-primary">{run.papers_processed}</strong></span>
              </div>
              {run.error_message && (
                <p className="mt-2 rounded-lg bg-danger/10 p-2 font-mono text-xs text-danger">{run.error_message}</p>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="flex gap-3">
        <input
          value={newKeyword}
          onChange={(e) => setNewKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
          placeholder="Add keyword..."
          className="flex-1 rounded-xl border border-border-default bg-bg-surface px-4 py-3 text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
        />
        <button
          onClick={addKeyword}
          className="flex items-center gap-2 rounded-xl bg-accent px-4 py-3 font-mono text-sm text-white hover:bg-accent-hover"
        >
          <Plus size={15} /> Add
        </button>
      </div>

      {!data?.keywords.length ? (
        <EmptyState title="No keywords yet" description="Add keywords to help filter and score papers." />
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {data.keywords.map((kw) => (
              <span
                key={kw}
                className="flex items-center gap-2 rounded-full border border-border-default bg-bg-surface px-3 py-1.5 font-mono text-xs text-text-secondary"
              >
                {kw}
                <button onClick={() => removeKeyword(kw)} className="text-text-tertiary hover:text-danger">
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
          <p className="font-mono text-xs text-text-tertiary">{data.keywords.length} keywords configured</p>
        </>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 size={20} className="animate-spin text-text-tertiary" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <p className="font-mono text-sm text-danger">{message}</p>
      <button
        onClick={() => window.location.reload()}
        className="mt-3 rounded-lg bg-bg-elevated px-4 py-2 font-mono text-sm text-text-secondary hover:text-text-primary"
      >
        Retry
      </button>
    </div>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <p className="font-mono text-base text-text-secondary">{title}</p>
      <p className="mt-1 font-mono text-sm text-text-tertiary">{description}</p>
    </div>
  );
}
