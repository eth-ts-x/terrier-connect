import { RESTDataSource } from "@apollo/datasource-rest";
import { context, propagation } from "@opentelemetry/api";

export interface GatewayUser {
  id: number;
  email: string;
  displayName: string | null;
  bio: string | null;
  avatarUrl: string | null;
}

export interface GatewayLikeStatus {
  liked: boolean;
  likeCount: number;
}

export interface GatewayPost {
  id: string;
  authorId: number;
  authorDisplayName: string | null;
  authorAvatarUrl: string | null;
  title: string;
  content: string;
  imageUrl: string | null;
  geolocation: string | null;
  hashtags: string[];
  likeCount?: number;
  likedByViewer?: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface GatewayComment {
  id: string;
  postId: string;
  authorId: number;
  authorDisplayName: string | null;
  authorAvatarUrl: string | null;
  content: string;
  parentId: string | null;
  createdAt: string;
  replies: GatewayComment[];
}

export interface GatewayPostConnection {
  items: GatewayPost[];
  nextCursor: string | null;
}

export interface GatewayUserPage {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  items: GatewayUser[];
}

export interface GatewaySearchPage {
  total: number;
  page: number;
  pageSize: number;
  items: GatewayPost[];
}

export interface GatewayHashtagStat {
  text: string;
  count: number;
}

interface CreatePostInput {
  title: string;
  content: string;
  hashtags?: string[];
  geolocation?: string | null;
}

interface UpdatePostInput {
  title?: string | null;
  content?: string | null;
  hashtags?: string[] | null;
  geolocation?: string | null;
}

type JsonObject = Record<string, unknown>;

export class DjangoAPI extends RESTDataSource {
  override baseURL: string;
  private readonly authorization: string;
  private readonly cookie: string;
  private readonly xRequestId: string;
  private readonly traceparent: string;

  constructor(options: {
    baseURL: string;
    authorization?: string;
    cookie?: string;
    xRequestId?: string;
    traceparent?: string;
  }) {
    super();
    this.baseURL = options.baseURL;
    this.authorization = options.authorization ?? "";
    this.cookie = options.cookie ?? "";
    this.xRequestId = options.xRequestId ?? "";
    this.traceparent = options.traceparent ?? "";
  }

  override resolveURL(path: string, request: any) {
    const relativePath = path.startsWith("/") ? path.slice(1) : path;
    return super.resolveURL(relativePath, request);
  }

  override willSendRequest(_path: string, request: any): void {
    request.headers = request.headers ?? {};

    if (this.authorization) {
      request.headers.authorization = this.authorization;
    }

    if (this.cookie) {
      request.headers.cookie = this.cookie;
    }

    if (this.xRequestId) {
      request.headers["x-request-id"] = this.xRequestId;
    }

    propagation.inject(context.active(), request.headers);

    if (!request.headers.traceparent && this.traceparent) {
      request.headers.traceparent = this.traceparent;
    }
  }

  async getViewer(): Promise<GatewayUser | null> {
    try {
      const response = this.asObject(await this.get("/users/me/"));
      return this.mapUser(response);
    } catch {
      return null;
    }
  }

  async getUser(userId: number): Promise<GatewayUser> {
    const response = this.asObject(await this.get(`/users/${userId}/`));
    return this.mapUser(response);
  }

  async getFollowers(userId: number, page = 1, pageSize = 10): Promise<GatewayUserPage> {
    const response = this.asObject(
      await this.get(`/users/${userId}/followers/`, {
        params: {
          page: String(page),
          pageSize: String(pageSize),
        },
      }),
    );

    return this.mapUserPage(response);
  }

  async getFollowing(userId: number, page = 1, pageSize = 10): Promise<GatewayUserPage> {
    const response = this.asObject(
      await this.get(`/users/${userId}/following/`, {
        params: {
          page: String(page),
          pageSize: String(pageSize),
        },
      }),
    );

    return this.mapUserPage(response);
  }

  async listPosts(flag: "all" | "following", pageSize = 10): Promise<GatewayPostConnection> {
    const response = this.asObject(
      await this.get("/posts/", {
        params: {
          flag,
          pageSize: String(pageSize),
        },
      }),
    );

    return {
      items: this.asArray(response.results).map((item) => this.mapPost(this.asObject(item))),
      nextCursor: this.asNullableString(response.nextCursor),
    };
  }

