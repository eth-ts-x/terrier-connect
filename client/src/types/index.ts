/* ── Domain types for Terrier Connect ── */

export interface User {
  id: number;
  email: string;
  display_name: string;
  bio: string;
  avatar_url: string | null;
}

export interface Post {
  post_id: string;
  author_id: number;
  author_display_name: string;
  author_avatar_url: string | null;
  title: string;
  content: string;
  image_url: string | null;
  geolocation: string | null;
  hashtags: string[];
  like_count: number;
  is_liked: boolean;
  create_time: string;
  update_time: string;
}

export interface Comment {
  comment_id: string;
  post_id: string;
  author_id: number;
  author_display_name: string;
  author_avatar_url: string | null;
  content: string;
  parent_id: string | null;
  create_time: string;
  replies: Comment[];
}

export interface Notification {
  notification_id: string;
  user_id: number;
  type: "like" | "comment" | "follow";
  actor_id: number;
  actor_display_name: string;
  actor_avatar_url: string | null;
  target_id: string;
  target_type: "post" | "user";
  message: string;
  is_read: boolean;
  create_time: string;
}

export interface Hashtag {
  id: number;
  hashtag_text: string;
  created_time: string;
}

/* ── API response wrappers ── */

export interface PaginatedResponse<T> {
  results: T[];
  nextCursor?: string | null;
  page?: number;
  pageSize?: number;
  totalItems?: number;
  totalPages?: number;
}

export interface SearchResponse<T> {
  total: number;
  page: number;
  pageSize: number;
  results: T[];
}

export interface LikeStatus {
  liked: boolean;
  like_count: number;
}
