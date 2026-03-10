import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  Link,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
} from "@mui/material";
import { Google as GoogleIcon } from "@mui/icons-material";
import { useGoogleLogin } from "@react-oauth/google";
import { useAuth } from "../../context/AuthContext";
import { login, register, googleLogin } from "../../services/authService";

const GOOGLE_ENABLED = !!process.env.REACT_APP_GOOGLE_CLIENT_ID;

/* Extracted so that useGoogleLogin hook is only mounted when the provider exists. */
function GoogleLoginButton({ onSuccess, onError }: {
  onSuccess: (accessToken: string) => void;
  onError: () => void;
}) {
  const handleGoogle = useGoogleLogin({
    onSuccess: (res) => onSuccess(res.access_token),
    onError: () => onError(),
  });
  return (
    <>
      <Divider sx={{ my: 2 }}>or</Divider>
      <Button
        variant="outlined"
        fullWidth
        startIcon={<GoogleIcon />}
        onClick={() => handleGoogle()}
        sx={{ mb: 2 }}
      >
        Continue with Google
      </Button>
    </>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { setUser } = useAuth();

  // Login state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // Register dialog
  const [regOpen, setRegOpen] = useState(false);
  const [regEmail, setRegEmail] = useState("");
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");
  const [regError, setRegError] = useState("");

  const handleLogin = async () => {
    try {
      const { user } = await login(email, password);
      setUser(user);
      navigate("/home");
    } catch (e: any) {
      setError(e.response?.data?.detail || "Login failed.");
    }
  };

  const handleRegister = async () => {
    setRegError("");
    if (regPassword !== regConfirm) {
      setRegError("Passwords do not match.");
      return;
    }
    try {
      const fd = new FormData();
      fd.append("email", regEmail);
      fd.append("username", regUsername);
      fd.append("password", regPassword);
      fd.append("confirmPassword", regConfirm);
      const { user } = await register(fd);
      setUser(user);
      navigate("/home");
    } catch (e: any) {
      const data = e.response?.data;
      setRegError(
        typeof data === "string"
          ? data
          : Object.values(data || {}).flat().join(" ")
      );
    }
  };

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      bgcolor="background.default"
    >
      <Card sx={{ width: 400, p: 2 }}>
        <CardContent>
          <Typography variant="h5" textAlign="center" gutterBottom>
            Terrier Connect
          </Typography>
          <Typography variant="body2" color="text.secondary" textAlign="center" mb={3}>
            BU Community Social Platform
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <TextField
            label="Email"
            fullWidth
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            sx={{ mb: 2 }}
          />
          <Button variant="contained" fullWidth onClick={handleLogin} sx={{ mb: 1.5 }}>
            Login
          </Button>

          {GOOGLE_ENABLED && (
            <GoogleLoginButton
              onSuccess={async (accessToken) => {
                try {
                  const { user } = await googleLogin(accessToken);
                  setUser(user);
                  navigate("/home");
                } catch {
                  setError("Google login failed.");
                }
              }}
              onError={() => setError("Google login failed.")}
            />
          )}

          <Typography variant="body2" textAlign="center">
            No account?{" "}
            <Link component="button" onClick={() => setRegOpen(true)}>
              Register
            </Link>
          </Typography>
        </CardContent>
      </Card>

      {/* Register dialog */}
      <Dialog open={regOpen} onClose={() => setRegOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Create Account</DialogTitle>
        <DialogContent>
          {regError && <Alert severity="error" sx={{ mb: 2 }}>{regError}</Alert>}
          <TextField
            label="Email"
            fullWidth
            value={regEmail}
            onChange={(e) => setRegEmail(e.target.value)}
            sx={{ mb: 2, mt: 1 }}
          />
          <TextField
            label="Username"
            fullWidth
            value={regUsername}
            onChange={(e) => setRegUsername(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            value={regPassword}
            onChange={(e) => setRegPassword(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            label="Confirm Password"
            type="password"
            fullWidth
            value={regConfirm}
            onChange={(e) => setRegConfirm(e.target.value)}
            sx={{ mb: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRegOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleRegister}>
            Register
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
