import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Box,
  Menu,
  MenuItem,
  Badge,
  Avatar,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Divider,
} from "@mui/material";
import {
  Menu as MenuIcon,
  Add as AddIcon,
  Notifications as NotificationsIcon,
  Search as SearchIcon,
} from "@mui/icons-material";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../context/AuthContext";
import { getPopularHashtags } from "../services/hashtagService";
import { getUnreadCount } from "../services/notificationService";
import { resolveMediaUrl } from "../services/apiClient";
import SearchBar from "./SearchBar";
import NewPostModal from "./NewPostModal";

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [newPostOpen, setNewPostOpen] = useState(false);

  const { data: popular } = useQuery({
    queryKey: ["popular-hashtags"],
    queryFn: () => getPopularHashtags(10),
    staleTime: 60_000,
  });

  const { data: unread } = useQuery({
    queryKey: ["unread-count"],
    queryFn: getUnreadCount,
    enabled: !!user,
    refetchInterval: 30_000,
  });

  return (
    <>
      <AppBar position="sticky" color="primary">
        <Toolbar>
          <IconButton color="inherit" edge="start" onClick={() => setDrawerOpen(true)}>
            <MenuIcon />
          </IconButton>

          <Typography
            variant="h6"
            noWrap
            sx={{ cursor: "pointer", mr: 2 }}
            onClick={() => navigate("/home")}
          >
            Terrier Connect
          </Typography>

          <SearchBar />

          <Box sx={{ flexGrow: 1 }} />

          {user && (
            <>
              <IconButton color="inherit" onClick={() => setNewPostOpen(true)}>
                <AddIcon />
              </IconButton>
              <IconButton color="inherit" onClick={() => navigate("/notifications")}>
                <Badge badgeContent={unread?.count ?? 0} color="error">
                  <NotificationsIcon />
                </Badge>
              </IconButton>
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)}>
                <Avatar
                  src={resolveMediaUrl(user.avatar_url) ?? undefined}
                  alt={user.display_name}
                  sx={{ width: 32, height: 32 }}
                />
              </IconButton>
              <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={() => setAnchorEl(null)}
              >
                <MenuItem
                  onClick={() => {
                    setAnchorEl(null);
                    navigate("/profile/me");
                  }}
                >
                  Profile
                </MenuItem>
                <MenuItem
                  onClick={() => {
                    setAnchorEl(null);
                    navigate("/profile/me/edit");
                  }}
                >
                  Edit Profile
                </MenuItem>
                <MenuItem
                  onClick={async () => {
                    setAnchorEl(null);
                    await logout();
                    navigate("/login");
                  }}
                >
                  Logout
                </MenuItem>
              </Menu>
            </>
          )}

          {!user && (
            <IconButton color="inherit" onClick={() => navigate("/login")}>
              <Avatar sx={{ width: 32, height: 32 }} />
            </IconButton>
          )}
        </Toolbar>
      </AppBar>

      {/* Trending drawer */}
      <Drawer anchor="left" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Box sx={{ width: 260, p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Trending Tags
          </Typography>
          <Divider sx={{ mb: 1 }} />
          <List>
            {(popular ?? []).map((tag) => (
              <ListItemButton
                key={tag.hashtag_text}
                onClick={() => {
                  setDrawerOpen(false);
                  navigate(`/search?type=tag&query=${encodeURIComponent(tag.hashtag_text)}`);
                }}
              >
                <ListItemText
                  primary={`#${tag.hashtag_text}`}
                  secondary={`${tag.count} posts`}
                />
              </ListItemButton>
            ))}
            {(!popular || popular.length === 0) && (
              <Typography variant="body2" color="text.secondary" sx={{ px: 2 }}>
                No trending tags yet.
              </Typography>
            )}
          </List>
        </Box>
      </Drawer>

      {/* New post modal */}
      <NewPostModal open={newPostOpen} onClose={() => setNewPostOpen(false)} />
    </>
  );
}
