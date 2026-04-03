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
  categories: string[];
  summary: string | null;
  relevance_score: number | null;
  score_reasoning: string | null;
  created_at: string | null;
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
  podcast_preference: 'single' | 'dual';
  email_digest_enabled: boolean;
  digest_frequency: 'daily' | 'weekly';
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

export interface Podcast {
  id: string;
  paper_id: string;
  voice_mode: 'single' | 'dual';
  audio_path: string | null;
  duration_seconds: number | null;
  generated_at: string;
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
