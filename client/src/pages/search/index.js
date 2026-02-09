import React, { useState, useEffect } from "react";
import {
  Box,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  Typography,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  Stack,
} from "@mui/material";
import { useNavigate, useLocation } from "react-router-dom";
import { listPostsByTag, fullTextSearch } from "../../services/searchService";

const PostSearch = () => {
  const [searchResults, setSearchResults] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [searchType, setSearchType] = useState("keyword"); // Default search type
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1); // Current page
  const [totalPages, setTotalPages] = useState(1); // Total pages
  const [pageSize, setPageSize] = useState(10); // Results per page
  const navigate = useNavigate();
  const location = useLocation();

  // Parse URL parameters
  const query = new URLSearchParams(location.search).get("query");
  const type = new URLSearchParams(location.search).get("searchType") || "keyword";

  useEffect(() => {
    setSearchType(type); // Set searchType based on URL parameter
    setSearchTerm(query || ""); // Set searchTerm based on URL parameter
    if (query) {
      fetchSearchResults(query, type, page, pageSize);
    }
  }, [query, type, page, pageSize]); // React to changes in query, type, page, or pageSize

  const fetchSearchResults = async (query, searchType, page, pageSize) => {
    setLoading(true);
    setError(null);

    try {
      let response;
      if (searchType === "tag") {
        response = await listPostsByTag({ tag: query, page, pageSize });
      
      } else if (searchType === "keyword") {
        response = await fullTextSearch({
          query,
          page,
          pageSize,
          orderBy: "-create_time",
        });
      }

      setSearchResults(response.results);
      setTotalPages(response.totalPages);
      setError(null); // Clear previous errors
    } catch (err) {
      console.error("Error fetching search results:", err);
      setError("Failed to fetch search results. Tags must be precisely matched.");
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (event) => {
    setSearchTerm(event.target.value);
  };

  const handleSearchTypeChange = (event) => {
    setSearchType(event.target.value);
  };

  const handleSearch = () => {
    if (searchTerm.trim()) {
      navigate(`/search?searchType=${searchType}&query=${encodeURIComponent(searchTerm)}&page=1`);
      setPage(1); // Reset to first page on new search
    } else {
      alert("Please enter a search term!");
    }
  };

  const handlePageChange = (event, value) => {
    setPage(value);
    navigate(`/search?searchType=${searchType}&query=${encodeURIComponent(searchTerm)}&page=${value}`);
  };

  return (
    <Box sx={{ maxWidth: 800, margin: "auto", padding: 2 }}>
      {/* Search bar */}
      <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
        <FormControl sx={{ minWidth: 120, marginRight: 2 }}>
          <InputLabel>Search Type</InputLabel>
          <Select
            value={searchType}
            onChange={handleSearchTypeChange}
            label="Search Type"
            sx={{ height: "100%" }}
          >
            <MenuItem value="keyword">Keyword</MenuItem>
            <MenuItem value="tag">Tag</MenuItem>
          </Select>
        </FormControl>

        <TextField
          label="Search..."
          variant="outlined"
          fullWidth
          value={searchTerm}
          onChange={handleSearchChange}
          sx={{ marginRight: 2 }}
        />
        <Button variant="contained" onClick={handleSearch}>
          Search
        </Button>
      </Box>

      {/* Search results */}
      {loading ? (
        <Typography align="center">Loading...</Typography>
      ) : error ? (
        <Typography color="error" align="center">
          {error}
        </Typography>
      ) : searchResults.length > 0 ? (
        <List>
          {searchResults.map((post) => (
            <React.Fragment key={post.id}>
              <ListItem
                button
                onClick={() => navigate(`/post/${post.id}`)}
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  marginBottom: 2,
                  padding: 2,
                  border: "1px solid #ddd",
                  borderRadius: "8px",
                  backgroundColor: "#f9f9f9",
                  "&:hover": {
                    backgroundColor: "#eaeaea",
                  },
                }}
              >
                <ListItemText
                  primary={
                    <>
                    <Typography variant="h6" sx={{ fontWeight: "bold" }}>
                      {post.title ? post.title.substring(0, 50) : "Untitled"}
                    </Typography>
                    <Typography variant="body2" color="textSecondary" sx={{ display: "block" }}>
                    {post.content ? post.content.substring(0, 50) : "No content available"}...
                  </Typography>
                  </>
                  }
                  secondary={
                    <Box>
                      <Typography variant="caption" color="textSecondary">
                        Author: {post.author} | Date: {new Date(post.timestamp).toLocaleString()}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
              <Divider />
            </React.Fragment>
          ))}
        </List>
      ) : (
        <Typography variant="body1" color="textSecondary" align="center">
          No matched posts can be found
        </Typography>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <Stack spacing={2} sx={{ mt: 4, alignItems: "center" }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={handlePageChange}
            color="primary"
            showFirstButton
            showLastButton
            sx={{ alignSelf: "center" }}
          />
        </Stack>
      )}
    </Box>
  );
};

export default PostSearch;
