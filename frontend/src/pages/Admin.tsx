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
    <div className="mx-auto max-w-4xl p-4">
      <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Admin Panel</h1>

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 rounded-lg bg-bg-surface p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'flex items-center gap-2 rounded-md px-4 py-2 font-mono text-sm transition',
              tab === t.key ? 'bg-bg-elevated text-text-primary' : 'text-text-secondary hover:text-text-primary',
            )}
          >
            <t.icon size={14} />
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
  const { data: journals, isLoading } = useQuery<Journal[]>({
    queryKey: ['admin', 'journals'],
    queryFn: async () => (await api.get('/api/v1/admin/journals')).data,
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      await api.patch(`/api/v1/admin/journals/${id}`, { is_active });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'journals'] }),
  });

  if (isLoading) return <div className="font-mono text-sm text-text-secondary">Loading...</div>;

  return (
    <div className="space-y-2">
      {journals?.map((j) => (
        <div key={j.id} className="flex items-center justify-between rounded-lg border border-border-default bg-bg-surface p-3">
          <div>
            <p className="font-mono text-sm text-text-primary">{j.name}</p>
            <p className="font-mono text-xs text-text-tertiary">{j.publisher} · {j.source_type} · {j.source_identifier}</p>
          </div>
          <button
            onClick={() => toggleMutation.mutate({ id: j.id, is_active: !j.is_active })}
            className={cn('transition', j.is_active ? 'text-success' : 'text-text-tertiary')}
          >
            {j.is_active ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
          </button>
        </div>
      ))}
    </div>
  );
}

function UserManagementTab() {
  const { data: users, isLoading } = useQuery<UserItem[]>({
    queryKey: ['admin', 'users'],
    queryFn: async () => (await api.get('/api/v1/users')).data,
  });

  if (isLoading) return <div className="font-mono text-sm text-text-secondary">Loading...</div>;

  return (
    <div className="space-y-2">
      {!users?.length ? (
        <p className="py-10 text-center font-mono text-sm text-text-secondary">No users found</p>
      ) : (
        users.map((u) => (
          <div key={u.id} className="flex items-center justify-between rounded-lg border border-border-default bg-bg-surface p-3">
            <div>
              <p className="font-mono text-sm text-text-primary">{u.full_name}</p>
              <p className="font-mono text-xs text-text-tertiary">{u.email}</p>
            </div>
            <span className={cn(
              'rounded-full px-2.5 py-0.5 font-mono text-xs',
              u.role === 'admin' ? 'bg-accent/15 text-accent' : 'bg-bg-elevated text-text-secondary',
            )}>
              {u.role}
            </span>
          </div>
        ))
      )}
    </div>
  );
}

function PipelineStatusTab() {
  const queryClient = useQueryClient();
  const { data: runs, isLoading } = useQuery<PipelineRun[]>({
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
    <div className="space-y-4">
      <button
        onClick={() => triggerMutation.mutate()}
        disabled={triggerMutation.isPending}
        className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
      >
        {triggerMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
        Run Pipeline Now
      </button>

      {isLoading ? (
        <div className="font-mono text-sm text-text-secondary">Loading...</div>
      ) : !runs?.length ? (
        <p className="py-10 text-center font-mono text-sm text-text-secondary">No pipeline runs yet</p>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <div key={run.id} className="rounded-lg border border-border-default bg-bg-surface p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'h-2 w-2 rounded-full',
                    run.status === 'success' && 'bg-success',
                    run.status === 'failed' && 'bg-danger',
                    run.status === 'running' && 'bg-warning animate-pulse',
                  )} />
                  <span className="font-mono text-sm text-text-primary">{run.status}</span>
                </div>
                <span className="font-mono text-xs text-text-tertiary">
                  {formatDate(run.started_at)}
                </span>
              </div>
              <div className="mt-2 flex gap-4 font-mono text-xs text-text-secondary">
                <span>Discovered: {run.papers_discovered}</span>
                <span>Filtered: {run.papers_filtered}</span>
                <span>Processed: {run.papers_processed}</span>
              </div>
              {run.error_message && (
                <p className="mt-1 font-mono text-xs text-danger">{run.error_message}</p>
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
  const { data, isLoading } = useQuery<{ keywords: string[] }>({
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

  if (isLoading) return <div className="font-mono text-sm text-text-secondary">Loading...</div>;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={newKeyword}
          onChange={(e) => setNewKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
          placeholder="Add keyword..."
          className="flex-1 rounded-lg border border-border-default bg-bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
        />
        <button
          onClick={addKeyword}
          className="flex items-center gap-1 rounded-lg bg-accent px-3 py-2 font-mono text-sm text-white hover:bg-accent-hover"
        >
          <Plus size={14} /> Add
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {data?.keywords.map((kw) => (
          <span
            key={kw}
            className="flex items-center gap-1 rounded-full bg-bg-surface px-3 py-1 font-mono text-xs text-text-secondary"
          >
            {kw}
            <button onClick={() => removeKeyword(kw)} className="text-text-tertiary hover:text-danger">
              <X size={12} />
            </button>
          </span>
        ))}
      </div>

      <p className="font-mono text-xs text-text-tertiary">{data?.keywords.length} keywords</p>
    </div>
  );
}
