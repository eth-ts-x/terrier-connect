import apiClient from "./apiClient";
import type { Notification } from "../types";

export async function getNotifications(pageSize = 20): Promise<{ results: Notification[] }> {
  const { data } = await apiClient.get("/notifications/", { params: { pageSize } });
  return data;
}

export async function markAllRead(): Promise<{ marked: number }> {
  const { data } = await apiClient.post("/notifications/mark-read/");
  return data;
}

export async function getUnreadCount(): Promise<{ count: number }> {
  const { data } = await apiClient.get("/notifications/unread-count/");
  return data;
}
