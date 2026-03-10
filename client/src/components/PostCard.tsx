import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardMedia,
  CardActions,
  Typography,
  IconButton,
  Chip,
  Box,
  Avatar,
  Stack,
} from "@mui/material";
import {
  Favorite as FavoriteIcon,
  FavoriteBorder as FavoriteBorderIcon,
  ChatBubbleOutline as CommentIcon,
} from "@mui/icons-material";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Post } from "../types";
import { likePost, unlikePost } from "../services/postService";
import { resolveMediaUrl } from "../services/apiClient";
import { useAuth } from "../context/AuthContext";

interface Props {
  post: Post;
}

export default function PostCard({ post }: Props) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const qc = useQueryClient();

  const likeMutation = useMutation({
    mutationFn: () => (post.is_liked ? unlikePost(post.post_id) : likePost(post.post_id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["posts"] });
      qc.invalidateQueries({ queryKey: ["post", post.post_id] });
    },
  });

  return (
    <Card sx={{ mb: 2, cursor: "pointer" }}>
      <CardContent onClick={() => navigate(`/post/${post.post_id}`)}>
        <Stack direction="row" spacing={1.5} alignItems="center" mb={1}>
          <Avatar
            src={resolveMediaUrl(post.author_avatar_url) ?? undefined}
            sx={{ width: 36, height: 36 }}
          />
          <Box>
            <Typography
              variant="subtitle2"
              sx={{ cursor: "pointer" }}
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/profile/${post.author_id}`);
              }}
            >
              {post.author_display_name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(post.create_time).toLocaleDateString()}
            </Typography>
          </Box>
        </Stack>

        <Typography variant="h6" gutterBottom>
          {post.title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {post.content.length > 200 ? `${post.content.slice(0, 200)}…` : post.content}
        </Typography>

        {post.hashtags.length > 0 && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 1 }}>
            {post.hashtags.map((tag) => (
              <Chip
                key={tag}
                label={`#${tag}`}
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/search?type=tag&query=${encodeURIComponent(tag)}`);
                }}
              />
            ))}
          </Box>
        )}
      </CardContent>

      {post.image_url && (
        <CardMedia
          component="img"
          height="300"
          image={resolveMediaUrl(post.image_url) ?? ""}
          alt={post.title}
          onClick={() => navigate(`/post/${post.post_id}`)}
          sx={{ objectFit: "cover" }}
        />
      )}

      <CardActions disableSpacing>
        <IconButton
          disabled={!user || likeMutation.isPending}
          onClick={() => likeMutation.mutate()}
          color={post.is_liked ? "error" : "default"}
        >
          {post.is_liked ? <FavoriteIcon /> : <FavoriteBorderIcon />}
        </IconButton>
        <Typography variant="body2" color="text.secondary">
          {post.like_count}
        </Typography>
        <IconButton sx={{ ml: 1 }} onClick={() => navigate(`/post/${post.post_id}`)}>
          <CommentIcon />
        </IconButton>
      </CardActions>
    </Card>
  );
}
