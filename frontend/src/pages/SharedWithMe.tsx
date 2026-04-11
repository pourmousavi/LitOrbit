import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Mail, MailOpen, Share2 } from 'lucide-react';
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
      <div className="px-3 pt-6 pb-4 md:px-6 md:py-8">
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-5">
            Shared with Me
          </h1>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
                <div className="h-5 w-3/4 rounded bg-bg-elevated" />
                <div className="mt-3 h-4 w-1/2 rounded bg-bg-elevated" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 pt-6 pb-4 md:px-6 md:py-8">
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-5">
          Shared with Me
        </h1>

        {!shares?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
            <Share2 className="text-text-tertiary" size={40} />
            <p style={{ marginTop: 16, fontSize: 18 }} className="font-mono text-text-secondary">Nothing shared yet</p>
            <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
              Papers shared with you will appear here
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {shares.map((share) => (
              <article
                key={share.id}
                className={cn(
                  'rounded-2xl border border-border-default bg-bg-surface transition cursor-pointer hover:border-border-strong',
                  !share.is_read && 'border-l-[3px] border-l-accent',
                )}
                style={{ padding: 14 }}
                onClick={() => {
                  if (!share.is_read) markRead.mutate(share.id);
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                    {share.is_read ? (
                      <MailOpen size={16} className="text-text-tertiary shrink-0" />
                    ) : (
                      <Mail size={16} className="text-accent shrink-0" />
                    )}
                    <span className="font-mono text-sm text-text-secondary truncate">
                      From <strong className="text-text-primary">{share.sharer_name}</strong> &middot; {formatDate(share.shared_at)}
                    </span>
                  </div>
                  <span className="hidden rounded-lg bg-bg-elevated font-mono text-xs text-text-secondary md:inline" style={{ padding: '4px 10px', flexShrink: 0 }}>
                    {share.paper.journal}
                  </span>
                </div>

                <h3 className="font-sans font-semibold text-text-primary" style={{ fontSize: 16, lineHeight: 1.4 }}>
                  {share.paper.title}
                </h3>

                {share.annotation && (
                  <div className="rounded-xl bg-accent-subtle" style={{ marginTop: 12, padding: '12px 16px' }}>
                    <p className="text-sm text-text-secondary italic">&ldquo;{share.annotation}&rdquo;</p>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
