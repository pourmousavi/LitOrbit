import { useState } from 'react';
import { X, Send, ChevronDown } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { Paper } from '@/types';

interface ShareModalProps {
  paper: Paper;
  onClose: () => void;
}

interface UserOption {
  id: string;
  full_name: string;
  email: string;
}

export default function ShareModal({ paper, onClose }: ShareModalProps) {
  const [selectedUserId, setSelectedUserId] = useState('');
  const [annotation, setAnnotation] = useState('');
  const queryClient = useQueryClient();

  const { data: users } = useQuery<UserOption[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/users');
      return data;
    },
  });

  const shareMutation = useMutation({
    mutationFn: async () => {
      await api.post('/api/v1/shares', {
        paper_id: paper.id,
        shared_with: selectedUserId,
        annotation: annotation || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shares'] });
      onClose();
    },
  });

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      className="bg-black/60"
      onClick={onClose}
    >
      <div
        className="rounded-2xl border border-border-default bg-bg-surface"
        style={{ width: '100%', maxWidth: 440, padding: 28 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 className="font-mono font-medium text-text-primary" style={{ fontSize: 16 }}>Share Paper</h3>
          <button
            onClick={onClose}
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-text-primary"
            style={{ padding: 6 }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Paper title preview */}
        <div
          className="rounded-xl bg-bg-base border border-border-default"
          style={{ padding: '12px 16px', marginBottom: 20 }}
        >
          <p className="font-sans text-sm text-text-secondary line-clamp-2" style={{ lineHeight: 1.5 }}>
            {paper.title}
          </p>
        </div>

        {/* User select */}
        <div style={{ marginBottom: 16 }}>
          <label className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
            Share with
          </label>
          <div className="relative">
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent appearance-none"
              style={{ width: '100%', padding: '12px 16px', paddingRight: 40 }}
            >
              <option value="">Select a lab member...</option>
              {users?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name} ({u.email})
                </option>
              ))}
            </select>
            <ChevronDown
              size={16}
              className="text-text-tertiary"
              style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
            />
          </div>
        </div>

        {/* Annotation */}
        <div style={{ marginBottom: 24 }}>
          <label className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
            Note <span className="text-text-tertiary">(optional)</span>
          </label>
          <textarea
            value={annotation}
            onChange={(e) => setAnnotation(e.target.value)}
            rows={3}
            className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent"
            style={{ width: '100%', padding: '12px 16px', resize: 'none' }}
            placeholder="Add a note for the recipient..."
          />
        </div>

        {/* Submit */}
        <button
          onClick={() => shareMutation.mutate()}
          disabled={!selectedUserId || shareMutation.isPending}
          className="flex items-center justify-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          style={{ width: '100%', gap: 8, padding: '14px 0' }}
        >
          <Send size={15} />
          {shareMutation.isPending ? 'Sharing...' : 'Share Paper'}
        </button>

        {shareMutation.isError && (
          <p className="font-mono text-xs text-danger" style={{ textAlign: 'center', marginTop: 12 }}>
            Failed to share. Try again.
          </p>
        )}
      </div>
    </div>
  );
}
