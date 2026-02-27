import apiClient from "./apiClient";

export const listPosts = async (params) => {
  const response = await apiClient.get("/posts/", { params });
  return response.data;
};

export const getPostDetail = async (postId) => {
  const response = await apiClient.get(`/posts/${postId}/`);
  return response.data;
};

export const addPost = async (formData) => {
  const response = await apiClient.post("/posts/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
};

export const updatePost = async (postId, data) => {
  const response = await apiClient.put(`/posts/${postId}/`, data);
  return response.data;
};

export const deletePost = async (postId) => {
  const response = await apiClient.delete(`/posts/${postId}/`);
  return response.data;
};

export const getComments = async (postId, params) => {
  const response = await apiClient.get(`/posts/${postId}/comments/`, { params });
  return response.data;
};

export const submitComment = async (postId, content, parentId = null) => {
  const response = await apiClient.post("/posts/comments/", {
    post: postId,
    content,
    parent: parentId,
  });
  return response.data;
};

export const getCommentsByAuthor = async (userId, params) => {
  const response = await apiClient.get("/posts/comments/by-author/", {
    params: { ...params, author: userId },
  });
  return response.data;
};