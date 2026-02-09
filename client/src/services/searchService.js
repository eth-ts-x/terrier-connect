import apiClient from "./apiClient";

export const listPostsByTag = async (params) => {
  const response = await apiClient.get("/posts/list_posts_by_tag/", { params });
  return response.data;
};

export const fullTextSearch = async (params) => {
  const response = await apiClient.get("/posts/full_text_search/", { params });
  return response.data;
};