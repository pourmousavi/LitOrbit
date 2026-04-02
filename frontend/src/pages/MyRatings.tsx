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
      <div className="p-4">
        <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">My Ratings</h1>
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-border-default bg-bg-surface p-4">
              <div className="h-4 w-3/4 rounded bg-bg-elevated" />
              <div className="mt-2 h-3 w-1/4 rounded bg-bg-elevated" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl p-4">
      <h1 className="mb-4 font-mono text-lg font-medium text-text-primary">My Ratings</h1>

      {!ratings?.length ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Star className="mb-3 text-text-tertiary" size={32} />
          <p className="font-mono text-lg text-text-secondary">No ratings yet</p>
          <p className="mt-1 font-mono text-sm text-text-tertiary">
            Rate papers from the feed to build your preference profile
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {ratings.map((item) => (
            <article
              key={item.id}
              className="flex items-center gap-4 rounded-xl border border-border-default bg-bg-surface p-4"
            >
              {/* Score */}
              <span
                className={cn(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-mono text-sm font-medium',
                  getScoreColor(item.rating),
                  item.rating >= 8
                    ? 'bg-score-high/15'
                    : item.rating >= 5
                      ? 'bg-score-mid/15'
                      : 'bg-score-low/15',
                )}
              >
                {item.rating}
              </span>

              {/* Paper info */}
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-serif text-sm font-semibold text-text-primary">
                  {item.paper_title}
                </h3>
                <p className="font-mono text-xs text-text-secondary">
                  {item.paper_journal}
                  {item.rated_at && ` · ${formatDate(item.rated_at)}`}
                </p>
              </div>

              {/* Feedback type */}
              {item.feedback_type && (
                <span className="shrink-0 rounded-md bg-bg-elevated px-2 py-0.5 font-mono text-xs text-text-tertiary">
                  {item.feedback_type}
                </span>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
