import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

// Create Auth Context
const AuthContext = createContext(null);

// Helper function to safely parse JSON from response
const parseResponseJson = async (response) => {
  try {
    // Clone the response so we can read the body multiple times if needed
    const clonedResponse = response.clone();
    const text = await clonedResponse.text();
    
    // If response body is empty, return empty object
    if (!text) {
      return {};
    }
    
    // Try to parse as JSON
    return JSON.parse(text);
  } catch (err) {
    if (err instanceof SyntaxError) {
      throw new Error('Invalid JSON response from server');
    }
    throw err;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

  // Initialize auth state from localStorage
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const storedToken = localStorage.getItem('authToken');
        const storedUser = localStorage.getItem('authUser');

        if (storedToken && storedUser) {
          setToken(storedToken);
          setUser(JSON.parse(storedUser));

          // Verify token is still valid
          try {
            const response = await fetch(`${BACKEND_URL}/api/auth/verify-token`, {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${storedToken}`,
                'Content-Type': 'application/json',
              },
            });

            if (!response.ok) {
              // Token is expired, clear storage
              localStorage.removeItem('authToken');
              localStorage.removeItem('authUser');
              setToken(null);
              setUser(null);
            }
          } catch (err) {
            console.error('Token verification error:', err);
            localStorage.removeItem('authToken');
            localStorage.removeItem('authUser');
            setToken(null);
            setUser(null);
          }
        }
      } catch (err) {
        console.error('Auth initialization error:', err);
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, [BACKEND_URL]);

  // Sign up
  const signup = useCallback(async (userData) => {
    try {
      setError(null);
      setLoading(true);

      const response = await fetch(`${BACKEND_URL}/api/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
      });

      // Parse response once
      let data;
      try {
        data = await parseResponseJson(response);
      } catch (parseErr) {
        throw new Error(`Response error: ${response.status} - ${parseErr.message}`);
      }

      // Check if request was successful
      if (!response.ok) {
        throw new Error(data.detail || 'Sign-up failed');
      }

      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('authToken', data.access_token);
      localStorage.setItem('authUser', JSON.stringify(data.user));

      return { success: true, user: data.user };
    } catch (err) {
      const errorMessage = err.message || 'An error occurred during sign-up';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  }, [BACKEND_URL]);

  // Login
  const login = useCallback(async (email, password) => {
    try {
      setError(null);
      setLoading(true);

      const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      // Parse response once
      let data;
      try {
        data = await parseResponseJson(response);
      } catch (parseErr) {
        throw new Error(`Response error: ${response.status} - ${parseErr.message}`);
      }

      // Check if request was successful
      if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
      }

      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('authToken', data.access_token);
      localStorage.setItem('authUser', JSON.stringify(data.user));

      return { success: true, user: data.user };
    } catch (err) {
      const errorMessage = err.message || 'An error occurred during login';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  }, [BACKEND_URL]);

  // Logout
  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setError(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('authUser');
  }, []);

  // Change password
  const changePassword = useCallback(async (currentPassword, newPassword) => {
    try {
      setError(null);
      setLoading(true);

      const response = await fetch(`${BACKEND_URL}/api/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      // Parse response once
      let data;
      try {
        data = await parseResponseJson(response);
      } catch (parseErr) {
        throw new Error(`Response error: ${response.status} - ${parseErr.message}`);
      }

      // Check if request was successful
      if (!response.ok) {
        throw new Error(data.detail || 'Password change failed');
      }

      return { success: true };
    } catch (err) {
      const errorMessage = err.message || 'An error occurred while changing password';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  }, [BACKEND_URL, token]);

  // Request password reset
  const requestPasswordReset = useCallback(async (email) => {
    try {
      setError(null);
      setLoading(true);

      const response = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      // Parse response once
      let data;
      try {
        data = await parseResponseJson(response);
      } catch (parseErr) {
        throw new Error(`Response error: ${response.status} - ${parseErr.message}`);
      }

      // Check if request was successful
      if (!response.ok) {
        throw new Error(data.detail || 'Password reset request failed');
      }

      return { success: true, ...data };
    } catch (err) {
      const errorMessage = err.message || 'An error occurred during password reset request';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  }, [BACKEND_URL]);

  // Reset password
  const resetPassword = useCallback(async (token, newPassword) => {
    try {
      setError(null);
      setLoading(true);

      const response = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          token,
          new_password: newPassword,
        }),
      });

      // Parse response once
      let data;
      try {
        data = await parseResponseJson(response);
      } catch (parseErr) {
        throw new Error(`Response error: ${response.status} - ${parseErr.message}`);
      }

      // Check if request was successful
      if (!response.ok) {
        throw new Error(data.detail || 'Password reset failed');
      }

      return { success: true };
    } catch (err) {
      const errorMessage = err.message || 'An error occurred while resetting password';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    } finally {
      setLoading(false);
    }
  }, [BACKEND_URL]);

  // Get profile
  const getProfile = useCallback(async () => {
    try {
      setError(null);

      const response = await fetch(`${BACKEND_URL}/api/auth/profile`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      // Parse response once
      let profileData;
      try {
        profileData = await parseResponseJson(response);
      } catch (parseErr) {
        throw new Error(`Response error: ${response.status} - ${parseErr.message}`);
      }

      // Check if request was successful
      if (!response.ok) {
        throw new Error(profileData.detail || 'Failed to fetch profile');
      }

      setUser(profileData);
      localStorage.setItem('authUser', JSON.stringify(profileData));
      return { success: true, user: profileData };
    } catch (err) {
      const errorMessage = err.message || 'An error occurred while fetching profile';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    }
  }, [BACKEND_URL, token]);

  const value = {
    user,
    token,
    loading,
    error,
    isAuthenticated: !!token && !!user,
    signup,
    login,
    logout,
    changePassword,
    requestPasswordReset,
    resetPassword,
    getProfile,
    setError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Hook to use auth context
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
