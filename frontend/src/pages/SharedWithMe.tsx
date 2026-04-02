import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, MailOpen } from 'lucide-react';
import api from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { cn } from '@/lib/utils';

interface ShareItem {
  id: string;
  paper: {
    id: string;
    title: string;
    journal: string;
    authors: string[];
    abstract: string | null;
  };
  sharer_name: string;
  annotation: string | null;
  is_read: boolean;
  shared_at: string | null;
}

export default function SharedWithMe() {
  const queryClient = useQueryClient();

  const { data: shares, isLoading } = useQuery<ShareItem[]>({
    queryKey: ['shares', 'inbox'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/shares/inbox');
      return data;
    },
  });

  const markRead = useMutation({
    mutationFn: async (shareId: string) => {
      await api.patch(`/api/v1/shares/${shareId}/read`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shares', 'inbox'] });
    },
  });

  if (isLoading) {
    return (
      <div className="p-4">
        <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Shared with Me</h1>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-border-default bg-bg-surface p-4">
              <div className="h-4 w-3/4 rounded bg-bg-elevated" />
              <div className="mt-2 h-3 w-1/2 rounded bg-bg-elevated" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">Shared with Me</h1>

      {!shares?.length ? (
        <div className="flex flex-col items-center justify-center py-20">
          <p className="font-mono text-lg text-text-secondary">Nothing shared yet</p>
          <p className="mt-1 font-mono text-sm text-text-tertiary">
            Papers shared with you will appear here
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {shares.map((share) => (
            <article
              key={share.id}
              className={cn(
                'rounded-xl border border-border-default bg-bg-surface p-4 transition',
                !share.is_read && 'border-l-2 border-l-accent',
              )}
              onClick={() => {
                if (!share.is_read) markRead.mutate(share.id);
              }}
            >
              <div className="mb-2 flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {share.is_read ? (
                    <MailOpen size={14} className="text-text-tertiary" />
                  ) : (
                    <Mail size={14} className="text-accent" />
                  )}
                  <span className="font-mono text-xs text-text-secondary">
                    From {share.sharer_name} · {formatDate(share.shared_at)}
                  </span>
                </div>
                <span className="rounded-md bg-bg-elevated px-2 py-0.5 font-mono text-xs text-text-secondary">
                  {share.paper.journal}
                </span>
              </div>

              <h3 className="mb-1 font-serif text-sm font-semibold text-text-primary">
                {share.paper.title}
              </h3>

              {share.annotation && (
                <div className="mt-2 rounded-md bg-accent-subtle px-3 py-2">
                  <p className="text-sm text-text-secondary italic">"{share.annotation}"</p>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
