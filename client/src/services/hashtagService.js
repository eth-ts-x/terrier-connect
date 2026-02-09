import apiClient from "./apiClient";

export const getPopularHashtags = async (params) => {
  const response = await apiClient.get("/hashtags/get_popular_hashtags/", {
    params,
  });
  return response.data;
};

export const getPostHashtagsByPostId = async (postId, params) => {
  const response = await apiClient.get(
    `/hashtags/get_post_hashtags_by_post_id/${postId}/`,
    { params }
  );
  return response.data;
};