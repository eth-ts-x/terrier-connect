import apiClient from "./apiClient";

export const listPosts = async (params) => {
  const response = await apiClient.get("/posts/list_posts/", { params });
  return response.data;
};

export const getPostDetail = async (postId) => {
  const response = await apiClient.get(`/posts/get_post_detail/${postId}/`);
  return response.data;
};

export const addPost = async (formData) => {
  const response = await apiClient.post("/posts/add_post/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
};

export const updatePost = async (postId, data) => {
  const response = await apiClient.put(`/posts/update_post/${postId}/`, data);
  return response.data;
};

export const deletePost = async (postId) => {
  const response = await apiClient.delete(`/posts/delete_post/${postId}/`);
  return response.data;
};

export const getComments = async (postId, params) => {
  const response = await apiClient.get(`/posts/${postId}/comments/`, { params });
  return response.data;
};

export const submitComment = async (postId, content, parentId = null) => {
  const response = await apiClient.post("/posts/comments/create/", {
    post: postId,
    content,
    parent: parentId,
  });
  return response.data;
};

export const getCommentsByAuthor = async (userId, params) => {
  const response = await apiClient.get(`/posts/comments/authors/${userId}/`, {
    params,
  });
  return response.data;
};