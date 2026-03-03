import apiClient from "./apiClient";
import type { Post, Comment, PaginatedResponse, LikeStatus, SearchResponse } from "../types";

/* ── List / Feed ── */

export async function listPosts(
  flag: "all" | "following" = "all",
  pageSize = 10
): Promise<PaginatedResponse<Post>> {
  const { data } = await apiClient.get("/posts/", { params: { flag, pageSize } });
  return data;
}

/* ── Detail ── */

export async function getPostDetail(postId: string): Promise<Post> {
  const { data } = await apiClient.get(`/posts/${postId}/`);
  return data;
}

/* ── Create / Update / Delete ── */

export async function createPost(formData: FormData): Promise<Post> {
  const { data } = await apiClient.post("/posts/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function updatePost(postId: string, formData: FormData): Promise<Post> {
  const { data } = await apiClient.put(`/posts/${postId}/`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deletePost(postId: string): Promise<void> {
  await apiClient.delete(`/posts/${postId}/`);
}

/* ── Like / Unlike ── */

export async function likePost(postId: string): Promise<LikeStatus> {
  const { data } = await apiClient.post(`/posts/${postId}/like/`);
  return data;
}

export async function unlikePost(postId: string): Promise<LikeStatus> {
  const { data } = await apiClient.delete(`/posts/${postId}/unlike/`);
  return data;
}

export async function getLikeStatus(postId: string): Promise<LikeStatus> {
  const { data } = await apiClient.get(`/posts/${postId}/like-status/`);
  return data;
}

/* ── Comments ── */

export async function getComments(postId: string): Promise<{ results: Comment[] }> {
  const { data } = await apiClient.get(`/posts/${postId}/comments/`);
  return data;
}

export async function addComment(
  postId: string,
  content: string,
  parentId?: string | null
): Promise<Comment> {
  const { data } = await apiClient.post(`/posts/${postId}/comments/add/`, {
    content,
    parent_id: parentId ?? null,
  });
  return data;
}

/* ── Search ── */

export async function searchPosts(
  query: string,
  page = 1,
  pageSize = 10
): Promise<SearchResponse<Post>> {
  const { data } = await apiClient.get("/posts/search/", { params: { query, page, pageSize } });
  return data;
}

export async function searchByTag(
  tag: string,
  page = 1,
  pageSize = 10
): Promise<SearchResponse<Post>> {
  const { data } = await apiClient.get("/posts/by-tag/", { params: { tag, page, pageSize } });
  return data;
}

/* ── Posts by user ── */

export async function getPostsByUser(
  authorId: number,
  pageSize = 10
): Promise<PaginatedResponse<Post>> {
  const { data } = await apiClient.get("/posts/by-user/", {
    params: { author: authorId, pageSize },
  });
  return data;
}
