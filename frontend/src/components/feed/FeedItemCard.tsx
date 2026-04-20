import type { FeedItem } from '@/types/feed';
import PaperCard from '@/components/papers/PaperCard';
import NewsCard from '@/components/feed/NewsCard';
import type { Paper } from '@/types';

interface FeedItemCardProps {
  item: FeedItem;
  isSelected?: boolean;
  onSelect?: () => void;
  onToggleFavorite?: () => void;
  onSendToScholarLib?: () => void;
}

/** Adapter: convert a FeedItem (paper type) back to the Paper shape PaperCard expects. */
function feedItemToPaper(item: FeedItem): Paper {
  const p = item.paper!;
  return {
    id: item.item_id,
    doi: p.doi,
    title: item.title,
    authors: p.authors,
    abstract: item.excerpt,
    full_text: null,
    journal: p.journal,
    journal_source: p.journal_source,
    published_date: item.published_at,
    online_date: null,
    early_access: p.early_access,
    url: p.url,
    pdf_path: null,
    keywords: p.keywords,
    categories: p.categories,
    summary: p.summary,
    relevance_score: item.relevance_score,
    score_reasoning: p.score_reasoning,
    created_at: item.created_at,
    created_by_name: null,
    collections: [],
    is_opened: item.user_state.read,
    is_favorite: item.user_state.starred,
    user_rating: item.user_state.rating,
  };
}

export default function FeedItemCard({ item, isSelected, onSelect, onToggleFavorite, onSendToScholarLib }: FeedItemCardProps) {
  if (item.item_type === 'paper' && item.paper) {
    return (
      <PaperCard
        paper={feedItemToPaper(item)}
        isSelected={isSelected}
        onClick={onSelect}
        onToggleFavorite={onToggleFavorite}
        onSendToScholarLib={onSendToScholarLib}
      />
    );
  }

  if (item.item_type === 'news' && item.news) {
    return <NewsCard item={item} onClick={onSelect} />;
  }

  return null;
}
