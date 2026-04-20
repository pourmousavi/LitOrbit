import { useInfiniteQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { FeedResponse, FeedFilters } from '@/types/feed';

const PAGE_SIZE = 25;

export function useFeed(filters: Partial<FeedFilters>, enabled = true) {
  return useInfiniteQuery<FeedResponse>({
    queryKey: ['feed', filters],
    enabled,
    queryFn: async ({ pageParam = 1 }) => {
      const params: Record<string, string> = {
        page: String(pageParam),
        size: String(PAGE_SIZE),
      };
      if (filters.type && filters.type !== 'all') params.type = filters.type;
      if (filters.sort) params.sort = filters.sort;
      if (filters.search) params.search = filters.search;
      if (filters.min_relevance != null) params.min_relevance = String(filters.min_relevance);
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.sources && filters.sources.length > 0) {
        params.sources = filters.sources.join(',');
      }

      const { data } = await api.get('/api/v1/feed', { params });
      return data;
    },
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.size);
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
    initialPageParam: 1,
  });
}
