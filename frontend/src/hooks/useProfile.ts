import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { UserProfile } from '@/types';
import { usePulseSettings } from '@/stores/pulseSettingsStore';

export function useProfile() {
  const query = useQuery<UserProfile>({
    queryKey: ['profile'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/users/me');
      return data;
    },
  });

  // Hydrate display settings from backend whenever profile loads
  const hydrate = usePulseSettings((s) => s.hydrate);
  useEffect(() => {
    if (query.data) {
      hydrate(query.data);
    }
  }, [query.data, hydrate]);

  return query;
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (updates: Partial<UserProfile>) => {
      const { data } = await api.patch('/api/v1/users/me', updates);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
  });
}
