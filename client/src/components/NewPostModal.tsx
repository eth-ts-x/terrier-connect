import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Chip,
  IconButton,
} from "@mui/material";
import { Close as CloseIcon, AddPhotoAlternate as PhotoIcon } from "@mui/icons-material";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPost } from "../services/postService";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function NewPostModal({ open, onClose }: Props) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [hashtag, setHashtag] = useState("");
  const [hashtags, setHashtags] = useState<string[]>([]);
  const [image, setImage] = useState<File | null>(null);

  const mutation = useMutation({
    mutationFn: (fd: FormData) => createPost(fd),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["posts"] });
      resetAndClose();
    },
  });

  const resetAndClose = () => {
    setTitle("");
    setContent("");
    setHashtag("");
    setHashtags([]);
    setImage(null);
    onClose();
  };

  const addHashtag = () => {
    const tag = hashtag.trim().replace(/^#/, "");
    if (tag && !hashtags.includes(tag)) {
      setHashtags([...hashtags, tag]);
    }
    setHashtag("");
  };

  const submit = () => {
    const fd = new FormData();
    fd.append("title", title);
    fd.append("content", content);
    fd.append("hashtags", JSON.stringify(hashtags));
    if (image) fd.append("image_url", image);
    mutation.mutate(fd);
  };

  return (
    <Dialog open={open} onClose={resetAndClose} fullWidth maxWidth="sm">
      <DialogTitle>
        New Post
        <IconButton
          onClick={resetAndClose}
          sx={{ position: "absolute", right: 8, top: 8 }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers>
        <TextField
          label="Title"
          fullWidth
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          sx={{ mb: 2 }}
        />
        <TextField
          label="Content"
          fullWidth
          multiline
          rows={4}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          sx={{ mb: 2 }}
        />
        <Box display="flex" gap={1} mb={1}>
          <TextField
            label="Add hashtag"
            size="small"
            value={hashtag}
            onChange={(e) => setHashtag(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addHashtag())}
          />
          <Button onClick={addHashtag} variant="outlined" size="small">
            Add
          </Button>
        </Box>
        <Box display="flex" flexWrap="wrap" gap={0.5} mb={2}>
          {hashtags.map((t) => (
            <Chip
              key={t}
              label={`#${t}`}
              onDelete={() => setHashtags(hashtags.filter((x) => x !== t))}
              size="small"
            />
          ))}
        </Box>
        <Button component="label" startIcon={<PhotoIcon />} variant="outlined">
          {image ? image.name : "Upload Image"}
          <input
            type="file"
            hidden
            accept="image/*"
            onChange={(e) => setImage(e.target.files?.[0] ?? null)}
          />
        </Button>
      </DialogContent>
      <DialogActions>
        <Button onClick={resetAndClose}>Cancel</Button>
        <Button
          onClick={submit}
          variant="contained"
          disabled={!title.trim() || !content.trim() || mutation.isPending}
        >
          {mutation.isPending ? "Posting…" : "Post"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
