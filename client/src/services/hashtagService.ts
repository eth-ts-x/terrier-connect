import apiClient from "./apiClient";
import type { Hashtag } from "../types";

export async function getPopularHashtags(limit = 10): Promise<{ hashtag_text: string; count: number }[]> {
  const { data } = await apiClient.get("/hashtags/popular/", { params: { limit } });
  return data;
}

export async function searchHashtags(text: string): Promise<Hashtag[]> {
  const { data } = await apiClient.get("/hashtags/search/", {
    params: { hashtag_text: text },
  });
  return data;
}
