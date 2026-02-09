import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Container,
  CircularProgress,
  List,
  ListItem,
  Pagination,
  Link,
  Tabs,
  Tab,
  Divider,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { listPosts } from "../services/postService";

const Home = () => {
  const [posts, setPosts] = useState([]); // State to store posts
  const [loading, setLoading] = useState(false); // Loading state
  const [error, setError] = useState(null); // Error state
  const [page, setPage] = useState(1); // Current page number
  const [totalPages, setTotalPages] = useState(1); // Total number of pages
  const [tabValue, setTabValue] = useState(0); // Tab state (0: Latest Posts, 1: From Following)
  const navigate = useNavigate();

  // Fetch posts
  const fetchPosts = async (page, following = false) => {
    setLoading(true);
    setError(null);
    try {
      const response = await listPosts({
        page,
        pageSize: 10,
        ...(following ? { flag: "following" } : {}),
      });
      setPosts(response.results);
      setTotalPages(response.totalPages);
    } catch (err) {
      setError("Failed to fetch posts. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Handle pagination change
  const handlePageChange = (event, value) => {
    setPage(value);
    const isFollowingTab = tabValue === 1;
    fetchPosts(value, isFollowingTab); // Fetch posts for the selected page
  };

  // Handle tab change
  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
    setPage(1); // Reset to page 1 when switching tabs
    const isFollowingTab = newValue === 1;
    fetchPosts(1, isFollowingTab); // Fetch posts for the new tab
  };

  // Handle post detail navigation
  const handlePostDetail = (postId) => {
    navigate(`/post/${postId}`);
  };

  // Fetch posts on component mount or tab/page change
  useEffect(() => {
    const isFollowingTab = tabValue === 1;
    fetchPosts(page, isFollowingTab);
  }, [page, tabValue]);

  return (
    <Box sx={{ bgcolor: "#F4F6F8", minHeight: "100vh", py: 4 }}>
      <Container maxWidth="md">
        <Typography
          variant="h4"
          sx={{ fontWeight: "bold", mb: 4, textAlign: "center" }}
        >
          Explore Posts
        </Typography>

        {/* Tabs for Latest Posts and From Following */}
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{ mb: 2 }}
        >
          <Tab label="Latest Posts" />
          <Tab label="From Following" />
        </Tabs>

        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", my: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Typography
            variant="body1"
            color="error"
            sx={{ textAlign: "center", my: 4 }}
          >
            {error}
          </Typography>
        ) : posts.length === 0 ? (
          <Typography variant="body1" sx={{ textAlign: "center", my: 4 }}>
            No posts found.
          </Typography>
        ) : (
          <List>
            {posts.map((post) => (
              <React.Fragment key={post.id}>
                <ListItem
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    borderBottom: "1px solid #ccc",
                    py: 2,
                  }}
                >
                  <Link
                    component="button"
                    variant="h6"
                    underline="hover"
                    sx={{ fontWeight: "bold", mb: 1, color: "#cc0000" }}
                    onClick={() => handlePostDetail(post.id)}
                  >
                    {post.title}
                  </Link>
                  <Typography variant="body2" color="text.secondary">
                    {post.content.length > 200
                      ? `${post.content.slice(0, 200)}...`
                      : post.content}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ display: "block", mt: 2, color: "gray" }}
                  >
                    {new Date(post.timestamp).toLocaleString()}
                  </Typography>
                </ListItem>
                <Divider />
              </React.Fragment>
            ))}
          </List>
        )}

        {/* Pagination */}
        {!loading && !error && (
          <Box sx={{ display: "flex", justifyContent: "center", mt: 4 }}>
            <Pagination
              count={totalPages}
              page={page}
              onChange={handlePageChange}
              color="primary"
            />
          </Box>
        )}
      </Container>
    </Box>
  );
};

export default Home;
