import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Play, Loader2, ToggleLeft, ToggleRight, AlertTriangle, ChevronDown, Activity } from 'lucide-react';
import api from '@/lib/api';
import { cn, formatDate } from '@/lib/utils';
import type { NewsSource } from '@/types/feed';

interface NewsIngestRun {
  id: string;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  items_new: number;
  items_skipped: number;
  items_embedded: number;
  items_scored: number;
  items_errors: number;
  sources_total: number;
  sources_succeeded: number;
  sources_failed: number;
  error_message: string | null;
  run_log: Record<string, unknown>[];
}


function formatElapsed(start: string | null, end: string | null): string {
  if (!start) return '';
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const sec = Math.floor((e - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

export default function NewsTab() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <NewsSourcesSection />
      <NewsFetchSection />
    </div>
  );
}

// --- News Sources List (identical to existing NewsSourcesTab) ---

function NewsSourcesSection() {
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
                  : `${(ingestMutation.data as any)?.new ?? 0} new, ${(ingestMutation.data as any)?.embedded ?? 0} embedded, ${(ingestMutation.data as any)?.scored ?? 0} scored, ${(ingestMutation.data as any)?.skipped_exists ?? 0} skipped — ${(ingestMutation.data as any)?.total_visible ?? '?'} visible`
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


// --- News Fetch Section (with trigger button + run history accordion) ---

function NewsFetchSection() {
  const queryClient = useQueryClient();

  const { data: runs, isLoading, isError } = useQuery<NewsIngestRun[]>({
    queryKey: ['admin', 'news-runs'],
    queryFn: async () => (await api.get('/api/v1/admin/news/runs')).data,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasRunning = data?.some((r) => r.status === 'running');
      return hasRunning ? 3000 : false;
    },
  });

  const isRunning = runs?.some((r) => r.status === 'running');

  const triggerMutation = useMutation({
    mutationFn: async () => {
      await api.post('/api/v1/admin/news/trigger');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'news-runs'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'news-stats'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'news-sources'] });
    },
  });

  const deleteBatchMutation = useMutation({
    mutationFn: async (runId: string) => {
      const { data } = await api.delete(`/api/v1/admin/news/runs/${runId}/items`);
      return data as { items_deleted: number };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'news-runs'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'news-stats'] });
    },
  });

  const rescoreMutation = useMutation({
    mutationFn: async (runId: string) => {
      const { data } = await api.post(`/api/v1/admin/news/runs/${runId}/rescore`);
      return data as { items_rescored: number; errors: number };
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
          {isRunning ? 'Fetching...' : 'Fetch News Now'}
        </button>
        {isRunning && (
          <span className="font-mono text-text-tertiary" style={{ fontSize: 12 }}>
            Auto-refreshing every 3s
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="font-mono text-sm text-text-tertiary" style={{ padding: 40, textAlign: 'center' }}>
          <Loader2 size={24} className="animate-spin mx-auto text-accent" style={{ marginBottom: 12 }} />
          Loading...
        </div>
      ) : isError ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 64 }}>
          <p className="font-mono text-danger" style={{ fontSize: 14 }}>Failed to load fetch history</p>
        </div>
      ) : !runs?.length ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 64 }}>
          <p className="font-mono text-text-secondary" style={{ fontSize: 16 }}>No fetch runs yet</p>
          <p className="font-mono text-text-tertiary" style={{ marginTop: 6, fontSize: 14 }}>Click 'Fetch News Now' to discover new articles from your sources.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {runs.map((run) => (
            <NewsRunAccordion key={run.id} run={run} rescoreMutation={rescoreMutation} deleteBatchMutation={deleteBatchMutation} />
          ))}
        </div>
      )}
    </div>
  );
}

// --- News Run Accordion ---

