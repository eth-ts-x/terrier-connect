import apiClient from "./apiClient";
import type { User, PaginatedResponse } from "../types";

export async function getUserDetail(userId: number): Promise<User> {
  const { data } = await apiClient.get(`/users/${userId}/`);
  return data;
}

export async function updateProfile(formData: FormData): Promise<{ user: User }> {
  const { data } = await apiClient.put("/users/profile/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string
): Promise<void> {
  await apiClient.put("/users/change-password/", {
    currentPassword,
    newPassword,
    confirmPassword,
  });
}

export async function getFollowers(
  userId: number,
  page = 1,
  pageSize = 10
): Promise<PaginatedResponse<User>> {
  const { data } = await apiClient.get(`/users/${userId}/followers/`, {
    params: { page, pageSize },
  });
  return data;
}

export async function getFollowing(
  userId: number,
  page = 1,
  pageSize = 10
): Promise<PaginatedResponse<User>> {
  const { data } = await apiClient.get(`/users/${userId}/following/`, {
    params: { page, pageSize },
  });
  return data;
}

export async function followUser(userId: number): Promise<void> {
  await apiClient.post(`/users/${userId}/follow/`);
}

export async function unfollowUser(userId: number): Promise<void> {
  await apiClient.delete(`/users/${userId}/unfollow/`);
}
