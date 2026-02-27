import apiClient from "./apiClient";

export const getPopularHashtags = async (params) => {
  const response = await apiClient.get("/hashtags/popular/", { params });
  return response.data;
};

export const getPostHashtagsByPostId = async (postId, params) => {
  const response = await apiClient.get(`/hashtags/by-post/${postId}/`, { params });
  return response.data;
};