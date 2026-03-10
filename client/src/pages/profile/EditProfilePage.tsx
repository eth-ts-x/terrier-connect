import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  TextField,
  Button,
  Alert,
  Avatar,
  Box,
  Stack,
} from "@mui/material";
import { useMutation } from "@tanstack/react-query";

import { useAuth } from "../../context/AuthContext";
import { updateProfile } from "../../services/userService";
import { resolveMediaUrl } from "../../services/apiClient";

export default function EditProfilePage() {
  const navigate = useNavigate();
  const { user, setUser } = useAuth();

  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [avatar, setAvatar] = useState<File | null>(null);
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: (fd: FormData) => updateProfile(fd),
    onSuccess: (data) => {
      setUser(data.user);
      navigate("/profile/me");
    },
    onError: () => setError("Failed to update profile."),
  });

  const handleSubmit = () => {
    const fd = new FormData();
    fd.append("display_name", displayName);
    fd.append("bio", bio);
    if (avatar) fd.append("avatar_url", avatar);
    mutation.mutate(fd);
  };

  if (!user) return null;

  return (
    <Container maxWidth="sm" sx={{ mt: 4 }}>
      <Typography variant="h5" gutterBottom>
        Edit Profile
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Stack alignItems="center" mb={3}>
        <Avatar
          src={avatar ? URL.createObjectURL(avatar) : resolveMediaUrl(user.avatar_url) ?? undefined}
          sx={{ width: 80, height: 80, mb: 1 }}
        />
        <Button component="label" variant="outlined" size="small">
          Change Photo
          <input
            type="file"
            hidden
            accept="image/*"
            onChange={(e) => setAvatar(e.target.files?.[0] ?? null)}
          />
        </Button>
      </Stack>

      <TextField
        label="Display Name"
        fullWidth
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        sx={{ mb: 2 }}
      />
      <TextField
        label="Bio"
        fullWidth
        multiline
        rows={3}
        value={bio}
        onChange={(e) => setBio(e.target.value)}
        sx={{ mb: 3 }}
      />

      <Box display="flex" gap={1}>
        <Button onClick={() => navigate(-1)}>Cancel</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Save"}
        </Button>
      </Box>
    </Container>
  );
}
