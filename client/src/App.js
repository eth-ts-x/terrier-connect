import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import Header from "./components/Header";
import HomePage from "./components/Home";
import Profile from "./components/Profile";
import EditProfile from "./components/EditProfile";
import ChangePassword from "./components/ChangePassword";
import Index from "./components/Index";
import UserMessages from "./pages/follower";
import PostSearch from "./pages/search";
import PostWithID from "./pages/forumPost/post";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";

// Wrapper: hide the Header on the /login page
const HeaderWrapper = ({ children }) => {
  const location = useLocation();
  const showHeader = location.pathname !== "/login";
  return (
    <>
      {showHeader && <Header />}
      {children}
    </>
  );
};

function App() {
  return (
    <Router>
      <AuthProvider>
        <HeaderWrapper>
          <Routes>
            {/* Default: redirect root to /home */}
            <Route path="/" element={<Navigate to="/home" replace />} />

            {/* Public login page */}
            <Route path="/login" element={<Index />} />

            {/* Public routes */}
            <Route path="/home" element={<HomePage />} />
            <Route path="/post/:id" element={<PostWithID />} />
            <Route path="/search" element={<PostSearch />} />
            <Route path="/profile/:id" element={<Profile />} />

            {/* Protected routes — require authentication */}
            <Route
              path="/profile/me"
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile/me/edit"
              element={
                <ProtectedRoute>
                  <EditProfile />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile/me/change-password"
              element={
                <ProtectedRoute>
                  <ChangePassword />
                </ProtectedRoute>
              }
            />
            <Route
              path="/follower"
              element={
                <ProtectedRoute>
                  <UserMessages />
                </ProtectedRoute>
              }
            />
          </Routes>
        </HeaderWrapper>
      </AuthProvider>
    </Router>
  );
}

export default App;

