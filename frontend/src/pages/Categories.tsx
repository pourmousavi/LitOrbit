import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FolderOpen, Plus, X, Trash2, Edit2, Check, Lock, Users } from 'lucide-react';
import api from '@/lib/api';
import { cn, formatDate } from '@/lib/utils';
import PaperCard from '@/components/papers/PaperCard';
import PaperDetail from '@/components/papers/PaperDetail';
import { useUIStore } from '@/stores/uiStore';
import type { Paper } from '@/types';

interface Collection {
  id: string;
  name: string;
  description: string | null;
  color: string;
  visibility: 'shared' | 'private';
  is_owner: boolean;
  paper_count: number;
  podcast_count_single: number;
  podcast_count_dual: number;
  last_updated: string | null;
  top_categories: string[];
  avg_relevance_score: number | null;
  summarized_count: number;
}

const COLORS = ['#0891b2', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#ef4444', '#6366f1', '#14b8a6'];

export default function Categories() {
  const queryClient = useQueryClient();
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const selectPaper = useUIStore((s) => s.selectPaper);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(COLORS[0]);
  const [newVisibility, setNewVisibility] = useState<'shared' | 'private'>('private');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  const { data: collections } = useQuery<Collection[]>({
    queryKey: ['collections'],
    queryFn: async () => (await api.get('/api/v1/collections')).data,
  });

  const { data: collectionPapers } = useQuery<{ papers: Paper[] }>({
    queryKey: ['collection-papers', selectedCollection],
    queryFn: async () => (await api.get(`/api/v1/collections/${selectedCollection}/papers`)).data,
    enabled: !!selectedCollection,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await api.post('/api/v1/collections', { name: newName.trim(), color: newColor, visibility: newVisibility });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setNewName('');
      setShowCreate(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/v1/collections/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      if (selectedCollection) setSelectedCollection(null);
    },
  });

  const renameMutation = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      await api.patch(`/api/v1/collections/${id}`, { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] });
      setEditingId(null);
    },
  });

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Main column */}
      <div className="flex-1 overflow-y-auto px-3 pt-6 pb-4 md:px-6 md:py-8">
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-5">
            Collections
          </h1>

          {/* Collection chips */}
          <div className="flex flex-nowrap gap-2 mb-2 overflow-x-auto pb-1 scrollbar-none md:flex-wrap md:overflow-visible"
          >
            <button
              onClick={() => setSelectedCollection(null)}
              className={cn(
                'whitespace-nowrap rounded-full font-mono text-sm transition',
                !selectedCollection
                  ? 'bg-accent text-white'
                  : 'bg-bg-surface text-text-secondary hover:text-text-primary border border-border-default',
              )}
              style={{ padding: '8px 16px', flexShrink: 0 }}
            >
              All
            </button>
            {collections?.map((col) => (
              <div key={col.id} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                {editingId === col.id ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') renameMutation.mutate({ id: col.id, name: editName }); }}
                      className="rounded-full border border-accent bg-bg-surface font-mono text-sm text-text-primary outline-none"
                      style={{ padding: '7px 14px', width: 140 }}
                      autoFocus
                    />
                    <button
                      onClick={() => renameMutation.mutate({ id: col.id, name: editName })}
                      className="text-success"
                    >
                      <Check size={14} />
                    </button>
                    <button onClick={() => setEditingId(null)} className="text-text-tertiary">
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setSelectedCollection(col.id)}
                    className={cn(
                      'rounded-full font-mono text-sm transition',
                      selectedCollection === col.id
                        ? 'text-white'
                        : 'bg-bg-surface text-text-secondary hover:text-text-primary border border-border-default',
                    )}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: selectedCollection === col.id ? col.color : undefined,
                      borderColor: selectedCollection === col.id ? col.color : undefined,
                    }}
                  >
                    {col.name}
                    <span className="text-xs opacity-70" style={{ marginLeft: 6 }}>{col.paper_count}</span>
                  </button>
                )}
              </div>
            ))}
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center rounded-full border border-dashed border-border-strong font-mono text-xs text-text-tertiary transition hover:border-accent hover:text-accent"
              style={{ gap: 4, padding: '8px 14px' }}
            >
              <Plus size={13} /> New
            </button>
          </div>

          {/* Selected collection actions (owner only) */}
          {selectedCollection && collections && collections.find(c => c.id === selectedCollection)?.is_owner && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 20, marginTop: 8 }}>
              <button
                onClick={() => { const col = collections.find(c => c.id === selectedCollection); if (col) { setEditName(col.name); setEditingId(col.id); } }}
                className="flex items-center rounded-lg font-mono text-xs text-text-tertiary transition hover:text-text-secondary"
                style={{ gap: 4, padding: '4px 8px' }}
              >
                <Edit2 size={12} /> Rename
              </button>
              <button
                onClick={() => { if (confirm('Delete this collection? Papers will NOT be deleted.')) deleteMutation.mutate(selectedCollection); }}
                className="flex items-center rounded-lg font-mono text-xs text-text-tertiary transition hover:text-danger"
                style={{ gap: 4, padding: '4px 8px' }}
              >
                <Trash2 size={12} /> Delete
              </button>
            </div>
          )}

          {/* Create form */}
          {showCreate && (
            <div className="rounded-2xl border border-accent/30 bg-bg-surface" style={{ padding: 20, marginBottom: 20 }}>
              <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim()) createMutation.mutate(); }}
                  placeholder="Collection name..."
                  className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
                  style={{ flex: 1, padding: '10px 16px' }}
                  autoFocus
                />
                <button
                  onClick={() => createMutation.mutate()}
                  disabled={!newName.trim()}
                  className="rounded-xl bg-accent font-mono text-sm text-white hover:bg-accent-hover disabled:opacity-50"
                  style={{ padding: '10px 20px' }}
                >
                  Create
                </button>
                <button onClick={() => setShowCreate(false)} className="text-text-tertiary hover:text-text-primary" style={{ padding: 8 }}>
                  <X size={16} />
                </button>
              </div>
              <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
                {COLORS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setNewColor(c)}
                    className={cn('rounded-full transition', newColor === c ? 'ring-2 ring-white ring-offset-2 ring-offset-bg-surface' : '')}
                    style={{ width: 24, height: 24, backgroundColor: c }}
                  />
                ))}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => setNewVisibility('private')}
                  className={cn(
                    'flex items-center rounded-lg font-mono text-xs transition',
                    newVisibility === 'private' ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                  )}
                  style={{ gap: 6, padding: '6px 12px' }}
                  title="Only you can see and edit this collection"
                >
                  <Lock size={12} /> Private
                </button>
                <button
                  onClick={() => setNewVisibility('shared')}
                  className={cn(
                    'flex items-center rounded-lg font-mono text-xs transition',
                    newVisibility === 'shared' ? 'bg-bg-elevated text-text-primary' : 'text-text-tertiary hover:text-text-secondary',
                  )}
                  style={{ gap: 6, padding: '6px 12px' }}
                  title="All users can see this collection and add papers; only you can rename or delete it"
                >
                  <Users size={12} /> Shared
                </button>
              </div>
            </div>
          )}

          {/* Papers */}
          {!selectedCollection ? (
            !collections?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
                <FolderOpen className="text-text-tertiary" size={40} />
                <p style={{ marginTop: 16, fontSize: 18 }} className="font-mono text-text-secondary">No collections yet</p>
                <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
                  Create a collection to organize your papers
                </p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(300px, 100%), 1fr))', gap: 12, marginTop: 16 }}>
                {collections.map((col) => {
                  const totalPodcasts = col.podcast_count_single + col.podcast_count_dual;
                  return (
                    <button
                      key={col.id}
                      onClick={() => setSelectedCollection(col.id)}
                      className="rounded-2xl border border-border-default bg-bg-surface text-left transition hover:border-border-strong"
                      style={{ padding: 20 }}
                    >
                      {/* Header: color dot + name */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                        <div className="rounded-full" style={{ width: 12, height: 12, backgroundColor: col.color, flexShrink: 0 }} />
                        <span className="font-mono font-medium text-text-primary" style={{ fontSize: 14 }}>{col.name}</span>
                        <span
                          className="flex items-center font-mono text-text-tertiary"
                          style={{ fontSize: 10, gap: 3 }}
                          title={col.visibility === 'private' ? 'Private (only you)' : 'Shared with all users'}
                        >
                          {col.visibility === 'private' ? <Lock size={10} /> : <Users size={10} />}
                          {col.visibility}
                        </span>
                      </div>

                      {/* Stats row */}
                      <div className="font-mono text-text-tertiary" style={{ fontSize: 12, display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
                        <span>{col.paper_count} {col.paper_count === 1 ? 'paper' : 'papers'}</span>
                        {totalPodcasts > 0 && (
                          <span>
                            {totalPodcasts} {totalPodcasts === 1 ? 'podcast' : 'podcasts'}
                            {col.podcast_count_single > 0 && col.podcast_count_dual > 0
                              ? ` (${col.podcast_count_single}S / ${col.podcast_count_dual}D)`
                              : col.podcast_count_dual > 0 ? ' (dual)' : ' (single)'}
                          </span>
                        )}
                        {col.summarized_count > 0 && (
                          <span>{col.summarized_count}/{col.paper_count} summarized</span>
                        )}
                      </div>

                      {/* Avg relevance score */}
                      {col.avg_relevance_score != null && (
                        <p className="font-mono text-text-tertiary" style={{ fontSize: 12, marginTop: 4 }}>
                          Avg relevance: {col.avg_relevance_score}/10
                        </p>
                      )}

                      {/* Top categories */}
                      {col.top_categories && col.top_categories.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                          {col.top_categories.map((cat) => (
                            <span
                              key={cat}
                              className="rounded-full bg-bg-elevated font-mono text-xs text-text-secondary"
                              style={{ padding: '2px 8px' }}
                            >
                              {cat}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Description */}
                      {col.description && (
                        <p className="text-text-secondary" style={{ fontSize: 13, marginTop: 6 }}>{col.description}</p>
                      )}

                      {/* Last updated */}
                      {col.last_updated && (
                        <p className="font-mono text-text-tertiary" style={{ fontSize: 11, marginTop: 8, opacity: 0.7 }}>
                          Updated {formatDate(col.last_updated)}
                        </p>
                      )}
                    </button>
                  );
                })}
              </div>
            )
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 8 }}>
              {!collectionPapers?.papers.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 60 }}>
                  <p className="font-mono text-text-secondary" style={{ fontSize: 16 }}>No papers in this collection</p>
                  <p className="font-mono text-text-tertiary" style={{ marginTop: 6, fontSize: 13 }}>
                    Add papers from the Feed using the detail panel
                  </p>
                </div>
              ) : (
                collectionPapers.papers.map((paper) => (
                  <PaperCard
                    key={paper.id}
                    paper={paper}
                    isSelected={selectedPaperId === paper.id}
                    onClick={() => selectPaper(paper.id)}
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Detail panel — sidebar on desktop, full-screen overlay on mobile */}
      {selectedPaperId && (
        <>
          <div
            className="fixed inset-0 z-50 overflow-y-auto bg-bg-base md:hidden"
            style={{ paddingBottom: 64 }}
          >
            <PaperDetail />
          </div>
          <div
            className="hidden border-l border-border-default bg-bg-surface md:block"
            style={{ width: 420, flexShrink: 0, overflowY: 'auto', height: '100vh' }}
          >
            <PaperDetail />
          </div>
        </>
      )}
    </div>
  );
}
