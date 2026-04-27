export type ItemType = 'paper' | 'news';

export type FeedItem = {
  item_type: ItemType;
  item_id: string;
  title: string;
  excerpt: string | null;
  published_at: string | null;
  relevance_score: number | null;
  source_name: string | null;
  source_id: string | null;
  paper?: {
    authors: string[];
    journal: string;
    journal_source: string;
    doi: string | null;
    url: string | null;
    keywords: string[];
    categories: string[];
    early_access: boolean;
    summary: string | null;
    score_reasoning: string | null;
  } | null;
  news?: {
    url: string;
    author: string | null;
    tags: string[];
    categories: string[];
    scholarlib_ref_id: string | null;
    cluster_also_covered_in: Array<{ source_name: string; url: string }>;
  } | null;
  user_state: {
    starred: boolean;
    read: boolean;
    rating: number | string | null;
    sent_to_scholarlib: boolean;
  };
  cross_links: Array<{
    target_type: ItemType;
    target_id: string;
    target_title: string;
    similarity: number;
  }>;
  created_at: string | null;
};

export type FeedFilters = {
  type: 'all' | 'papers' | 'news';
  sources: string[];
  date_from: string | null;
  date_to: string | null;
  min_relevance: number | null;
  sort: 'relevance' | 'date_desc' | 'date_asc';
  search: string | null;
};

export type FeedResponse = {
  items: FeedItem[];
  facets: {
    by_type: { papers: number; news: number };
  };
  page: number;
  size: number;
  total: number;
};

export type NewsSource = {
  id: string;
  name: string;
  feed_url: string;
  website_url: string;
  authority_weight: number;
  enabled: boolean;
  per_source_daily_cap: number;
  use_proxy: boolean;
  last_fetched_at: string | null;
  last_fetch_status: string | null;
  last_fetch_error: string | null;
};