  async getUserPosts(userId: number, pageSize = 10): Promise<GatewayPostConnection> {
    const response = this.asObject(
      await this.get("/posts/by-user/", {
        params: {
          author: String(userId),
          pageSize: String(pageSize),
        },
      }),
    );

    return {
      items: this.asArray(response.results).map((item) => this.mapPost(this.asObject(item))),
      nextCursor: this.asNullableString(response.nextCursor),
    };
  }

  async getPost(postId: string): Promise<GatewayPost> {
    const response = this.asObject(await this.get(`/posts/${postId}/`));
    return this.mapPost(response);
  }

  async createPost(input: CreatePostInput): Promise<GatewayPost> {
    const response = this.asObject(
      await this.post("/posts/", {
        body: this.serializePostInput(input),
      }),
    );

    return this.mapPost(response);
  }

  async updatePost(postId: string, input: UpdatePostInput): Promise<GatewayPost> {
    const response = this.asObject(
      await this.put(`/posts/${postId}/`, {
        body: this.serializePostInput(input),
      }),
    );

    return this.mapPost(response);
  }

  async deletePost(postId: string): Promise<{ ok: boolean; message: string }> {
    try {
      const response = this.asObject(await this.delete(`/posts/${postId}/`));
      return {
        ok: true,
        message: this.asString(response.message) ?? "Post deleted.",
      };
    } catch {
      return {
        ok: true,
        message: "Post deleted.",
      };
    }
  }

  async getLikeStatus(postId: string): Promise<GatewayLikeStatus> {
    const response = this.asObject(await this.get(`/posts/${postId}/like-status/`));
    return {
      liked: this.asBoolean(response.liked) ?? false,
      likeCount: this.asNumber(response.like_count) ?? 0,
    };
  }

  async likePost(postId: string): Promise<GatewayLikeStatus> {
    const response = this.asObject(await this.post(`/posts/${postId}/like/`));
    return {
      liked: this.asBoolean(response.liked) ?? true,
      likeCount: this.asNumber(response.like_count) ?? 0,
    };
  }

  async unlikePost(postId: string): Promise<GatewayLikeStatus> {
    const response = this.asObject(await this.delete(`/posts/${postId}/unlike/`));
    return {
      liked: this.asBoolean(response.liked) ?? false,
      likeCount: this.asNumber(response.like_count) ?? 0,
    };
  }

  async getComments(postId: string, pageSize = 50): Promise<GatewayComment[]> {
    const response = this.asObject(
      await this.get(`/posts/${postId}/comments/`, {
        params: {
          pageSize: String(pageSize),
        },
      }),
    );

    return this.asArray(response.results).map((item) => this.mapComment(this.asObject(item)));
  }

  async addComment(postId: string, content: string, parentId?: string | null): Promise<GatewayComment> {
    const response = this.asObject(
      await this.post(`/posts/${postId}/comments/add/`, {
        body: {
          content,
          parent_id: parentId ?? null,
        },
      }),
    );

    return this.mapComment(response);
  }

  async searchPosts(query: string, page = 1, pageSize = 10): Promise<GatewaySearchPage> {
    const response = this.asObject(
      await this.get("/posts/search/", {
        params: {
          query,
          page: String(page),
          pageSize: String(pageSize),
        },
      }),
    );

    return this.mapSearchPage(response);
  }

  async getPostsByTag(tag: string, page = 1, pageSize = 10): Promise<GatewaySearchPage> {
    const response = this.asObject(
      await this.get("/posts/by-tag/", {
        params: {
          tag,
          page: String(page),
          pageSize: String(pageSize),
        },
      }),
    );

    return this.mapSearchPage(response);
  }

  async getPopularHashtags(limit = 10): Promise<GatewayHashtagStat[]> {
    const response = await this.get("/hashtags/popular/", {
      params: {
        limit: String(limit),
      },
    });

    return this.asArray(response).map((item) => {
      const hashtag = this.asObject(item);
      return {
        text: this.asString(hashtag.hashtag_text) ?? "",
        count: this.asNumber(hashtag.count) ?? 0,
      };
    });
  }

  async followUser(userId: number): Promise<{ ok: boolean; message: string }> {
    const response = this.asObject(await this.post(`/users/${userId}/follow/`));
    return {
      ok: true,
      message: this.asString(response.message) ?? "Followed user.",
    };
  }

