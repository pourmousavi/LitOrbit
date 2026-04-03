import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { PapersResponse, Paper } from '@/types';

export function usePapers(filters?: { journal?: string; category?: string; search?: string }) {
  return useInfiniteQuery<PapersResponse>({
    queryKey: ['papers', filters],
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string | number> = { page: pageParam as number, per_page: 20 };
      if (filters?.journal) params.journal = filters.journal;
      if (filters?.category) params.category = filters.category;
      if (filters?.search) params.search = filters.search;
      const { data } = await api.get('/api/v1/papers', { params });
      return data;
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.per_page);
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
  });
}

export function usePaper(paperId: string | null) {
  return useQuery<Paper>({
    queryKey: ['paper', paperId],
    queryFn: async () => {
      const { data } = await api.get(`/api/v1/papers/${paperId}`);
      return data;
    },
    enabled: !!paperId,
  });
}
