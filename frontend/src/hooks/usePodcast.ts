import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

interface PodcastInfo {
  id: string;
  paper_id: string;
  voice_mode: string;
  audio_url: string;
  duration_seconds: number | null;
  generated_at: string;
}

interface PodcastStatus {
  status: 'not_generated' | 'generating' | 'ready' | 'failed';
  podcast: PodcastInfo | null;
  error?: string;
  estimated_seconds?: number;
}

export function usePodcastStatus(paperId: string | null, voiceMode: string) {
  return useQuery<PodcastStatus>({
    queryKey: ['podcast', paperId, voiceMode],
    queryFn: async () => {
      const { data } = await api.get(`/api/v1/podcasts/${paperId}`, {
        params: { voice_mode: voiceMode },
      });
      return data;
    },
    enabled: !!paperId,
    refetchInterval: (query) => {
      if (query.state.data?.status === 'generating') return 3000;
      return false;
    },
  });
}

export function useGeneratePodcast() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ paperId, voiceMode }: { paperId: string; voiceMode: string }) => {
      const { data } = await api.post(`/api/v1/podcasts/${paperId}/generate`, {
        voice_mode: voiceMode,
      });
      return data;
    },
    onSuccess: (data, variables) => {
      // Immediately set status to generating so the UI shows the spinner
      queryClient.setQueryData(
        ['podcast', variables.paperId, variables.voiceMode],
        { status: 'generating', podcast: null, estimated_seconds: data.estimated_seconds },
      );
      // Also invalidate to start polling
      queryClient.invalidateQueries({ queryKey: ['podcast', variables.paperId] });
    },
  });
}

interface PodcastListItem {
  id: string;
  paper_id: string;
  paper_title: string;
  paper_journal: string;
  voice_mode: string;
  audio_url: string;
  duration_seconds: number | null;
  generated_at: string;
  collections: { id: string; name: string; color: string }[];
}

export function useDeletePodcast() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (podcastId: string) => {
      const { data } = await api.delete(`/api/v1/podcasts/${podcastId}`);
      return data as { status: string; paper_id: string; voice_mode: string };
    },
    onMutate: async (podcastId: string) => {
      // Cancel in-flight refetches
      await queryClient.cancelQueries({ queryKey: ['podcasts', 'list'] });

      // Snapshot previous list
      const previousList = queryClient.getQueryData<PodcastListItem[]>(['podcasts', 'list']);

      // Optimistically remove from the list
      if (previousList) {
        queryClient.setQueryData<PodcastListItem[]>(
          ['podcasts', 'list'],
          previousList.filter((p) => p.id !== podcastId),
        );
      }

      return { previousList };
    },
    onError: (_err, _podcastId, context) => {
      // Rollback on error
      if (context?.previousList) {
        queryClient.setQueryData(['podcasts', 'list'], context.previousList);
      }
    },
    onSettled: (_data, _error, _podcastId, _context) => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: ['podcasts', 'list'] });
    },
    onSuccess: (data) => {
      // Also refresh the paper's podcast status so the generate button reappears
      queryClient.invalidateQueries({ queryKey: ['podcast', data.paper_id] });
    },
  });
}

export function usePodcastList() {
  return useQuery<PodcastListItem[]>({
    queryKey: ['podcasts', 'list'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/podcasts');
      return data;
    },
  });
}
