import { DateTimeTypeDefinition, UUIDDefinition } from "graphql-scalars";
import { gql } from "graphql-tag";

export const typeDefs = gql`
  ${UUIDDefinition}
  ${DateTimeTypeDefinition}

  enum FeedMode {
    GLOBAL
    FOLLOWING
  }

  type User {
    id: Int!
    email: String!
    displayName: String
    bio: String
    avatarUrl: String
  }

  type LikeStatus {
    liked: Boolean!
    likeCount: Int!
  }

  type Post {
    id: UUID!
    authorId: Int!
    author: User!
    authorDisplayName: String
    authorAvatarUrl: String
    title: String!
    content: String!
    imageUrl: String
    geolocation: String
    hashtags: [String!]!
    likeCount: Int!
    likedByViewer: Boolean!
    createdAt: DateTime!
    updatedAt: DateTime!
  }

  type Comment {
    id: UUID!
    postId: UUID!
    authorId: Int!
    author: User!
    authorDisplayName: String
    authorAvatarUrl: String
    content: String!
    parentId: UUID
    createdAt: DateTime!
    replies: [Comment!]!
  }

  type PostConnection {
    items: [Post!]!
    nextCursor: String
  }

  type UserPage {
    page: Int!
    pageSize: Int!
    totalItems: Int!
    totalPages: Int!
    items: [User!]!
  }

  type SearchPage {
    total: Int!
    page: Int!
    pageSize: Int!
    items: [Post!]!
  }

  type HashtagStat {
    text: String!
    count: Int!
  }

  type MutationStatus {
    ok: Boolean!
    message: String!
  }

  input CreatePostInput {
    title: String!
    content: String!
    hashtags: [String!] = []
    geolocation: String
  }

  input UpdatePostInput {
    title: String
    content: String
    hashtags: [String!]
    geolocation: String
  }

  type Query {
    viewer: User
    user(id: Int!): User
    feed(mode: FeedMode = GLOBAL, first: Int = 10): PostConnection!
    userPosts(userId: Int!, first: Int = 10): PostConnection!
    post(id: UUID!): Post
    searchPosts(query: String!, page: Int = 1, pageSize: Int = 10): SearchPage!
    postsByTag(tag: String!, page: Int = 1, pageSize: Int = 10): SearchPage!
    comments(postId: UUID!, first: Int = 50): [Comment!]!
    followers(userId: Int!, page: Int = 1, pageSize: Int = 10): UserPage!
    following(userId: Int!, page: Int = 1, pageSize: Int = 10): UserPage!
    likeStatus(postId: UUID!): LikeStatus!
    popularHashtags(limit: Int = 10): [HashtagStat!]!
  }

  type Mutation {
    createPost(input: CreatePostInput!): Post!
    updatePost(id: UUID!, input: UpdatePostInput!): Post!
    deletePost(id: UUID!): MutationStatus!
    likePost(id: UUID!): LikeStatus!
    unlikePost(id: UUID!): LikeStatus!
    addComment(postId: UUID!, content: String!, parentId: UUID): Comment!
    followUser(userId: Int!): MutationStatus!
    unfollowUser(userId: Int!): MutationStatus!
  }
`;
