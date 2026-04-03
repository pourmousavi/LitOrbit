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
