import React, { useState } from "react";
import {
  AppBar,
  Box,
  Toolbar,
  IconButton,
  Typography,
  Badge,
  MenuItem,
  Menu,
  Drawer,
  List,
  ListItem,
  ListItemText,
  Button,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import MenuIcon from "@mui/icons-material/Menu";
import NoteAddIcon from "@mui/icons-material/NoteAdd";
import AccountCircle from "@mui/icons-material/AccountCircle";
import MailIcon from "@mui/icons-material/Mail";
import NotificationsIcon from "@mui/icons-material/Notifications";
import MoreIcon from "@mui/icons-material/MoreVert";
import NewPostModal from "./NewPostButton";
import SearchBar from "./SearchBar";
import { getPopularHashtags } from "../services/hashtagService";
import { useAuth } from "../context/AuthContext";

export default function PrimarySearchAppBar() {
  const [anchorEl, setAnchorEl] = useState(null);
  const [mobileMoreAnchorEl, setMobileMoreAnchorEl] = useState(null);
  const [isSidebarOpen, setSidebarOpen] = useState(false); // Sidebar control
  const [tags, setTags] = useState([]); // To store tags
  const [modalOpen, setModalOpen] = useState(false);

  const navigate = useNavigate();
  const { logout } = useAuth();
  const isMenuOpen = Boolean(anchorEl);
  const isMobileMenuOpen = Boolean(mobileMoreAnchorEl);

  // Fetch popular tags
  const fetchTags = async () => {
    try {
      const response = await getPopularHashtags({ page: 1, pageSize: 10 });
      setTags(response.results);
    } catch (error) {
      console.error("Error fetching tags:", error);
    }
  };

  // Toggle sidebar with tags
  const toggleSidebar = (open) => async () => {
    setSidebarOpen(open);
    if (open) {
      await fetchTags(); // Fetch tags when opening the sidebar
    }
  };

  const handleProfileMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMobileMenuClose = () => {
    setMobileMoreAnchorEl(null);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    handleMobileMenuClose();
  };

  const handleMobileMenuOpen = (event) => {
    setMobileMoreAnchorEl(event.currentTarget);
  };

  const handleProfileClick = () => {
    handleMenuClose(); // Close the menu
    navigate("/profile/me"); // Navigate to the current user's profile
  };

  const handleLogout = () => {
    logout();
  };

  const menuId = "primary-search-account-menu";
  const renderMenu = (
    <Menu
      anchorEl={anchorEl}
      anchorOrigin={{
        vertical: "top",
        horizontal: "right",
      }}
      id={menuId}
      keepMounted
      transformOrigin={{
        vertical: "top",
        horizontal: "right",
      }}
      open={isMenuOpen}
      onClose={handleMenuClose}
    >
      <MenuItem onClick={() => navigate("/home")}>Home</MenuItem>
      <MenuItem onClick={handleProfileClick}>Profile</MenuItem>
      <MenuItem onClick={handleLogout}>Logout</MenuItem>
    </Menu>
  );

  const mobileMenuId = "primary-search-account-menu-mobile";
  const renderMobileMenu = (
    <Menu
      anchorEl={mobileMoreAnchorEl}
      anchorOrigin={{
        vertical: "top",
        horizontal: "right",
      }}
      id={mobileMenuId}
      keepMounted
      transformOrigin={{
        vertical: "top",
        horizontal: "right",
      }}
      open={isMobileMenuOpen}
      onClose={handleMobileMenuClose}
    >
      <MenuItem onClick={() => setModalOpen(true)}>NewPost</MenuItem>
      <MenuItem onClick={() => navigate("/home")}>Home</MenuItem>
      <MenuItem onClick={handleProfileClick}>Profile</MenuItem>
      <MenuItem onClick={handleLogout}>Logout</MenuItem>
    </Menu>
  );

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static">
        <Toolbar>
          {/* Drawer Button */}
          <IconButton
            size="large"
            edge="start"
            color="inherit"
            aria-label="open drawer"
            onClick={toggleSidebar(true)} // Open the sidebar
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          
          <Typography
            variant="h6"
            noWrap
            component="div"
            sx={{ display: { xs: "none", sm: "block" } }}
            onClick={() => navigate(`/home`)}
          >
            Terrier Connect
          </Typography>

          <SearchBar />

          <Box sx={{ flexGrow: 1 }} />
          <Box sx={{ display: { xs: "none", md: "flex" } }}>
            <IconButton
              size="large"
              aria-label="new notifications"
              color="inherit"
              onClick={() => setModalOpen(true)}
            >
              <Badge>
                <NoteAddIcon />
              </Badge>
            </IconButton>

            <IconButton
              size="large"
              edge="end"
              aria-label="account of current user"
              aria-controls={menuId}
              aria-haspopup="true"
              onClick={handleProfileMenuOpen}
              color="inherit"
            >
              <AccountCircle />
            </IconButton>
          </Box>

          <Box sx={{ display: { xs: "flex", md: "none" } }}>
            <IconButton
              size="large"
              aria-label="show more"
              aria-controls={mobileMenuId}
              aria-haspopup="true"
              onClick={handleMobileMenuOpen}
              color="inherit"
            >
              <MoreIcon />
            </IconButton>
          </Box>
        </Toolbar>
      </AppBar>

      {/* New Post Modal */}
      <NewPostModal open={modalOpen} handleClose={() => setModalOpen(false)} />

      {/* Sidebar Drawer */}
      <Drawer anchor="left" open={isSidebarOpen} onClose={toggleSidebar(false)}>
        <Box
          sx={{
            width: 250,
            p: 2,
            display: "flex",
            flexDirection: "column",
            height: "100%",
          }}
        >
          <Typography variant="h5" sx={{ mb: 2, fontWeight: "bold" }}>
            Most Popular Tags
          </Typography>

          {/* Display the tags */}
          <List>
            {tags.map((tag) => (
              <ListItem key={tag.id} button 
                onClick={() => navigate(`/search?searchType=tag&query=${tag.hashtag_text}`)}>
                <ListItemText primary={`#${tag.hashtag_text}`} />
              </ListItem>
            ))}
          </List>

          <Button
            variant="outlined"
            sx={{ mt: "auto" }}
            onClick={toggleSidebar(false)}
          >
            Close
          </Button>
        </Box>
      </Drawer>

      {renderMobileMenu}
      {renderMenu}
    </Box>
  );
}
