import apiClient from "./apiClient";

export const login = async ({ email, password }) => {
  const response = await apiClient.post("/users/login/", { email, password });
  return response.data;
};

export const logout = async () => {
  await apiClient.post("/users/logout/");
};

export const register = async (formData) => {
  const response = await apiClient.post("/users/register/", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
};

export const getMe = async () => {
  const response = await apiClient.get("/users/me/");
  return response.data;
};