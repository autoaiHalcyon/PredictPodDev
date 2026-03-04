import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Toast from '../components/Toast';
import './AuthPages.css';

const ForgotPasswordPage = () => {
  const navigate = useNavigate();
  const { requestPasswordReset, isAuthenticated, loading: authLoading } = useAuth();
  const { showToast, Component: ToastComponent } = Toast();

  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [resetToken, setResetToken] = useState('');

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      navigate('/');
    }
  }, [isAuthenticated, authLoading, navigate]);

  const validateEmail = () => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      setError('Email is required');
      return false;
    } else if (!emailRegex.test(email)) {
      setError('Please enter a valid email address');
      return false;
    }
    setError('');
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateEmail()) {
      showToast(error, 'error');
      return;
    }

    setLoading(true);

    const result = await requestPasswordReset(email);

    if (result.success) {
      showToast('Password reset link sent to your email', 'success');
      // Store the reset token if provided (for demo purposes)
      if (result.reset_token) {
        setResetToken(result.reset_token);
      }
      setSubmitted(true);
    } else {
      showToast(result.error, 'error');
    }

    setLoading(false);
  };

  if (authLoading) {
    return <div className="auth-loading">Loading...</div>;
  }

  return (
    <div className="auth-page">
      <ToastComponent />
      <div className="auth-container">
        <div className="auth-box">
          {!submitted ? (
            <>
              <div className="auth-header">
                <h1>Forgot Password?</h1>
                <p>Enter your email to receive a password reset link</p>
              </div>

              <form onSubmit={handleSubmit} className="auth-form">
                {/* Email Field */}
                <div className="form-group">
                  <label htmlFor="email">Email Address</label>
                  <input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setError('');
                    }}
                    placeholder="john@example.com"
                    className={`form-input ${error ? 'input-error' : ''}`}
                    autoComplete="email"
                  />
                  {error && <span className="error-text">{error}</span>}
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading || authLoading}
                  className="auth-button"
                >
                  {loading ? 'Sending...' : 'Send Reset Link'}
                </button>
              </form>

              {/* Back to Login Link */}
              <div className="auth-footer">
                <p>
                  Remember your password?{' '}
                  <Link to="/login" className="auth-link">
                    Log In
                  </Link>
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="auth-header success-header">
                <h1>Check Your Email</h1>
                <p>We've sent a password reset link to:{' '}
                  <strong>{email}</strong>
                </p>
              </div>

              <div className="success-message">
                <p>Click the link in the email to reset your password. The link will expire in 24 hours.</p>
                
                {resetToken && (
                  <div className="token-section">
                    <p className="token-label">For testing purposes, your reset token is:</p>
                    <code className="token-code">{resetToken}</code>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(resetToken);
                        showToast('Token copied to clipboard', 'success');
                      }}
                      className="copy-button"
                    >
                      Copy Token
                    </button>
                  </div>
                )}

                <div className="success-actions">
                  <Link to="/login" className="auth-button">
                    Back to Log In
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setEmail('');
                      setSubmitted(false);
                      setResetToken('');
                    }}
                    className="auth-button secondary"
                  >
                    Try Another Email
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
