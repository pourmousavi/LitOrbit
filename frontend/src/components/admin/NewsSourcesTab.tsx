import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Play, Loader2, ToggleLeft, ToggleRight, AlertTriangle } from 'lucide-react';
import api from '@/lib/api';
import { cn, formatDate } from '@/lib/utils';
import type { NewsSource } from '@/types/feed';

export default function NewsSourcesTab() {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({ name: '', feed_url: '', website_url: '', authority_weight: '1.0' });

  const { data: sources, isLoading } = useQuery<NewsSource[]>({
    queryKey: ['admin', 'news-sources'],
    queryFn: async () => (await api.get('/api/v1/admin/news-sources')).data,
  });

  const addMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      return (await api.post('/api/v1/admin/news-sources', {
        ...data,
        authority_weight: parseFloat(data.authority_weight),
      })).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'news-sources'] });
      setShowAddForm(false);
      setForm({ name: '', feed_url: '', website_url: '', authority_weight: '1.0' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      return (await api.patch(`/api/v1/admin/news-sources/${id}`, { enabled })).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'news-sources'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => (await api.delete(`/api/v1/admin/news-sources/${id}`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'news-sources'] }),
  });

  const testMutation = useMutation({
    mutationFn: async (id: string) => (await api.post(`/api/v1/admin/news-sources/${id}/test-feed`)).data,
  });

  const ingestMutation = useMutation({
    mutationFn: async (id: string) => (await api.post(`/api/v1/admin/news-sources/${id}/run-now`)).data,
  });

  if (isLoading) {
    return <div className="font-mono text-sm text-text-tertiary" style={{ padding: 40, textAlign: 'center' }}>Loading news sources...</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 className="font-mono text-lg font-semibold text-text-primary">News Sources</h2>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center rounded-xl bg-accent font-mono text-xs font-medium text-white transition hover:bg-accent-hover"
          style={{ gap: 6, padding: '8px 14px' }}
        >
          <Plus size={14} /> Add Source
        </button>
      </div>

      {showAddForm && (
        <div className="rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Source name (e.g. RenewEconomy)"
              className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
              style={{ padding: '8px 12px' }}
            />
            <input
              value={form.feed_url}
              onChange={(e) => setForm({ ...form, feed_url: e.target.value })}
              placeholder="RSS feed URL (e.g. https://example.com/feed/)"
              className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
              style={{ padding: '8px 12px' }}
            />
            <input
              value={form.website_url}
              onChange={(e) => setForm({ ...form, website_url: e.target.value })}
              placeholder="Website URL (e.g. https://example.com/)"
              className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
              style={{ padding: '8px 12px' }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <label className="font-mono text-xs text-text-secondary">Authority weight:</label>
              <input
                type="number"
                value={form.authority_weight}
                onChange={(e) => setForm({ ...form, authority_weight: e.target.value })}
                min="0" max="2" step="0.05"
                className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary outline-none focus:border-accent"
                style={{ padding: '8px 12px', width: 80 }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => addMutation.mutate(form)}
                disabled={!form.name || !form.feed_url || !form.website_url || addMutation.isPending}
                className="flex items-center rounded-lg bg-accent font-mono text-xs text-white hover:bg-accent-hover disabled:opacity-50"
                style={{ gap: 6, padding: '8px 14px' }}
              >
                {addMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                Add
              </button>
              <button onClick={() => setShowAddForm(false)} className="rounded-lg font-mono text-xs text-text-secondary hover:text-text-primary" style={{ padding: '8px 14px' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {(sources || []).map((source) => (
          <div
            key={source.id}
            className="rounded-2xl border border-border-default bg-bg-surface"
            style={{ padding: 16 }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span className="font-mono text-sm font-semibold text-text-primary">{source.name}</span>
                  <span className={cn(
                    'rounded-lg font-mono text-xs',
                    source.enabled ? 'bg-success/15 text-success' : 'bg-bg-elevated text-text-tertiary',
                  )} style={{ padding: '2px 8px' }}>
                    {source.enabled ? 'Active' : 'Disabled'}
                  </span>
                  <span className="rounded-lg bg-bg-elevated font-mono text-xs text-text-tertiary" style={{ padding: '2px 8px' }}>
                    w={source.authority_weight.toFixed(2)}
                  </span>
                </div>
                <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 4, wordBreak: 'break-all' }}>
                  {source.feed_url}
                </p>
                <div className="font-mono text-xs text-text-tertiary" style={{ display: 'flex', gap: 12 }}>
                  <span>Cap: {source.per_source_daily_cap}/day</span>
                  <span>Min relevance: {source.per_source_min_relevance}</span>
                  {source.last_fetched_at && (
                    <span>
                      Last fetch: {formatDate(source.last_fetched_at)}
                      {source.last_fetch_status && (
                        <span className={cn('ml-1', source.last_fetch_status === 'ok' ? 'text-success' : 'text-danger')}>
                          ({source.last_fetch_status})
                        </span>
                      )}
                    </span>
                  )}
                </div>
                {source.last_fetch_error && (
                  <p className="font-mono text-xs text-danger" style={{ marginTop: 4 }}>
                    <AlertTriangle size={11} className="inline mr-1" />
                    {source.last_fetch_error}
                  </p>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                <button
                  onClick={() => testMutation.mutate(source.id)}
                  disabled={testMutation.isPending}
                  className="rounded-lg font-mono text-xs text-text-secondary hover:text-accent hover:bg-bg-elevated transition"
                  style={{ padding: '6px 10px' }}
                  title="Test feed"
                >
                  {testMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : 'Test'}
                </button>
                <button
                  onClick={() => ingestMutation.mutate(source.id)}
                  disabled={ingestMutation.isPending}
                  className="rounded-lg text-text-secondary hover:text-accent hover:bg-bg-elevated transition"
                  style={{ padding: 6 }}
                  title="Run ingest now"
                >
                  {ingestMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Play size={14} />}
                </button>
                <button
                  onClick={() => toggleMutation.mutate({ id: source.id, enabled: !source.enabled })}
                  className="rounded-lg text-text-secondary hover:text-text-primary transition"
                  style={{ padding: 6 }}
                  title={source.enabled ? 'Disable' : 'Enable'}
                >
                  {source.enabled ? <ToggleRight size={18} className="text-success" /> : <ToggleLeft size={18} />}
                </button>
                <button
                  onClick={() => { if (confirm(`Delete "${source.name}"?`)) deleteMutation.mutate(source.id); }}
                  className="rounded-lg text-text-tertiary hover:text-danger transition"
                  style={{ padding: 6 }}
                  title="Delete source"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>

            {/* Test result */}
            {testMutation.isSuccess && testMutation.variables === source.id && (
              <div className={cn(
                'rounded-lg font-mono text-xs mt-3',
                (testMutation.data as any)?.valid ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger',
              )} style={{ padding: '8px 12px' }}>
                {(testMutation.data as any)?.valid
                  ? `Valid feed: ${(testMutation.data as any)?.item_count} items, latest: ${(testMutation.data as any)?.latest_pub_at || 'unknown'}`
                  : `Invalid: ${(testMutation.data as any)?.parse_errors?.join(', ') || 'Unknown error'}`}
              </div>
            )}

            {/* Ingest result */}
            {ingestMutation.isSuccess && ingestMutation.variables === source.id && (
              <div className={`rounded-lg font-mono text-xs mt-3 ${(ingestMutation.data as any)?.error ? 'bg-danger/10 text-danger' : 'bg-success/10 text-success'}`} style={{ padding: '8px 12px' }}>
                {(ingestMutation.data as any)?.error
                  ? `Error: ${(ingestMutation.data as any)?.error}`
                  : `${(ingestMutation.data as any)?.new ?? 0} new items, ${(ingestMutation.data as any)?.embedded ?? 0} embedded, ${(ingestMutation.data as any)?.skipped_exists ?? 0} skipped (exists), ${(ingestMutation.data as any)?.errors ?? 0} errors — ${(ingestMutation.data as any)?.total_visible ?? '?'} visible in feed`
                }
              </div>
            )}
            {ingestMutation.isError && ingestMutation.variables === source.id && (
              <div className="rounded-lg bg-danger/10 font-mono text-xs text-danger mt-3" style={{ padding: '8px 12px' }}>
                Ingest failed: {(ingestMutation.error as any)?.response?.data?.detail || (ingestMutation.error as any)?.message || 'Unknown error'}
              </div>
            )}
          </div>
        ))}

        {(!sources || sources.length === 0) && (
          <div className="font-mono text-sm text-text-tertiary" style={{ textAlign: 'center', padding: 40 }}>
            No news sources configured. Add one to start ingesting news.
          </div>
        )}
      </div>
    </div>
  );
}
