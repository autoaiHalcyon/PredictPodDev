import React from "react";
import "./App.css";
import "./index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import TopNavbar from "./components/TopNavbar";
import ProtectedRoute from "./components/ProtectedRoute";

// Alpha pages
import Dashboard       from "./pages/alpha/Dashboard";
import GameDetail      from "./pages/alpha/GameDetail";
import Trades          from "./pages/alpha/Trades";
import Portfolio       from "./pages/alpha/Portfolio";
import Phases          from "./pages/alpha/Phases";
import Rules           from "./pages/alpha/Rules";

// Auth pages (keep existing)
import LoginPage          from "./pages/LoginPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";

const AppContent = () => {
  const { isAuthenticated, loading } = useAuth();
  return (
    <div className="App min-h-screen" style={{ background: "#050911", minHeight: "100vh" }}>
      <BrowserRouter>
        {isAuthenticated && !loading && <TopNavbar />}
        <div className={isAuthenticated && !loading ? "" : ""}>
          <Routes>
            {/* Auth */}
            <Route path="/login"           element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/change-password" element={<ProtectedRoute><ChangePasswordPage /></ProtectedRoute>} />
            {/* Alpha app */}
            <Route path="/"              element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/game/:gameId"  element={<ProtectedRoute><GameDetail /></ProtectedRoute>} />
            <Route path="/trades"        element={<ProtectedRoute><Trades /></ProtectedRoute>} />
            <Route path="/portfolio"     element={<ProtectedRoute><Portfolio /></ProtectedRoute>} />
            <Route path="/phases"        element={<ProtectedRoute><Phases /></ProtectedRoute>} />
            <Route path="/rules"         element={<ProtectedRoute><Rules /></ProtectedRoute>} />
            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </div>
  );
};

export default function App() {
  return (
    <ThemeProvider defaultTheme="dark">
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}
