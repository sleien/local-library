// Types mirroring the backend Pydantic schemas.

export interface User {
  id: number;
  email: string;
  display_name: string;
  is_superuser: boolean;
}

export interface HouseholdSummary {
  id: number;
  name: string;
  role: string;
}

export interface Me {
  user: User;
  households: HouseholdSummary[];
}

export interface AuthConfig {
  allow_registration: boolean;
  oidc_enabled: boolean;
  oidc_display_name: string;
}

export interface LocationNode {
  id: number;
  household_id: number;
  parent_id: number | null;
  name: string;
  kind: string;
  sort_order: number;
  path: string;
  children: LocationNode[];
}

export interface Tag {
  id: number;
  name: string;
  color: string | null;
  source: string;
}

export interface Cover {
  id: number;
  source: string;
  source_url: string | null;
  asset_id: number | null;
  url: string | null;
  width: number | null;
  height: number | null;
  selected: boolean;
}

export interface LookupCover {
  source: string;
  url: string;
  width: number | null;
  height: number | null;
}

export interface LookupResult {
  title: string;
  subtitle: string | null;
  authors: string[];
  isbn10: string | null;
  isbn13: string | null;
  publisher: string | null;
  published_date: string | null;
  page_count: number | null;
  language: string | null;
  description: string | null;
  subjects: string[];
  covers: LookupCover[];
  sources: string[];
}

export interface CopyOut {
  id: number;
  book_id: number;
  location_id: number | null;
  location_path: string | null;
  acquired_date: string | null;
  condition: string | null;
  notes: string | null;
  is_borrowed: boolean;
  borrowed_by: string | null;
}

export interface UserBook {
  status: string;
  rating: number | null;
  review: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface CommentOut {
  id: number;
  body: string;
  user_id: number;
  user_name: string;
  created_at: string;
}

export interface BookSummary {
  id: number;
  title: string;
  subtitle: string | null;
  authors: string[];
  isbn13: string | null;
  cover_url: string | null;
  tags: Tag[];
  copy_count: number;
  my_status: string | null;
}

export interface BookDetail extends BookSummary {
  isbn10: string | null;
  publisher: string | null;
  published_date: string | null;
  page_count: number | null;
  language: string | null;
  description: string | null;
  metadata_source: string | null;
  covers: Cover[];
  copies: CopyOut[];
  comments: CommentOut[];
  my_book: UserBook | null;
}

export interface Person {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  active_loan_count: number;
}

export interface Feedback {
  rating: number | null;
  comment: string | null;
  created_at: string;
}

export interface Loan {
  id: number;
  copy_id: number;
  person_id: number;
  person_name: string;
  book_id: number;
  book_title: string;
  lent_at: string;
  due_date: string | null;
  returned_at: string | null;
  is_active: boolean;
  is_overdue: boolean;
  notes: string | null;
  feedback: Feedback | null;
}

export interface Member {
  user_id: number;
  display_name: string;
  email: string;
  role: string;
}

export interface Invite {
  id: number;
  token: string;
  email: string | null;
  role: string;
  expires_at: string | null;
  accepted_at: string | null;
}

export interface Share {
  id: number;
  viewer_user_id: number;
  viewer_name: string;
  viewer_email: string;
}

export interface ApiToken {
  id: number;
  name: string;
  prefix: string;
  last_used_at: string | null;
  created_at: string;
}

export interface TokenCreated extends ApiToken {
  token: string;
}

export interface BulkAddItem {
  isbn: string;
  status: string;
  book_id: number | null;
  copy_id: number | null;
  title: string | null;
  message: string | null;
}

export interface BulkAddResult {
  items: BulkAddItem[];
  added: number;
  failed: number;
}
