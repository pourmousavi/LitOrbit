import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export interface NewsItemDetail {
  id: string;
  source_id: string;
  source_name: string;
  source_website: string;
  authority_weight: number;
  url: string;
  canonical_url: string | null;
  title: string;
  excerpt: string | null;
  full_text: string | null;
  full_text_scraped_at: string | null;
  author: string | null;
  published_at: string | null;
  tags: string[];
  categories: string[];
  relevance_score: number | null;
  is_cluster_primary: boolean;
  scholarlib_ref_id: string | null;
  cluster_also_covered_in: Array<{ id: string; url: string; title: string; source_name: string }>;
  created_at: string | null;
}

export function useNewsItem(newsId: string | null) {
  return useQuery<NewsItemDetail>({
    queryKey: ['news-item', newsId],
    queryFn: async () => {
      const { data } = await api.get(`/api/v1/news/${newsId}`);
      return data;
    },
    enabled: !!newsId,
  });
}
