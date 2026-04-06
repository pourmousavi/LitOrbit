import { useState, useEffect, useRef } from 'react';
import { Search, X, Plus, Upload, Link, Loader2, ArrowUpDown } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '@/stores/uiStore';
import PaperFeed from '@/components/papers/PaperFeed';
import PaperDetail from '@/components/papers/PaperDetail';
import api from '@/lib/api';

export default function Feed() {
  const selectedPaperId = useUIStore((s) => s.selectedPaperId);
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [showDoiInput, setShowDoiInput] = useState(false);
  const [doi, setDoi] = useState('');
  const [sort, setSort] = useState('score');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  // Debounce search input by 400ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput.trim()), 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const { data } = await api.post('/api/v1/papers/upload-new', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data as { paper_id: string; title: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      setShowAddMenu(false);
    },
  });

  const doiMutation = useMutation({
    mutationFn: async (doiValue: string) => {
      const { data } = await api.post('/api/v1/papers/doi-lookup', { doi: doiValue });
      return data as { status: string; paper_id: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['papers'] });
      setDoi('');
      setShowDoiInput(false);
      setShowAddMenu(false);
    },
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadMutation.mutate(file);
    e.target.value = '';
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Feed column — independently scrollable */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px 24px' }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
            <h1 style={{ fontSize: 22, fontWeight: 600 }} className="font-mono text-text-primary">
              Paper Feed
            </h1>

            {/* Add Paper button */}
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => { setShowAddMenu(!showAddMenu); setShowDoiInput(false); }}
                className="flex items-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover"
                style={{ gap: 6, padding: '8px 16px' }}
              >
                <Plus size={15} /> Add Paper
              </button>

              {showAddMenu && (
                <div
                  className="rounded-xl border border-border-default bg-bg-surface shadow-lg"
                  style={{ position: 'absolute', right: 0, top: '100%', marginTop: 8, width: 280, zIndex: 50 }}
                >
                  {!showDoiInput ? (
                    <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploadMutation.isPending}
                        className="flex items-center rounded-lg font-mono text-sm text-text-primary transition hover:bg-bg-elevated"
                        style={{ gap: 10, padding: '10px 12px', width: '100%', textAlign: 'left' }}
                      >
                        {uploadMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                        <div>
                          <div>Upload PDF</div>
                          <div className="text-text-tertiary" style={{ fontSize: 11 }}>Add a paper from a PDF file</div>
                        </div>
                      </button>
                      <button
                        onClick={() => setShowDoiInput(true)}
                        className="flex items-center rounded-lg font-mono text-sm text-text-primary transition hover:bg-bg-elevated"
                        style={{ gap: 10, padding: '10px 12px', width: '100%', textAlign: 'left' }}
                      >
                        <Link size={16} />
                        <div>
                          <div>Lookup by DOI</div>
                          <div className="text-text-tertiary" style={{ fontSize: 11 }}>Fetch open access PDF automatically</div>
                        </div>
                      </button>
                    </div>
                  ) : (
                    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <input
                        value={doi}
                        onChange={(e) => setDoi(e.target.value)}
                        placeholder="e.g. 10.1016/j.apenergy.2024.123456"
                        className="rounded-lg border border-border-default bg-bg-base text-sm text-text-primary placeholder-text-tertiary outline-none focus:border-accent"
                        style={{ padding: '8px 12px', width: '100%' }}
                        autoFocus
                        onKeyDown={(e) => { if (e.key === 'Enter' && doi.trim()) doiMutation.mutate(doi.trim()); }}
                      />
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          onClick={() => doiMutation.mutate(doi.trim())}
                          disabled={!doi.trim() || doiMutation.isPending}
                          className="flex items-center rounded-lg bg-accent font-mono text-xs text-white hover:bg-accent-hover disabled:opacity-50"
                          style={{ gap: 6, padding: '8px 14px' }}
                        >
                          {doiMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Link size={13} />}
                          Fetch
                        </button>
                        <button
                          onClick={() => setShowDoiInput(false)}
                          className="rounded-lg font-mono text-xs text-text-secondary hover:text-text-primary"
                          style={{ padding: '8px 14px' }}
                        >
                          Back
                        </button>
                      </div>
                      {doiMutation.isError && (
                        <p className="font-mono text-danger" style={{ fontSize: 11 }}>
                          {(doiMutation.error as any)?.response?.data?.detail || 'Failed to fetch DOI'}
                        </p>
                      )}
                    </div>
                  )}

                  {uploadMutation.isSuccess && (
                    <p className="font-mono text-success" style={{ fontSize: 11, padding: '0 12px 10px' }}>
                      Paper added: {uploadMutation.data?.title?.slice(0, 50)}...
                    </p>
                  )}
                  {uploadMutation.isError && (
                    <p className="font-mono text-danger" style={{ fontSize: 11, padding: '0 12px 10px' }}>
                      {(uploadMutation.error as any)?.response?.data?.detail || 'Failed to upload PDF'}
                    </p>
                  )}
                </div>
              )}

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </div>
          </div>

          {/* Search bar */}
          <div
            className="rounded-2xl border border-border-default bg-bg-surface transition focus-within:border-accent"
            style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', marginBottom: 24 }}
          >
            <Search size={16} className="text-text-tertiary" style={{ flexShrink: 0 }} />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search titles, authors, journals, keywords, DOI..."
              className="font-mono text-sm text-text-primary placeholder-text-tertiary outline-none bg-transparent"
              style={{ flex: 1 }}
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput('')}
                className="text-text-tertiary hover:text-text-primary transition"
                style={{ flexShrink: 0 }}
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Sort options */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <ArrowUpDown size={13} className="text-text-tertiary" style={{ flexShrink: 0 }} />
            {([
              ['score', 'Highest Score'],
              ['newest', 'Recently Fetched'],
              ['published', 'Recently Published'],
              ['oldest', 'Oldest First'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setSort(value)}
                className={`rounded-lg font-mono text-xs transition ${
                  sort === value
                    ? 'bg-bg-elevated text-text-primary'
                    : 'text-text-tertiary hover:text-text-secondary'
                }`}
                style={{ padding: '6px 12px' }}
              >
                {label}
              </button>
            ))}
          </div>

          <PaperFeed search={debouncedSearch || undefined} sort={sort} />
        </div>
      </div>

      {/* Detail panel — independently scrollable */}
      {selectedPaperId && (
        <div
          className="hidden border-l border-border-default bg-bg-surface md:block"
          style={{ width: 420, flexShrink: 0, overflowY: 'auto', height: '100vh' }}
        >
          <PaperDetail />
        </div>
      )}
    </div>
  );
}
