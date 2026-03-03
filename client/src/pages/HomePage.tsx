import React, { useState } from "react";
import { Container, Tabs, Tab, Box, Typography, CircularProgress } from "@mui/material";
import { useQuery } from "@tanstack/react-query";

import { listPosts } from "../services/postService";
import { useAuth } from "../context/AuthContext";
import PostCard from "../components/PostCard";

export default function HomePage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"all" | "following">("all");

  const { data, isLoading, error } = useQuery({
    queryKey: ["posts", tab],
    queryFn: () => listPosts(tab),
  });

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>
        Feed
      </Typography>
      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Latest Posts" value="all" />
          {user && <Tab label="Following" value="following" />}
        </Tabs>
      </Box>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}
      {error && (
        <Typography color="error">Failed to load posts.</Typography>
      )}
      {data?.results.map((post) => (
        <PostCard key={post.post_id} post={post} />
      ))}
      {data && data.results.length === 0 && (
        <Typography color="text.secondary" textAlign="center" mt={4}>
          No posts yet. Be the first!
        </Typography>
      )}
    </Container>
  );
}
