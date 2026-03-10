import apiClient from "./apiClient";
import type { User } from "../types";

export async function login(email: string, password: string): Promise<{ user: User }> {
  const { data } = await apiClient.post("/users/login/", { email, password });
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/users/logout/");
}

export async function register(formData: FormData): Promise<{ user: User }> {
  const { data } = await apiClient.post("/users/register/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get("/users/me/");
  return data;
}

export async function googleLogin(accessToken: string): Promise<{ user: User }> {
  const { data } = await apiClient.post("/users/auth/google/", {
    access_token: accessToken,
  });
  return data;
}
