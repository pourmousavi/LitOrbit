import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import type { PulseData } from '@/types';

export function useEngagement() {
  return useQuery<PulseData>({
    queryKey: ['engagement', 'pulse'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/engagement/pulse');
      return data;
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
    refetchInterval: 10 * 60 * 1000,
  });
}
