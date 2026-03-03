import React from "react";
import { useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  List,
  ListItemButton,
  ListItemAvatar,
  ListItemText,
  Avatar,
  CircularProgress,
  Box,
  Button,
  Chip,
} from "@mui/material";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { getNotifications, markAllRead } from "../../services/notificationService";
import { resolveMediaUrl } from "../../services/apiClient";

export default function NotificationsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(),
  });

  const markMutation = useMutation({
    mutationFn: markAllRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  return (
    <Container maxWidth="md" sx={{ mt: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Notifications</Typography>
        <Button
          size="small"
          onClick={() => markMutation.mutate()}
          disabled={markMutation.isPending}
        >
          Mark all read
        </Button>
      </Box>

      {isLoading && (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      )}

      <List>
        {(data?.results ?? []).map((n) => (
          <ListItemButton
            key={n.notification_id}
            onClick={() => {
              if (n.target_type === "post") navigate(`/post/${n.target_id}`);
              else navigate(`/profile/${n.target_id}`);
            }}
            sx={{ bgcolor: n.is_read ? "transparent" : "action.hover", mb: 0.5, borderRadius: 1 }}
          >
            <ListItemAvatar>
              <Avatar src={resolveMediaUrl(n.actor_avatar_url) ?? undefined} />
            </ListItemAvatar>
            <ListItemText
              primary={n.message || `${n.actor_display_name} ${n.type}d your ${n.target_type}`}
              secondary={new Date(n.create_time).toLocaleString()}
            />
            <Chip label={n.type} size="small" variant="outlined" />
          </ListItemButton>
        ))}
      </List>

      {data && data.results.length === 0 && (
        <Typography color="text.secondary" textAlign="center" mt={4}>
          No notifications yet.
        </Typography>
      )}
    </Container>
  );
}
