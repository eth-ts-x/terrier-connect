import React, { useState } from "react";
import {
  Modal,
  Box,
  Typography,
  TextField,
  Button,
  Snackbar,
  Alert,
  Grid,
  Chip,
  Switch,
  FormControlLabel,
} from "@mui/material";
import { Close } from "@mui/icons-material";
import MapView from "./MapSelection";
import { addPost } from "../services/postService";

const NewPostModal = ({ open, handleClose }) => {
  const [formData, setFormData] = useState({
    title: "",
    eventLocation: "[-71.10540390014648, 42.35050441261373]",
    content: "",
    hashtags: [], // Example initial hashtags
    image_url: null,
    newHashtag: "", // For storing the current input for a new hashtag
  });

  const [successMessage, setSuccessMessage] = useState(false);
  const [mapEnabled, setMapEnabled] = useState(true); // State to control map visibility

  // Handle input changes
  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleImageChange = (event) => {
    const file = event.target.files[0];
    setFormData({ ...formData, image_url: file });
  };

  // Add new hashtag to the list
  const handleAddHashtag = () => {
    const sanitizedHashtag = formData.newHashtag.trim().replace(/^#/, ""); // Remove # from the beginning
    if (sanitizedHashtag !== "" && !formData.hashtags.includes(sanitizedHashtag)) {
      setFormData({
        ...formData,
        hashtags: [...formData.hashtags, sanitizedHashtag],
        newHashtag: "", // Clear the input field after adding
      });
    } else {
      alert("Please input a valid and unique tag!");
    }
  };

  // Remove hashtag from the list
  const handleRemoveHashtag = (hashtagToRemove) => {
    setFormData({
      ...formData,
      hashtags: formData.hashtags.filter((hashtag) => hashtag !== hashtagToRemove),
    });
  };

  // Submit handler
  const handleSubmit = async () => {
    if (!formData.title || !formData.content) {
      alert("Please fill out all required fields!");
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("User is not logged in, please log in first!");
      return;
    }

    const data = new FormData();
    data.append("title", formData.title);
    data.append("content", formData.content);
    data.append("hashtags", JSON.stringify(formData.hashtags)); // Convert hashtags to string
    if (formData.image_url) {
      data.append("image_url", formData.image_url);
    }
    if (formData.eventLocation) {
      data.append("geolocation", formData.eventLocation);
    }

    try {
      console.log("Image:", data.image_url);
      const response = await addPost(data);
      console.log("Post created successfully:", response);
      setSuccessMessage(true);
      setFormData({
        title: "",
        eventLocation: "",
        content: "",
        hashtags: [],
        image_url: null,
        newHashtag: "",
      });
      handleClose();

      // Refresh the page after successful submission
      setTimeout(() => {
        window.location.reload();
      }, 500); // Add a slight delay to let the success message show
      
    } catch (error) {
      console.error("Error creating post:", error.response || error.message);
      alert("Posting failed, please check your input!");
    }
  };

  // Handle map coordinates change
  const handleCoordinatesChange = (coords) => {
    const coordsString = `[${coords.lng}, ${coords.lat}]`;
    setFormData({ ...formData, eventLocation: coordsString });
  };

  // Handle the map switch
  const handleMapSwitch = (event) => {
    const isMapOn = event.target.checked;
    setMapEnabled(isMapOn);
    if (!isMapOn) {
      // Reset event location and selected coordinates when map is off
      setFormData({ ...formData, eventLocation: "" });
    } else {
      setFormData({ ...formData, eventLocation: "[-71.10540390014648, 42.35050441261373]" });
    }
  };

  return (
    <>
      <Modal open={open} onClose={handleClose} aria-labelledby="new-post-modal">
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "80%",
            maxHeight: "80vh", // Limit the height of the box
            overflowY: "auto", // Enable scrolling if content overflows
            bgcolor: "background.paper",
            boxShadow: 24,
            p: 4,
            borderRadius: 2,
          }}
        >
          <Typography id="new-post-modal" variant="h5" sx={{ fontWeight: "bold", mb: 2 }}>
            Create New Post
          </Typography>

          {/* Title */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12}>
              <TextField
                required
                label="Title"
                name="title"
                fullWidth
                value={formData.title}
                onChange={handleChange}
              />
            </Grid>
          </Grid>

          {/* Content */}
          <TextField
            required
            label="Content"
            name="content"
            margin="dense"
            fullWidth
            multiline
            rows={6}
            value={formData.content}
            onChange={handleChange}
            sx={{ mb: 2 }}
          />

          {/* Image Upload */}
          <input
              accept="image/*"
              type="file"
              id="avatar-upload"
              style={{ display: "none" }}
              onChange={handleImageChange}
            />
            <label htmlFor="avatar-upload">
              <Button variant="outlined" component="span">
                Choose Image File
              </Button>
            </label>
            {formData.image_url && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                Selected file: {formData.image_url.name}
              </Typography>
            )}

          {/* Hashtag Input */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={10}>
              <TextField
                label="New Hashtag"
                name="newHashtag"
                fullWidth
                value={formData.newHashtag}
                onChange={handleChange}
                onKeyDown={(e) => e.key === "Enter" && handleAddHashtag()}
              />
            </Grid>
            <Grid item xs={2}>
              <Button
                variant="contained"
                color="primary"
                fullWidth
                onClick={handleAddHashtag}
                sx={{ height: "100%" }}
              >
                Add
              </Button>
            </Grid>
          </Grid>

          {/* Display selected hashtags */}
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, marginBottom: 2 }}>
            {formData.hashtags.map((hashtag, index) => (
              <Chip
                key={index}
                label={hashtag}
                onDelete={() => handleRemoveHashtag(hashtag)}
                deleteIcon={<Close />}
                color="primary"
                sx={{ fontSize: "14px", backgroundColor: "#e0f7fa" }}
              />
            ))}
          </Box>

          {/* Map Switch */}
          <FormControlLabel
            control={
              <Switch
                checked={mapEnabled}
                onChange={handleMapSwitch}
                color="primary"
              />
            }
            label="Include Map Location"
            sx={{ mb: 2 }}
          />

          {/* Conditional Map Display */}
          {mapEnabled && (
            <div style={{ marginBottom: "16px" }}>
              <MapView onCoordinatesChange={handleCoordinatesChange} />
            </div>
          )}

          {/* Post button */}
          <Button
            variant="contained"
            fullWidth
            sx={{
              marginTop: 2,
              backgroundColor: "#42b72a",
              color: "#fff",
              padding: "10px 0",
              fontSize: "16px",
              fontWeight: "bold",
              "&:hover": {
                backgroundColor: "#36a420",
              },
            }}
            onClick={handleSubmit}
          >
            Post
          </Button>
        </Box>
      </Modal>

      {/* Success message */}
      <Snackbar
        open={successMessage}
        autoHideDuration={3000}
        onClose={() => setSuccessMessage(false)}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert onClose={() => setSuccessMessage(false)} severity="success" sx={{ width: "100%" }}>
          Post created successfully!
        </Alert>
      </Snackbar>
    </>
  );
};

export default NewPostModal;
