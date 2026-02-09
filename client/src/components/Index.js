import React, { useState } from "react";
import {
  Box,
  Typography,
  TextField,
  Button,
  Container,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import { useNavigate } from "react-router-dom"; // Import useNavigate
import { login, register } from "../services/authService";
import { resolveMediaUrl } from "../services/apiClient";

const Index = () => {
  const [openRegister, setOpenRegister] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    avatar: null,
  });
  const [loading, setLoading] = useState(false); // For loading states
  const [error, setError] = useState(null); // For error handling
  const [user, setUser] = useState(null); // For storing logged-in user data

  const navigate = useNavigate(); // Initialize navigate

  // Open/Close Registration Dialog
  const handleRegisterOpen = () => setOpenRegister(true);
  const handleRegisterClose = () => setOpenRegister(false);

  // Handle login input changes
  const handleLoginChange = (e) => {
    setLoginForm({ ...loginForm, [e.target.name]: e.target.value });
  };

  // Handle register input changes
  const handleRegisterChange = (e) => {
    const { name, value } = e.target;
    setRegisterForm({ ...registerForm, [name]: value });
  };

  // Handle avatar upload
  const handleAvatarChange = (event) => {
    const file = event.target.files[0];
    setRegisterForm({ ...registerForm, avatar: file });
  };

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await login({
        email: loginForm.email,
        password: loginForm.password,
      });

      // Extract token and user information from the response
      const { token, user } = response;

      // Save user data to localStorage
      localStorage.setItem("token", token);
      localStorage.setItem("user", JSON.stringify(user));
      localStorage.setItem("userId", user.id); // Save user ID to localStorage

      console.log("Login successful:", response);

      // Update user state
      setUser(user);

      alert(`Welcome, ${user.display_name}!`);

      // Redirect to /home after login
      navigate("/home");
    } catch (err) {
      setError("Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  // Register API Call
  const handleRegister = async () => {
    setLoading(true);
    setError(null);
    const formData = new FormData();
    formData.append("username", registerForm.username);
    formData.append("email", registerForm.email);
    formData.append("password", registerForm.password);
    formData.append("confirmPassword", registerForm.confirmPassword);
    if (registerForm.avatar) {
      formData.append("avatar", registerForm.avatar);
    }

    try {
      const response = await register(formData);
      console.log("Registration Success:", response);
      alert("Registration successful!");
      handleRegisterClose(); // Close dialog after successful registration
    } catch (err) {
      setError("Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    // Clear the token and user data
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("userId"); // Remove user ID
    setUser(null);
    alert("You have been logged out.");
  };

  // Handle key press for login
  const handleKeyPress = (event) => {
    if (event.key === "Enter") {
      handleLogin();
    }
  };

  return (
    <Box
      sx={{
        bgcolor: "#F4F6F8",
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
      }}
    >
      <Container maxWidth="sm" sx={{ textAlign: "center", mt: 8 }}>
        <Typography
          variant="h3"
          color="#cc0000"
          sx={{ fontWeight: "bold", mb: 2 }}
        >
          Terrier Connect
        </Typography>
        <Typography variant="h6" sx={{ color: "gray", mb: 4 }}>
          Connect with friends and the BU community around you on Terrier
          Connect.
        </Typography>
        <Box
          sx={{
            boxShadow: 3,
            p: 4,
            borderRadius: 2,
            bgcolor: "white",
          }}
        >
          {!user ? (
            <>
              <TextField
                fullWidth
                name="email"
                variant="outlined"
                label="BU Email"
                value={loginForm.email}
                onChange={handleLoginChange}
                onKeyUp={handleKeyPress}
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                name="password"
                variant="outlined"
                label="Password"
                type="password"
                value={loginForm.password}
                onChange={handleLoginChange}
                onKeyUp={handleKeyPress}
                sx={{ mb: 3 }}
              />
              <Button
                fullWidth
                variant="contained"
                size="large"
                sx={{
                  mb: 2,
                  backgroundColor: "#CC0000",
                  "&:hover": { backgroundColor: "#990000" },
                }}
                onClick={handleLogin}
                disabled={loading}
              >
                {loading ? "Logging in..." : "Log In"}
              </Button>
              {error && (
                <Typography variant="body2" color="error" sx={{ mb: 2 }}>
                  {error}
                </Typography>
              )}
              <Button
                fullWidth
                variant="outlined"
                size="large"
                color="success"
                onClick={handleRegisterOpen}
              >
                Create new account
              </Button>
            </>
          ) : (
            <>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Welcome, {user.display_name}!
              </Typography>
              <Typography variant="body1" sx={{ mb: 4 }}>
                Email: {user.email}
              </Typography>
              <img
                src={resolveMediaUrl(user.avatar_url)}
                alt="User Avatar"
                style={{ width: "100px", height: "100px", borderRadius: "50%" }}
              />
              <Button
                fullWidth
                variant="contained"
                size="large"
                color="error"
                sx={{ mt: 4 }}
                onClick={handleLogout}
              >
                Log Out
              </Button>
            </>
          )}
        </Box>

        {/* Registration Dialog */}
        <Dialog open={openRegister} onClose={handleRegisterClose}>
          <DialogTitle>Create a new account</DialogTitle>
          <DialogContent>
            <TextField
              fullWidth
              name="username"
              variant="outlined"
              label="Username"
              value={registerForm.username}
              onChange={handleRegisterChange}
              sx={{ mt: 3, mb: 2 }}
            />
            <TextField
              fullWidth
              name="email"
              variant="outlined"
              label="Email"
              value={registerForm.email}
              onChange={handleRegisterChange}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              name="password"
              variant="outlined"
              label="Password"
              type="password"
              value={registerForm.password}
              onChange={handleRegisterChange}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              name="confirmPassword"
              variant="outlined"
              label="Confirm Password"
              type="password"
              value={registerForm.confirmPassword}
              onChange={handleRegisterChange}
              sx={{ mb: 2 }}
            />
            <Box sx={{ mt: 2, mb: 2 }}>
              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                Choose Avatar
              </Typography>
              <input
                accept="image/*"
                type="file"
                id="avatar-upload"
                style={{ display: "none" }}
                onChange={handleAvatarChange}
              />
              <label htmlFor="avatar-upload">
                <Button variant="outlined" component="span">
                  Upload Avatar
                </Button>
              </label>
              {registerForm.avatar && (
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Selected file: {registerForm.avatar.name}
                </Typography>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleRegisterClose} color="primary">
              Cancel
            </Button>
            <Button
              variant="contained"
              color="success"
              onClick={handleRegister}
              disabled={loading}
            >
              {loading ? "Registering..." : "Register"}
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
};

export default Index;
