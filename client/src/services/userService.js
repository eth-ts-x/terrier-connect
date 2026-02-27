import apiClient from "./apiClient";

export const getUserDetail = async (userId) => {
  const response = await apiClient.get(`/users/${userId}/`);
  return response.data;
};

export const updateProfile = async (formData) => {
  const response = await apiClient.put("/users/profile/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
};

export const changePassword = async (formData) => {
  const response = await apiClient.put("/users/change-password/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
};

export const getFollowing = async (userId, params) => {
  const response = await apiClient.get(`/users/${userId}/following/`, { params });
  return response.data;
};

export const getFollowers = async (userId, params) => {
  const response = await apiClient.get(`/users/${userId}/followers/`, { params });
  return response.data;
};

export const followUser = async (userId) => {
  const response = await apiClient.post(`/users/${userId}/follow/`);
  return response.data;
};

export const unfollowUser = async (userId) => {
  const response = await apiClient.delete(`/users/${userId}/unfollow/`);
  return response.data;
};