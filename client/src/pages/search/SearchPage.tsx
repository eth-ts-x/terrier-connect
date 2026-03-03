import React from "react";
import { useSearchParams } from "react-router-dom";
import { Container, Typography, CircularProgress, Box } from "@mui/material";
import { useQuery } from "@tanstack/react-query";

import { searchPosts, searchByTag } from "../../services/postService";
import PostCard from "../../components/PostCard";

export default function SearchPage() {
  const [params] = useSearchParams();
  const type = params.get("type") || "keyword";
  const query = params.get("query") || "";

  const { data, isLoading, error } = useQuery({
    queryKey: ["search", type, query],
    queryFn: () =>
      type === "tag" ? searchByTag(query) : searchPosts(query),
    enabled: !!query,
  });

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Typography variant="h5" gutterBottom>
        {type === "tag" ? `Posts tagged #${query}` : `Search: "${query}"`}
      </Typography>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}
      {error && <Typography color="error">Search failed.</Typography>}

      {data && (
        <Typography variant="body2" color="text.secondary" mb={2}>
          {data.total} result{data.total !== 1 ? "s" : ""} found
        </Typography>
      )}

      {data?.results.map((post) => (
        <PostCard key={post.post_id} post={post} />
      ))}

      {!query && (
        <Typography color="text.secondary" textAlign="center" mt={4}>
          Enter a search term to find posts.
        </Typography>
      )}
    </Container>
  );
}
