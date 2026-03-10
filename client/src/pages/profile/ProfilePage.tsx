import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  Avatar,
  Box,
  Button,
  Tabs,
  Tab,
  CircularProgress,
  Stack,
  List,
  ListItemButton,
  ListItemAvatar,
  ListItemText,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../../context/AuthContext";
import { getUserDetail, getFollowers, getFollowing, followUser, unfollowUser } from "../../services/userService";
import { getPostsByUser } from "../../services/postService";
import { resolveMediaUrl } from "../../services/apiClient";
import PostCard from "../../components/PostCard";

export default function ProfilePage() {
  const { userId } = useParams<{ userId: string }>();
  const { user: me } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const isMe = !userId || userId === "me";
  const profileId = isMe ? me?.id : Number(userId);

  const [tab, setTab] = useState(0);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["user", profileId],
    queryFn: () => getUserDetail(profileId!),
    enabled: !!profileId,
  });

  const { data: posts } = useQuery({
    queryKey: ["user-posts", profileId],
    queryFn: () => getPostsByUser(profileId!),
    enabled: !!profileId && tab === 0,
  });

  const { data: followers } = useQuery({
    queryKey: ["followers", profileId],
    queryFn: () => getFollowers(profileId!),
    enabled: !!profileId && tab === 1,
  });

  const { data: following } = useQuery({
    queryKey: ["following", profileId],
    queryFn: () => getFollowing(profileId!),
    enabled: !!profileId && tab === 2,
  });

  // Check if current user follows this profile
  const { data: myFollowing } = useQuery({
    queryKey: ["following", me?.id],
    queryFn: () => getFollowing(me!.id, 1, 200),
    enabled: !!me && !isMe,
  });

  const isFollowing = myFollowing?.results.some((u) => u.id === profileId) ?? false;

  const followMutation = useMutation({
    mutationFn: () => (isFollowing ? unfollowUser(profileId!) : followUser(profileId!)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["following", me?.id] });
      qc.invalidateQueries({ queryKey: ["followers", profileId] });
    },
  });

  if (isLoading || !profile) {
    return (
      <Box display="flex" justifyContent="center" mt={6}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Stack direction="row" spacing={3} alignItems="center" mb={3}>
        <Avatar
          src={resolveMediaUrl(profile.avatar_url) ?? undefined}
          sx={{ width: 80, height: 80 }}
        />
        <Box flex={1}>
          <Typography variant="h5">{profile.display_name}</Typography>
          <Typography variant="body2" color="text.secondary">
            {profile.email}
          </Typography>
          {profile.bio && (
            <Typography variant="body2" mt={0.5}>
              {profile.bio}
            </Typography>
          )}
        </Box>
        {me && !isMe && (
          <Button
            variant={isFollowing ? "outlined" : "contained"}
            onClick={() => followMutation.mutate()}
            disabled={followMutation.isPending}
          >
            {isFollowing ? "Unfollow" : "Follow"}
          </Button>
        )}
        {isMe && (
          <Button variant="outlined" onClick={() => navigate("/profile/me/edit")}>
            Edit Profile
          </Button>
        )}
      </Stack>

      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Posts" />
          <Tab label="Followers" />
          <Tab label="Following" />
        </Tabs>
      </Box>

      {tab === 0 &&
        posts?.results.map((post) => (
          <PostCard key={post.post_id} post={post} />
        ))}

      {tab === 1 && (
        <UserList users={followers?.results ?? []} navigate={navigate} />
      )}

      {tab === 2 && (
        <UserList users={following?.results ?? []} navigate={navigate} />
      )}
    </Container>
  );
}

function UserList({
  users,
  navigate,
}: {
  users: { id: number; display_name: string; avatar_url: string | null }[];
  navigate: (path: string) => void;
}) {
  if (users.length === 0) {
    return (
      <Typography color="text.secondary" textAlign="center" mt={3}>
        No users to show.
      </Typography>
    );
  }
  return (
    <List>
      {users.map((u) => (
        <ListItemButton key={u.id} onClick={() => navigate(`/profile/${u.id}`)}>
          <ListItemAvatar>
            <Avatar src={resolveMediaUrl(u.avatar_url) ?? undefined} />
          </ListItemAvatar>
          <ListItemText primary={u.display_name} />
        </ListItemButton>
      ))}
    </List>
  );
}