function NewsRunAccordion({ run, rescoreMutation, deleteBatchMutation }: {
  run: NewsIngestRun;
  rescoreMutation: ReturnType<typeof useMutation<{ items_rescored: number; errors: number }, Error, string>>;
  deleteBatchMutation: ReturnType<typeof useMutation<{ items_deleted: number }, Error, string>>;
}) {
  const isDeleted = run.status === 'deleted';
  const isRunning = run.status === 'running';
  const [expanded, setExpanded] = useState(!isDeleted);

  // Tick every second while running so elapsed timer updates
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
        run.status === 'partial' ? 'border-warning/30 bg-bg-surface' :
        run.status === 'failed' ? 'border-danger/30 bg-bg-surface' :
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
              run.status === 'deleted' && 'bg-text-tertiary',
              run.status === 'running' && 'bg-warning animate-pulse',
            )}
            style={{ width: 10, height: 10, flexShrink: 0 }}
          />
          <span className={cn('font-mono font-medium capitalize', isDeleted ? 'text-text-tertiary' : 'text-text-primary')} style={{ fontSize: 14 }}>
            {run.status === 'running' ? 'Fetching news...' : isDeleted ? 'Deleted' : run.status}
          </span>
          {isDeleted && (
            <span className="font-mono text-xs text-text-tertiary">
              — {run.error_message || `${run.items_new} items removed`}
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
                Fetching from {run.sources_total} source{run.sources_total !== 1 ? 's' : ''}...
              </div>
            </div>
          )}

          {/* Stats row */}
          {run.status !== 'running' && (
            <div className={cn('font-mono text-text-secondary', isDeleted && 'line-through')} style={{ display: 'flex', flexWrap: 'wrap', gap: 20, fontSize: 13 }}>
              <span>New: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.items_new}</strong></span>
              <span>Embedded: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.items_embedded}</strong></span>
              <span>Scored: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.items_scored}</strong></span>
              <span>Skipped: <strong className={isDeleted ? 'text-text-tertiary' : 'text-text-primary'}>{run.items_skipped}</strong></span>
              {run.items_errors > 0 && (
                <span className="text-danger">Errors: <strong>{run.items_errors}</strong></span>
              )}
              <span className="text-text-tertiary">Sources: {run.sources_succeeded}/{run.sources_total}</span>
            </div>
          )}

          {/* Per-source log */}
          {run.run_log && run.run_log.length > 0 && (
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {run.run_log.map((entry: any, i: number) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className={entry.error ? 'text-danger' : 'text-success'} style={{ fontSize: 14, flexShrink: 0 }}>
                    {entry.error ? '✕' : '✓'}
                  </span>
                  <span className="font-mono text-text-secondary" style={{ fontSize: 12 }}>
                    {entry.source}
                    {entry.error
                      ? <span className="text-danger"> — {entry.error}</span>
                      : <span className="text-text-tertiary"> — {entry.new ?? 0} new, {entry.scored ?? 0} scored, {entry.embedded ?? 0} embedded</span>
                    }
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Error message */}
          {run.error_message && !isDeleted && (
            <p
              className="rounded-xl font-mono bg-danger/10 text-danger"
              style={{ marginTop: 12, padding: '10px 14px', fontSize: 12 }}
            >
              {run.error_message}
            </p>
          )}

          {/* Per-run actions */}
          {(run.status === 'success' || run.status === 'partial') && (
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <button
                onClick={() => { if (confirm(`Re-score ${run.items_new} news items from this batch?`)) rescoreMutation.mutate(run.id); }}
                disabled={rescoreMutation.isPending}
                className="flex items-center rounded-xl border border-border-default font-mono text-xs text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
                style={{ gap: 6, padding: '8px 14px' }}
              >
                {rescoreMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Activity size={13} />}
                Re-score
              </button>
              <button
                onClick={() => { if (confirm(`Delete all ${run.items_new} news items from this batch? This cannot be undone.`)) deleteBatchMutation.mutate(run.id); }}
                disabled={deleteBatchMutation.isPending}
                className="flex items-center rounded-xl border border-border-default font-mono text-xs text-text-secondary transition hover:border-danger hover:text-danger disabled:opacity-50"
                style={{ gap: 6, padding: '8px 14px' }}
              >
                {deleteBatchMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                Delete batch
              </button>
              {rescoreMutation.isSuccess && rescoreMutation.variables === run.id && (
                <span className="font-mono text-success" style={{ fontSize: 11 }}>
                  Re-scored {rescoreMutation.data?.items_rescored} items
                </span>
              )}
              {deleteBatchMutation.isSuccess && deleteBatchMutation.variables === run.id && (
                <span className="font-mono text-success" style={{ fontSize: 11 }}>
                  Deleted {deleteBatchMutation.data?.items_deleted} items
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
