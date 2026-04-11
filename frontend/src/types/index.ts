export interface Paper {
  id: string;
  doi: string | null;
  title: string;
  authors: string[];
  abstract: string | null;
  full_text: string | null;
  journal: string;
  journal_source: string;
  published_date: string | null;
  online_date: string | null;
  early_access: boolean;
  url: string | null;
  pdf_path: string | null;
  keywords: string[];
  categories: string[];
  summary: string | null;
  relevance_score: number | null;
  score_reasoning: string | null;
  created_at: string | null;
  created_by_name: string | null;
  collections?: { id: string; name: string; color: string }[];
  is_opened?: boolean;
  is_favorite?: boolean;
  user_rating?: number | null;
}

export interface PaperSummary {
  research_gap: string;
  methodology: string;
  key_findings: string;
  relevance_to_energy_group: string;
  suggested_action: 'read_fully' | 'skim' | 'monitor';
  categories: string[];
}

export interface PapersResponse {
  papers: Paper[];
  total: number;
  page: number;
  per_page: number;
}

export interface UserProfile {
  id: string;
  full_name: string;
  role: 'admin' | 'researcher';
  email: string;
  interest_keywords: string[];
  interest_categories: string[];
  interest_vector: Record<string, number>;
  category_weights: Record<string, number>;
  podcast_preference: 'single' | 'dual';
  email_digest_enabled: boolean;
  digest_frequency: 'daily' | 'weekly';
  digest_day: string;
  digest_podcast_enabled: boolean;
  digest_podcast_voice_mode: 'single' | 'dual';
  digest_top_papers: number | null;
  scoring_prompt: string | null;
  single_voice_prompt: string | null;
  dual_voice_prompt: string | null;
  single_voice_id: string | null;
  dual_voice_alex_id: string | null;
  dual_voice_sam_id: string | null;
  podcast_feed_enabled: boolean;
  podcast_feed_token: string | null;
  podcast_feed_title: string | null;
  podcast_feed_description: string | null;
  podcast_feed_author: string | null;
  podcast_feed_cover_url: string | null;
}

export interface ReferencePaper {
  id: string;
  title: string;
  abstract_preview: string | null;
  doi: string | null;
  source: 'pdf_upload' | 'doi_lookup' | 'manual';
  has_embedding: boolean;
  created_at: string | null;
}

export interface Rating {
  id: string;
  paper_id: string;
  user_id: string;
  rating: number;
  feedback_type: string | null;
  feedback_note: string | null;
  rated_at: string;
}

export interface RatingResponse {
  rating: Rating;
  follow_up_question: string | null;
  follow_up_options: string[] | null;
}

export interface DigestPaper {
  id: string;
  title: string;
  journal: string;
  relevance_score: number | null;
  is_favorite: boolean;
}

export interface Podcast {
  id: string;
  paper_id: string | null;
  voice_mode: 'single' | 'dual';
  podcast_type: 'paper' | 'digest';
  audio_path: string | null;
  duration_seconds: number | null;
  generated_at: string;
  digest_papers?: DigestPaper[];
}

export interface Share {
  id: string;
  paper_id: string;
  shared_by: string;
  shared_with: string;
  annotation: string | null;
  is_read: boolean;
  shared_at: string;
  paper?: Paper;
  sharer_name?: string;
}
