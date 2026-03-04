import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import TopNavbar from "./components/TopNavbar";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import GameDetail from "./pages/GameDetail";
import Portfolio from "./pages/Portfolio";
import Settings from "./pages/Settings";
import StrategyCommandCenter from "./pages/StrategyCommandCenter";
import EnhancedStrategyCommandCenter from "./pages/EnhancedStrategyCommandCenter";
import OptimizationCenter from "./pages/OptimizationCenter";
import AllGamesPage from "./pages/AllGamesPage";
import CapitalPreviewPage from "./pages/CapitalPreviewPage";
import DailyResults from "./pages/DailyResults";
import TradesCenter from "./pages/TradesCenter";
import LoginPage from "./pages/LoginPage";
// import SignupPage from "./pages/SignupPage"; // Signup disabled
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";

// Paper Trading Mode Banner Component
const PaperTradingBanner = () => (
  <div 
    data-testid="paper-trading-banner"
    className="fixed top-0 left-0 right-0 z-50 bg-amber-500 text-black px-4 py-2 text-center font-bold text-sm"
  >
    PAPER TRADING MODE - All trades are simulated. Live trading disabled until Kalshi API keys are configured.
  </div>
);

// Main app content with routing
const AppContent = () => {
  const { isAuthenticated, loading } = useAuth();
  const location = window.location.pathname;

  return (
    <div className="App min-h-screen bg-background text-foreground transition-colors duration-300">
      <BrowserRouter>
        {!isAuthenticated && !loading && location !== '/login' && window.history.replaceState({}, '', '/login')}
        {isAuthenticated && !loading && <PaperTradingBanner />}
        <div className={isAuthenticated && !loading ? "pt-10" : ""}>
          {isAuthenticated && !loading && <TopNavbar />}
          
          {/* Page Content */}
          <Routes>
            {/* Auth Routes - accessible to non-authenticated users */}
            <Route path="/login" element={<LoginPage />} />
            {/* Signup disabled - only login available */}
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/change-password" element={
              <ProtectedRoute>
                <ChangePasswordPage />
              </ProtectedRoute>
            } />

            {/* Protected Routes - require authentication */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/game/:gameId"
              element={
                <ProtectedRoute>
                  <GameDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/portfolio"
              element={
                <ProtectedRoute>
                  <Portfolio />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <Settings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/strategies"
              element={
                <ProtectedRoute>
                  <StrategyCommandCenter />
                </ProtectedRoute>
              }
            />
            <Route
              path="/strategy-command-center"
              element={
                <ProtectedRoute>
                  <EnhancedStrategyCommandCenter />
                </ProtectedRoute>
              }
            />
            <Route
              path="/optimization"
              element={
                <ProtectedRoute>
                  <OptimizationCenter />
                </ProtectedRoute>
              }
            />
            <Route
              path="/all-games"
              element={
                <ProtectedRoute>
                  <AllGamesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/capital/:gameId"
              element={
                <ProtectedRoute>
                  <CapitalPreviewPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/trades"
              element={
                <ProtectedRoute>
                  <TradesCenter />
                </ProtectedRoute>
              }
            />
            <Route
              path="/daily-results"
              element={
                <ProtectedRoute>
                  <DailyResults />
                </ProtectedRoute>
              }
            />

            {/* Fallback route */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </div>
  );
};

function App() {
  return (
    <ThemeProvider defaultTheme="dark">
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
