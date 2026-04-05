import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { ReferencePaper } from '@/types';

export function useReferencePapers() {
  return useQuery<ReferencePaper[]>({
    queryKey: ['reference-papers'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/reference-papers');
      return data;
    },
  });
}

export function useUploadReferencePaper() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const { data } = await api.post('/api/v1/reference-papers/upload-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data as { status: string; id: string; title: string; has_embedding: boolean; warning?: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reference-papers'] });
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
  });
}

export function useAddReferencePaperByDOI() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (doi: string) => {
      const { data } = await api.post('/api/v1/reference-papers/doi-lookup', { doi });
      return data as { status: string; id: string; title: string; has_embedding: boolean; warning?: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reference-papers'] });
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
  });
}

export function useAddReferencePaperManual() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (entry: { title: string; abstract?: string }) => {
      const { data } = await api.post('/api/v1/reference-papers/manual', entry);
      return data as { status: string; id: string; title: string; has_embedding: boolean; warning?: string };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reference-papers'] });
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
  });
}

export function useDeleteReferencePaper() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.delete(`/api/v1/reference-papers/${id}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reference-papers'] });
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    },
  });
}
