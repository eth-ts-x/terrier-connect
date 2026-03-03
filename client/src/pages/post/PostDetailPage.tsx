import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  Avatar,
  Chip,
  IconButton,
  Card,
  CardContent,
  CardMedia,
  TextField,
  Button,
  Divider,
  Stack,
  CircularProgress,
  Fab,
} from "@mui/material";
import {
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
} from "@mui/icons-material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  getPostDetail,
  getComments,
  addComment,
  likePost,
  unlikePost,
  deletePost,
} from "../../services/postService";
import { resolveMediaUrl } from "../../services/apiClient";
import { useAuth } from "../../context/AuthContext";
import type { Comment } from "../../types";

export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const qc = useQueryClient();

  const [commentText, setCommentText] = useState("");
  const [replyTo, setReplyTo] = useState<string | null>(null);

  const { data: post, isLoading } = useQuery({
    queryKey: ["post", postId],
    queryFn: () => getPostDetail(postId!),
    enabled: !!postId,
  });

  const { data: commentsData } = useQuery({
    queryKey: ["comments", postId],
    queryFn: () => getComments(postId!),
    enabled: !!postId,
  });

  const likeMutation = useMutation({
    mutationFn: () =>
      post?.is_liked ? unlikePost(postId!) : likePost(postId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["post", postId] });
    },
  });

  const commentMutation = useMutation({
    mutationFn: () => addComment(postId!, commentText, replyTo),
    onSuccess: () => {
      setCommentText("");
      setReplyTo(null);
      qc.invalidateQueries({ queryKey: ["comments", postId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePost(postId!),
    onSuccess: () => navigate("/home"),
  });

  if (isLoading || !post) {
    return (
      <Box display="flex" justifyContent="center" mt={6}>
        <CircularProgress />
      </Box>
    );
  }

  const isAuthor = user?.id === post.author_id;

  return (
    <Container maxWidth="md" sx={{ mt: 3, pb: 6 }}>
      <Card>
        <CardContent>
          <Stack direction="row" spacing={1.5} alignItems="center" mb={2}>
            <Avatar
              src={resolveMediaUrl(post.author_avatar_url) ?? undefined}
              sx={{ width: 44, height: 44, cursor: "pointer" }}
              onClick={() => navigate(`/profile/${post.author_id}`)}
            />
            <Box>
              <Typography
                variant="subtitle1"
                fontWeight={600}
                sx={{ cursor: "pointer" }}
                onClick={() => navigate(`/profile/${post.author_id}`)}
              >
                {post.author_display_name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {new Date(post.create_time).toLocaleString()}
              </Typography>
            </Box>
          </Stack>

          <Typography variant="h5" gutterBottom>
            {post.title}
          </Typography>
          <Typography variant="body1" sx={{ whiteSpace: "pre-wrap", mb: 2 }}>
            {post.content}
          </Typography>

          {post.hashtags.length > 0 && (
            <Box display="flex" flexWrap="wrap" gap={0.5} mb={2}>
              {post.hashtags.map((tag) => (
                <Chip
                  key={tag}
                  label={`#${tag}`}
                  size="small"
                  onClick={() =>
                    navigate(`/search?type=tag&query=${encodeURIComponent(tag)}`)
                  }
                />
              ))}
            </Box>
          )}
        </CardContent>

        {post.image_url && (
          <CardMedia
            component="img"
            image={resolveMediaUrl(post.image_url) ?? ""}
            alt={post.title}
            sx={{ maxHeight: 500, objectFit: "contain" }}
          />
        )}

        <CardContent>
          <Stack direction="row" alignItems="center" spacing={1}>
            <IconButton
              disabled={!user || likeMutation.isPending}
              onClick={() => likeMutation.mutate()}
              color={post.is_liked ? "error" : "default"}
            >
              {post.is_liked ? <FavoriteIcon /> : <FavoriteBorderIcon />}
            </IconButton>
            <Typography variant="body2">{post.like_count} likes</Typography>
          </Stack>
        </CardContent>
      </Card>

      {/* Comments */}
      <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
        Comments
      </Typography>

      {user && (
        <Box mb={3}>
          {replyTo && (
            <Typography variant="caption" color="primary" sx={{ mb: 0.5, display: "block" }}>
              Replying to comment…{" "}
              <Button size="small" onClick={() => setReplyTo(null)}>
                Cancel
              </Button>
            </Typography>
          )}
          <Stack direction="row" spacing={1}>
            <TextField
              fullWidth
              size="small"
              placeholder="Write a comment…"
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && commentText.trim() && commentMutation.mutate()
              }
            />
            <Button
              variant="contained"
              size="small"
              disabled={!commentText.trim() || commentMutation.isPending}
              onClick={() => commentMutation.mutate()}
            >
              Send
            </Button>
          </Stack>
        </Box>
      )}

      {(commentsData?.results ?? []).map((c) => (
        <CommentItem
          key={c.comment_id}
          comment={c}
          onReply={(id) => setReplyTo(id)}
        />
      ))}

      {/* Author FABs */}
      {isAuthor && (
        <Box sx={{ position: "fixed", bottom: 24, right: 24, display: "flex", gap: 1 }}>
          <Fab color="error" size="small" onClick={() => deleteMutation.mutate()}>
            <DeleteIcon />
          </Fab>
        </Box>
      )}
    </Container>
  );
}

function CommentItem({
  comment,
  onReply,
  depth = 0,
}: {
  comment: Comment;
  onReply: (id: string) => void;
  depth?: number;
}) {
  return (
    <Box sx={{ ml: depth * 4, mb: 1.5 }}>
      <Stack direction="row" spacing={1} alignItems="flex-start">
        <Avatar
          src={resolveMediaUrl(comment.author_avatar_url) ?? undefined}
          sx={{ width: 28, height: 28, mt: 0.5 }}
        />
        <Box flex={1}>
          <Typography variant="subtitle2">{comment.author_display_name}</Typography>
          <Typography variant="body2">{comment.content}</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" color="text.secondary">
              {new Date(comment.create_time).toLocaleString()}
            </Typography>
            <Button size="small" onClick={() => onReply(comment.comment_id)}>
              Reply
            </Button>
          </Stack>
        </Box>
      </Stack>
      {comment.replies?.map((r) => (
        <CommentItem key={r.comment_id} comment={r} onReply={onReply} depth={depth + 1} />
      ))}
      {depth === 0 && <Divider sx={{ mt: 1 }} />}
    </Box>
  );
}

function resolveMediaUrl_inner(url: string | null | undefined): string | null {
  // Re-using parent import
  return resolveMediaUrl(url ?? null);
}
