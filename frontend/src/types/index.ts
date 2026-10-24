export type Role = "student" | "faculty" | "admin";

export type AccessType = "free" | "premium";

export type ResourceType =
  | "book"
  | "ebook"
  | "study_material"
  | "research_paper"
  | "journal"
  | "journal_article"
  | "newspaper"
  | "question_paper"
  | "lecture_notes"
  | "thesis"
  | "dissertation"
  | "case_study"
  | "academic_report"
  | "video"
  | "playlist";

export type Difficulty = "beginner" | "intermediate" | "advanced";

export interface User {
  user_id: string;
  email: string;
  student_id?: string | null;
  name: string;
  role: Role;
  department_code?: string | null;
  academic_year?: number | null;
  semester?: number | null;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  tokens: AuthTokens;
  user: User;
}

export interface Department {
  code: string;
  name: string;
  description?: string;
  icon?: string;
  resource_count?: number;
}

export interface Subject {
  code: string;
  name: string;
  department_code: string;
  description?: string;
  resource_count?: number;
}

export interface Topic {
  code: string;
  name: string;
  subject_code: string;
  description?: string;
  resource_count?: number;
}

export interface TaxonomyInfo {
  department?: string | null;
  department_name?: string | null;
  subjects?: string[];
  subject_names?: string[];
  topics?: string[];
  topic_names?: string[];
}

export interface ResourceSummary {
  resource_id: string;
  type: ResourceType;
  title: string;
  subtitle?: string | null;
  description?: string | null;
  authors: string[];
  year?: number | null;
  publisher?: string | null;
  access: AccessType;
  premium_price_usd?: number | null;
  taxonomy: TaxonomyInfo;
  keywords: string[];
  rating_average: number;
  rating_count: number;
  views: number;
  reads: number;
  downloads: number;
  bookmarks: number;
  citation_count?: number | null;
  external_url?: string | null;
  source_name?: string | null;
  youtube_thumbnail?: string | null;
  is_seed_data?: boolean;
}

export interface ResourceDetail extends ResourceSummary {
  content?: {
    full_text?: string | null;
    pdf_url?: string | null;
    sample_text?: string | null;
  };
  has_access?: boolean;
}

export interface SearchFilters {
  query?: string;
  department?: string;
  subject?: string;
  topic?: string;
  types?: ResourceType[];
  year_from?: number;
  year_to?: number;
  difficulty?: Difficulty;
  access?: AccessType;
  author?: string;
  min_rating?: number;
}

export interface SearchResponse {
  items: ResourceSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query?: string;
}
