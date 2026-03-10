import { DateTimeResolver, UUIDResolver } from "graphql-scalars";

import type {
  DjangoAPI,
  GatewayComment,
  GatewayLikeStatus,
  GatewayPost,
  GatewayUser,
} from "../datasources/DjangoAPI.js";

interface AppContext {
  dataSources: {
    djangoAPI: DjangoAPI;
  };
  loaders: {
    userById: {
      load: (id: number) => Promise<GatewayUser>;
    };
    likeStatusByPostId: {
      load: (postId: string) => Promise<GatewayLikeStatus>;
    };
  };
}

export const resolvers = {
  UUID: UUIDResolver,
  DateTime: DateTimeResolver,

  Query: {
    viewer: async (_parent: unknown, _args: unknown, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.getViewer();
    },

    user: async (_parent: unknown, { id }: { id: number }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.getUser(id);
    },

    feed: async (
      _parent: unknown,
      { mode = "GLOBAL", first = 10 }: { mode?: "GLOBAL" | "FOLLOWING"; first?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.listPosts(mode === "FOLLOWING" ? "following" : "all", first);
    },

    userPosts: async (
      _parent: unknown,
      { userId, first = 10 }: { userId: number; first?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.getUserPosts(userId, first);
    },

    post: async (_parent: unknown, { id }: { id: string }, { dataSources }: AppContext) => {
      try {
        return await dataSources.djangoAPI.getPost(id);
      } catch {
        return null;
      }
    },

    searchPosts: async (
      _parent: unknown,
      { query, page = 1, pageSize = 10 }: { query: string; page?: number; pageSize?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.searchPosts(query, page, pageSize);
    },

    postsByTag: async (
      _parent: unknown,
      { tag, page = 1, pageSize = 10 }: { tag: string; page?: number; pageSize?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.getPostsByTag(tag, page, pageSize);
    },

    comments: async (
      _parent: unknown,
      { postId, first = 50 }: { postId: string; first?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.getComments(postId, first);
    },

    followers: async (
      _parent: unknown,
      { userId, page = 1, pageSize = 10 }: { userId: number; page?: number; pageSize?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.getFollowers(userId, page, pageSize);
    },

    following: async (
      _parent: unknown,
      { userId, page = 1, pageSize = 10 }: { userId: number; page?: number; pageSize?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.getFollowing(userId, page, pageSize);
    },

    likeStatus: async (_parent: unknown, { postId }: { postId: string }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.getLikeStatus(postId);
    },

    popularHashtags: async (
      _parent: unknown,
      { limit = 10 }: { limit?: number },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.getPopularHashtags(limit);
    },
  },

  Mutation: {
    createPost: async (
      _parent: unknown,
      { input }: { input: { title: string; content: string; hashtags?: string[]; geolocation?: string | null } },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.createPost(input);
    },

    updatePost: async (
      _parent: unknown,
      { id, input }: { id: string; input: { title?: string | null; content?: string | null; hashtags?: string[] | null; geolocation?: string | null } },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.updatePost(id, input);
    },

    deletePost: async (_parent: unknown, { id }: { id: string }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.deletePost(id);
    },

    likePost: async (_parent: unknown, { id }: { id: string }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.likePost(id);
    },

    unlikePost: async (_parent: unknown, { id }: { id: string }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.unlikePost(id);
    },

    addComment: async (
      _parent: unknown,
      { postId, content, parentId }: { postId: string; content: string; parentId?: string | null },
      { dataSources }: AppContext,
    ) => {
      return dataSources.djangoAPI.addComment(postId, content, parentId);
    },

    followUser: async (_parent: unknown, { userId }: { userId: number }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.followUser(userId);
    },

    unfollowUser: async (_parent: unknown, { userId }: { userId: number }, { dataSources }: AppContext) => {
      return dataSources.djangoAPI.unfollowUser(userId);
    },
  },

  UserPage: {
    items: (page: { items: GatewayUser[] }) => page.items,
  },

  SearchPage: {
    items: (page: { items: GatewayPost[] }) => page.items,
  },

  PostConnection: {
    items: (connection: { items: GatewayPost[] }) => connection.items,
  },

  Post: {
    author: async (post: GatewayPost, _args: unknown, { loaders }: AppContext) => {
      return loaders.userById.load(post.authorId);
    },

    likeCount: async (post: GatewayPost, _args: unknown, { loaders }: AppContext) => {
      if (typeof post.likeCount === "number") {
        return post.likeCount;
      }

      const likeStatus = await loaders.likeStatusByPostId.load(post.id);
      return likeStatus.likeCount;
    },

    likedByViewer: async (post: GatewayPost, _args: unknown, { loaders }: AppContext) => {
      if (typeof post.likedByViewer === "boolean") {
        return post.likedByViewer;
      }

      const likeStatus = await loaders.likeStatusByPostId.load(post.id);
      return likeStatus.liked;
    },
  },

  Comment: {
    author: async (comment: GatewayComment, _args: unknown, { loaders }: AppContext) => {
      return loaders.userById.load(comment.authorId);
    },
  },
};
