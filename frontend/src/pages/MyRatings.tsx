import { useQuery } from '@tanstack/react-query';
import { Star } from 'lucide-react';
import api from '@/lib/api';
import { cn, getScoreColor, formatDate } from '@/lib/utils';

interface RatingItem {
  id: string;
  paper_id: string;
  paper_title: string;
  paper_journal: string;
  rating: number;
  feedback_type: string | null;
  rated_at: string | null;
}

export default function MyRatings() {
  const { data: ratings, isLoading } = useQuery<RatingItem[]>({
    queryKey: ['ratings', 'history'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/ratings/history');
      return data;
    },
  });

  if (isLoading) {
    return (
      <div className="px-3 py-4 md:px-6 md:py-8">
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-5">
            My Ratings
          </h1>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="animate-pulse rounded-2xl border border-border-default bg-bg-surface" style={{ padding: 20 }}>
                <div className="h-5 w-3/4 rounded bg-bg-elevated" />
                <div className="mt-3 h-4 w-1/4 rounded bg-bg-elevated" />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-4 md:px-6 md:py-8">
      <div style={{ maxWidth: 680, margin: '0 auto' }}>
        <h1 style={{ fontWeight: 600 }} className="font-mono text-text-primary text-xl mb-5">
          My Ratings
        </h1>

        {!ratings?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 80 }}>
            <Star className="text-text-tertiary" size={40} />
            <p style={{ marginTop: 16, fontSize: 18 }} className="font-mono text-text-secondary">No ratings yet</p>
            <p style={{ marginTop: 6 }} className="font-mono text-sm text-text-tertiary">
              Rate papers from the feed to build your preference profile
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {ratings.map((item) => (
              <article
                key={item.id}
                className="rounded-2xl border border-border-default bg-bg-surface overflow-hidden"
                style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 12 }}
              >
                {/* Score */}
                <span
                  className={cn(
                    'flex items-center justify-center rounded-xl font-mono text-base font-semibold',
                    getScoreColor(item.rating),
                    item.rating >= 8
                      ? 'bg-score-high/15'
                      : item.rating >= 5
                        ? 'bg-score-mid/15'
                        : 'bg-score-low/15',
                  )}
                  style={{ width: 42, height: 42, flexShrink: 0 }}
                >
                  {item.rating}
                </span>

                {/* Paper info */}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <h3 className="font-sans font-semibold text-text-primary line-clamp-2" style={{ fontSize: 14, lineHeight: 1.4 }}>
                    {item.paper_title}
                  </h3>
                  <p className="font-mono text-xs text-text-secondary truncate" style={{ marginTop: 4 }}>
                    {item.paper_journal}
                    {item.rated_at && ` · ${formatDate(item.rated_at)}`}
                    {item.feedback_type && ` · ${item.feedback_type}`}
                  </p>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