  async unfollowUser(userId: number): Promise<{ ok: boolean; message: string }> {
    try {
      const response = this.asObject(await this.delete(`/users/${userId}/unfollow/`));
      return {
        ok: true,
        message: this.asString(response.message) ?? "Unfollowed user.",
      };
    } catch {
      return {
        ok: true,
        message: "Unfollowed user.",
      };
    }
  }

  private serializePostInput(input: CreatePostInput | UpdatePostInput): JsonObject {
    return {
      title: input.title ?? undefined,
      content: input.content ?? undefined,
      geolocation: input.geolocation ?? undefined,
      hashtags: input.hashtags ? JSON.stringify(input.hashtags) : undefined,
    };
  }

  private mapUserPage(response: JsonObject): GatewayUserPage {
    return {
      page: this.asNumber(response.page) ?? 1,
      pageSize: this.asNumber(response.pageSize) ?? 10,
      totalItems: this.asNumber(response.totalItems) ?? 0,
      totalPages: this.asNumber(response.totalPages) ?? 0,
      items: this.asArray(response.results).map((item) => this.mapUser(this.asObject(item))),
    };
  }

  private mapSearchPage(response: JsonObject): GatewaySearchPage {
    return {
      total: this.asNumber(response.total) ?? 0,
      page: this.asNumber(response.page) ?? 1,
      pageSize: this.asNumber(response.pageSize) ?? 10,
      items: this.asArray(response.results).map((item) => this.mapPost(this.asObject(item))),
    };
  }

  private mapUser(response: JsonObject): GatewayUser {
    return {
      id: this.asNumber(response.id) ?? 0,
      email: this.asString(response.email) ?? "",
      displayName: this.asNullableString(response.display_name),
      bio: this.asNullableString(response.bio),
      avatarUrl: this.asNullableString(response.avatar_url),
    };
  }

  private mapPost(response: JsonObject): GatewayPost {
    return {
      id: this.asString(response.post_id) ?? this.asString(response.id) ?? "",
      authorId: this.asNumber(response.author_id) ?? this.asNumber(response.author) ?? 0,
      authorDisplayName: this.asNullableString(response.author_display_name),
      authorAvatarUrl: this.asNullableString(response.author_avatar_url),
      title: this.asString(response.title) ?? "",
      content: this.asString(response.content) ?? "",
      imageUrl: this.asNullableString(response.image_url),
      geolocation: this.asNullableString(response.geolocation),
      hashtags: this.asStringArray(response.hashtags),
      likeCount: this.asNumber(response.like_count) ?? undefined,
      likedByViewer: this.asBoolean(response.is_liked) ?? undefined,
      createdAt: this.asString(response.create_time) ?? new Date(0).toISOString(),
      updatedAt:
        this.asString(response.update_time) ?? this.asString(response.create_time) ?? new Date(0).toISOString(),
    };
  }

  private mapComment(response: JsonObject): GatewayComment {
    return {
      id: this.asString(response.comment_id) ?? this.asString(response.id) ?? "",
      postId: this.asString(response.post_id) ?? this.asString(response.post) ?? "",
      authorId: this.asNumber(response.author_id) ?? this.asNumber(response.author) ?? 0,
      authorDisplayName: this.asNullableString(response.author_display_name),
      authorAvatarUrl: this.asNullableString(response.author_avatar_url),
      content: this.asString(response.content) ?? "",
      parentId: this.asNullableString(response.parent_id),
      createdAt: this.asString(response.create_time) ?? new Date(0).toISOString(),
      replies: this.asArray(response.replies).map((item) => this.mapComment(this.asObject(item))),
    };
  }

  private asObject(value: unknown): JsonObject {
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      return value as JsonObject;
    }

    return {};
  }

  private asArray(value: unknown): unknown[] {
    return Array.isArray(value) ? value : [];
  }

  private asString(value: unknown): string | null {
    return typeof value === "string" ? value : null;
  }

  private asNullableString(value: unknown): string | null {
    if (typeof value === "string") {
      return value.trim() === "" ? null : value;
    }

    return null;
  }

  private asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) {
      return [];
    }

    return value.filter((item): item is string => typeof item === "string");
  }

  private asNumber(value: unknown): number | null {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (typeof value === "string" && value.trim() !== "") {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    return null;
  }

  private asBoolean(value: unknown): boolean | null {
    if (typeof value === "boolean") {
      return value;
    }

    return null;
  }
}
