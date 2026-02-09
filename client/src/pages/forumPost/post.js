import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  CircularProgress,
  Grid,
  Chip,
  Fab,
  Modal,
  TextField,
  Button,
  Avatar,
  Divider,
} from "@mui/material";
import AddCommentIcon from "@mui/icons-material/AddComment";
import DeleteIcon from "@mui/icons-material/Delete";
import {
  getPostDetail,
  getComments,
  submitComment,
  deletePost,
} from "../../services/postService";
import { getUserDetail } from "../../services/userService";
import { getPostHashtagsByPostId } from "../../services/hashtagService";
import { resolveMediaUrl } from "../../services/apiClient";
import { postBoxStyle, commentStyle } from "./postStyles.js";
import EditPost from "./editpost.js";
import MapView from "./Map.js";


const PostWithID = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [post, setPost] = useState(null);
  const [author, setAuthor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [comment, setComment] = useState("");
  const [open, setOpen] = useState(false);
  const [comments, setComments] = useState([]);
  const [userMap, setUserMap] = useState({});
  const [replyOpen, setReplyOpen] = useState(false);
  const [parentId, setParentId] = useState(null);
  const [replyContent, setReplyContent] = useState("");
  const [currentUserId, setCurrentUserId] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [tags, setTags] = useState([]);

  useEffect(() => {
   const user = JSON.parse(localStorage.getItem("user"));
  if (user) { setCurrentUserId(user.id); }   
      const fetchData = async () => {
    try {
      const postDetail = await getPostDetail(id);
      setPost(postDetail);

      const userDetail = await getUserDetail(postDetail.author);
      setAuthor(userDetail);

      const commentsData = await getComments(id, {
        page: 1,
        pageSize: 10,
        orderBy: "create_time",
      });
      setComments(commentsData.results || commentsData);

      const tagResponse = await getPostHashtagsByPostId(id, {
        page: 1,
        pageSize: 20,
      });
      const tagList = tagResponse.results || tagResponse;
      setTags(Array.isArray(tagList) ? tagList.map((tag) => tag.hashtag_text) : []);
    } catch (err) {
      console.error("Error fetching data:", err);
      setError("Unable to load data! ");
    } finally {
      setLoading(false);
    }
  };

    fetchData();
  }, [id]);

  const handleReplyClick = (commentId) => {
    setParentId(commentId);
    setReplyOpen(true);
  };

  const handleCommentSubmit = async () => {
    try {
      await submitComment(id, comment);
      alert("Comment submitted successfully!");
      setComment("");
      setOpen(false);

      // Update the comments
      const commentsData = await getComments(id, {
        page: 1,
        pageSize: 10,
        orderBy: "create_time",
      });
      setComments(commentsData.results || commentsData);
    } catch (err) {
      console.error("Error submitting comment:", err);
      alert("Comment submission failed, please try again later.");
    }
  };

  const handleReplySubmit = async () => {
    try {
      await submitComment(id, replyContent, parentId);
      alert("Response submitted successfully!");
      setReplyContent("");
      setReplyOpen(false);

      // update the comments
      const commentsData = await getComments(id, {
        page: 1,
        pageSize: 10,
        orderBy: "create_time",
      });
      setComments(commentsData.results || commentsData);
    } catch (error) {
      console.error("Error submitting reply:", error);
      alert("Reply Submission failed, please try again later.");
    }
  };

  const fetchUserName = async (userId) => {
    if (userMap[userId]) return;

    try {
      const userDetail = await getUserDetail(userId);
      setUserMap((prev) => ({ ...prev, [userId]: userDetail || "unkonwn user" }));
    } catch (error) {
      console.error(`Error fetching user name for userId ${userId}:`, error);
    }
  };

  const fetchPost = async () => {
    const postData = await getPostDetail(id);
    setPost(postData);
  };

  const renderReplies = (replies) =>
    replies.map((reply) => {
      fetchUserName(reply.author);
  
      return (
        <Box
          key={reply.id}
          sx={{
            marginBottom: 2,
            padding: 2,
            border: "2px solid #ddd",
            borderRadius: 2,
            backgroundColor: "#f9f9f9",
            marginLeft: 5, // Indent for replies
          }}
        >
          {/* Main Reply Section */}
          <Box sx={{ display: "flex", alignItems: "flex-start" }}>
            {/* Render Avatar */}
            <Avatar
              sx={{
                width: 40,
                height: 40,
                marginRight: 2,
                cursor: "pointer", // Indicate clickable
                "&:hover": { border: "1px solid #1976d2" }, // Add hover effect
              }}
              src={
                userMap[reply.author]?.avatar_url
                    ? resolveMediaUrl(userMap[reply.author]?.avatar_url)
                  : ""
              }
              alt={userMap[reply.author]?.display_name || "User"}
              onClick={() => navigate(`/profile/${reply.author}`)}
            />
  
            {/* Render Reply Details */}
            <Box sx={{ flex: 1 }}>
              {/* Top Row: Username and Timestamp */}
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 1,
                }}
              >
                <Box>
                  <Typography variant="body1" sx={{ fontWeight: "bold" }}>
                    {userMap[reply.author]?.display_name || "Unknown User"}
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    {new Date(reply.create_time).toLocaleString()}
                  </Typography>
                </Box>
  
                {/* Reply Button */}
                <Button
                  size="small"
                  onClick={() => handleReplyClick(reply.id)}
                  sx={{ alignSelf: "flex-start" }}
                >
                  Reply
                </Button>
              </Box>
  
              {/* Reply Content */}
              <Typography variant="body1">{reply.content}</Typography>
            </Box>
          </Box>
  
          {/* Render Sub Replies Section */}
          {reply.replies && reply.replies.length > 0 && (
            <Box>
              {renderReplies(reply.replies)}
            </Box>
          )}
        </Box>
      );
    });  

  const renderComments = () =>
    comments.map((comment) => {
      fetchUserName(comment.author);

      return (
        <Box
          key={comment.id}
          sx={{
            marginBottom: 2,
            padding: 2,
            border: "2px solid #ddd",
            borderRadius: 2,
            backgroundColor: "#f9f9f9",
          }}
        >
          {/* Main Comment Section */}
          <Box sx={{ display: "flex", alignItems: "flex-start" }}>
            {/* Render Avatar */}
            <Avatar
              sx={{
                width: 40,
                height: 40,
                marginRight: 2,
                cursor: "pointer",
                "&:hover": { border: "1px solid #1976d2" },
              }}
              src={
                userMap[comment.author]?.avatar_url
                    ? resolveMediaUrl(userMap[comment.author]?.avatar_url)
                  : ""
              }
              alt={userMap[comment.author]?.display_name || "User"}
              onClick={() => navigate(`/profile/${comment.author}`)}
            />

            {/* Render Comment Details */}
            <Box sx={{ flex: 1 }}>
              {/* Top Row: Username and Timestamp */}
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 1,
                }}
              >
                <Box>
                  <Typography variant="body1" sx={{ fontWeight: "bold" }}>
                    {userMap[comment.author]?.display_name || "Unknown User"}
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    {new Date(comment.create_time).toLocaleString()}
                  </Typography>
                </Box>

                {/* Reply Button */}
                <Button
                  size="small"
                  onClick={() => handleReplyClick(comment.id)}
                  sx={{ alignSelf: "flex-start" }}
                >
                  Reply
                </Button>
              </Box>

              {/* Comment Content */}
              <Typography variant="body1">{comment.content}</Typography>
            </Box>
          </Box>

          {/* Render Replies Section */}
          {comment.replies && (
            <Box sx={{ marginTop: 1 }}>
              {renderReplies(comment.replies)}
            </Box>
          )}
        </Box>
      );
    });

  const handleDeletePost = async () => {
    try {
      await deletePost(id);
      alert("Post deleted!");
      navigate("/home");
    } catch (error) {
      console.error("Error deleting post:", error);
      alert("Deletion failed, please try again later!");
    } finally {
      setDeleteConfirmOpen(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ textAlign: "center", marginTop: 4 }}>
        <CircularProgress />
        <Typography sx={{ marginTop: 2 }}>Loading...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ textAlign: "center", marginTop: 4 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Post Info Box */}
      <Box sx={postBoxStyle}>
        <Grid container spacing={1}>
          {/* Author information on the left */}
          <Grid item xs={12} md={2}>
            <Box
              sx={{
                padding: 2,
                borderRight: "1px solid #444",
                height: "100%",
              }}
            >
              <Avatar
                sx={{ width: 60, height: 60, mb: 2,
                  cursor: "pointer", // Indicate clickable
                  "&:hover": {
                    border: "2px solid #1976d2", // Add border on hover
                    boxShadow: "0 0 10px rgba(0, 0, 0, 0.3)", // Optional: Add shadow for hover effect
                  },
                }}
                src={resolveMediaUrl(author.avatar_url)}
                onClick={() => navigate(`/profile/${author.id}`)} // Add navigate function
                alt={author.display_name}
              />

              <Typography variant="h6" sx={{ marginBottom: 1 }}>
              {author.display_name || "No name"}
              </Typography>
              <Typography variant="body1">Email: {author.email}</Typography>
              <Typography variant="body2">Profile: {author.bio || "No Profile"}</Typography>
            </Box>
          </Grid>

          {/* The content of the post is on the right */}
          <Grid item xs={12} md={10}>
            <Box sx={{ padding: 2 }}>
              <Typography variant="h4" sx={{ marginBottom: 2 }}>
                {post.title}
              </Typography>
              {post.image_url && (
          <Box
            component="img"
            src={resolveMediaUrl(post.image_url)}
            alt="Post Image"
            sx={{
              width: "100%",
              maxWidth: "500px",
              maxHeight: "300px",
              borderRadius: 2,
              marginBottom: 2,
              objectFit: "contain",
              display: post.image_url ? "block" : "none",
            }}
          />
        )}
              <Typography variant="body1" sx={{ marginBottom: 2 }}>
                {post.content}
              </Typography>
              <Typography variant="caption" color="textSecondary">
              Creation time:{new Date(post.create_time).toLocaleString()}
              </Typography>
              <Typography variant="caption" color="textSecondary" sx={{ display: "block", marginTop: 1 }}>
                {post.update_time
                  ? `Last edited:${new Date(post.update_time).toLocaleString()}`
                  : "unedited"}
              </Typography>

              {/* Tag Display Area */}
              <Box sx={{ marginTop: 4 }}>
                <Typography variant="h6" sx={{ marginBottom: 1 }}>
                  Tags:
                </Typography>
                {loading ? (
                  <Typography>Loading Tags...</Typography>
                ) : error ? (
                  <Typography color="error">{error}</Typography>
                ) : (
                  <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                    {tags.map((tag, index) => (
                      <Chip
                        key={index}
                        label={tag}
                        sx={{ fontSize: "14px", backgroundColor: "#e0f7fa" }}
                      />
                    ))}
                  </Box>
                )}
              </Box>
              {/* Map Diplay */}

              {post.geolocation && (
                <Box sx={{ marginTop: 4 }}>
                  <Typography variant="h6" sx={{ marginBottom: 1 }}>
                  Location:
                  </Typography>
                  <MapView
                    geolocation={{
                      lng: parseFloat(post.geolocation.split(",")[0].slice(1)),
                      lat: parseFloat(post.geolocation.split(",")[1].slice(0, -1)),
                    }}
                  />
                </Box>
              )}
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* comment section */}
      <Box
        sx={{
          margin: 8,
          padding: 2,
          border: "2px solid #444",
          borderRadius: 4,
          backgroundColor: "#f9f9f9",
        }}
      >
        <Typography variant="h5" sx={{ marginBottom: 2 }}>
          Comments
        </Typography>
        <Divider sx={{ marginBottom: 2 }} />
        {renderComments()}
      </Box>

      {/* Floating comment button */}
      <Fab
        color="primary"
        sx={{ position: "fixed", bottom: 24, right: 24 }}
        onClick={() => setOpen(true)}
      >
        <AddCommentIcon />
      </Fab>

      {/* Edit button (visible only to the author) */}
      {currentUserId === post.author && (
        <>
          <EditPost postId={post.id} onPostUpdated={fetchPost}/>

          {/* Delete button */}
          <Fab
            color="error"
            sx={{ position: "fixed", bottom: 24, right: 168 }}
            onClick={() => setDeleteConfirmOpen(true)}
          >
            <DeleteIcon />
          </Fab>
        </>
      )}

      {/* Comment dialog box */}
      <Modal open={open} onClose={() => setOpen(false)}>
        <Box
          sx={commentStyle}
        >
          <Typography variant="h6" sx={{ marginBottom: 2 }}>
          Add a comment
          </Typography>
          <TextField
            label="content"
            multiline
            rows={4}
            fullWidth
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <Box sx={{ marginTop: 2, textAlign: "right" }}>
            <Button onClick={() => setOpen(false)} sx={{ marginRight: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" color="primary" onClick={handleCommentSubmit}>
              Submit
            </Button>
          </Box>
        </Box>
      </Modal>

      {/* Respond to the dialog box */}
      <Modal open={replyOpen} onClose={() => setReplyOpen(false)}>
        <Box sx={commentStyle}>
          <Typography variant="h6" sx={{ marginBottom: 2 }}>
            reply
          </Typography>
          <TextField
            label="content"
            multiline
            rows={4}
            fullWidth
            value={replyContent}
            onChange={(e) => setReplyContent(e.target.value)}
          />
          <Box sx={{ marginTop: 2, textAlign: "right" }}>
            <Button onClick={() => setReplyOpen(false)} sx={{ marginRight: 1 }}>
              cancel
            </Button>
            <Button variant="contained" color="primary" onClick={handleReplySubmit}>
              submit
            </Button>
          </Box>
        </Box>
      </Modal>

      {/* Delete Confirmation Box */}
      <Modal open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)}>
        <Box sx={commentStyle}>
          <Typography variant="h6" sx={{ marginBottom: 2 }}>
          Confirm deletion
          </Typography>
          <Typography variant="body1" sx={{ marginBottom: 2 }}>
          Sure you want to delete this post? This action cannot be undone.
          </Typography>
          <Box sx={{ textAlign: "right" }}>
            <Button onClick={() => setDeleteConfirmOpen(false)} sx={{ marginRight: 1 }}>
              Cancel
            </Button>
            <Button variant="contained" color="error" onClick={handleDeletePost}>
            Confirm
            </Button>
          </Box>
        </Box>
      </Modal>

    </Box>
  );
};

export default PostWithID;