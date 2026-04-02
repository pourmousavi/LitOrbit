import { useState } from 'react';
import { X, Send } from 'lucide-react';
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-border-default bg-bg-surface p-5"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-mono text-sm font-medium text-text-primary">Share Paper</h3>
          <button onClick={onClose} className="rounded-full p-1 text-text-tertiary hover:text-text-primary">
            <X size={16} />
          </button>
        </div>

        {/* Paper title */}
        <p className="mb-4 font-serif text-sm text-text-secondary line-clamp-2">{paper.title}</p>

        {/* User select */}
        <div className="mb-3">
          <label className="mb-1.5 block font-mono text-xs text-text-secondary">Share with</label>
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-bg-base px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
          >
            <option value="">Select a lab member...</option>
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name} ({u.email})
              </option>
            ))}
          </select>
        </div>

        {/* Annotation */}
        <div className="mb-4">
          <label className="mb-1.5 block font-mono text-xs text-text-secondary">Note (optional)</label>
          <textarea
            value={annotation}
            onChange={(e) => setAnnotation(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-border-default bg-bg-base px-3 py-2 text-sm text-text-primary outline-none focus:border-accent resize-none"
            placeholder="Add a note for the recipient..."
          />
        </div>

        {/* Submit */}
        <button
          onClick={() => shareMutation.mutate()}
          disabled={!selectedUserId || shareMutation.isPending}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
        >
          <Send size={14} />
          {shareMutation.isPending ? 'Sharing...' : 'Share'}
        </button>

        {shareMutation.isError && (
          <p className="mt-2 text-center text-xs text-danger">Failed to share. Try again.</p>
        )}
      </div>
    </div>
  );
}
