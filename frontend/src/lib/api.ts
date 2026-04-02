import axios from 'axios';
import { supabase } from './supabase';

const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Inject auth token on every request
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 → redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;
