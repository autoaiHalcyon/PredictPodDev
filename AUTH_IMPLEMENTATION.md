# Authentication Implementation Guide

## Overview
This document describes the complete authentication system implementation for PredictPod, including sign-up, login, password management, and protected routes.

## Backend Implementation

### 1. Database Models
- **User Model** (`backend/models/user.py`): Defines user schemas for signup, login, and API responses
- **PasswordResetToken Model**: Manages password reset tokens

### 2. Authentication Services
- **AuthUtils** (`backend/services/auth_utils.py`):
  - `PasswordUtils`: Password hashing and verification using bcrypt
  - `JWTUtils`: JWT token generation and verification
  - `TokenUtils`: Reset token generation and hashing
  - `get_current_user()`: Dependency for protected routes

- **AuthService** (`backend/services/auth_service.py`):
  - `signup()`: User registration
  - `login()`: Email/password authentication
  - `change_password()`: Password change for authenticated users
  - `request_password_reset()`: Initiate forgot password flow
  - `reset_password()`: Complete password reset
  - `get_user()`: Fetch user profile

### 3. Database Repositories
- **UserRepository** (`backend/repositories/user_repository.py`):
  - Create user with password hashing
  - Get user by email/ID
  - Update password
  - User validation

- **PasswordResetTokenRepository**:
  - Create reset tokens
  - Verify reset tokens
  - Mark tokens as used

### 4. API Routes
All routes prefixed with `/api/auth`:

#### Public Routes
- `POST /signup` - User registration
- `POST /login` - User authentication
- `POST /forgot-password` - Request password reset
- `POST /reset-password` - Reset password with token

#### Protected Routes (require Bearer token)
- `GET /profile` - Get current user profile
- `POST /change-password` - Change password
- `POST /verify-token` - Verify authentication token

### 5. Server Integration
The authentication service is initialized in `server.py`:
- Repositories and service are created during app startup
- Auth router is included in the FastAPI app
- Global instances for dependency injection

## Frontend Implementation

### 1. Authentication Context
**File**: `frontend/src/context/AuthContext.js`

Provides:
- User state management
- Token storage and retrieval
- Authentication methods (signup, login, logout, etc.)
- Loading and error states
- `useAuth()` hook for component access

**Features**:
- Token persistence in localStorage
- Token validation on app load
- Error handling for all operations
- Automatic cleanup on logout

### 2. Authentication Pages

#### Sign-up Page (`frontend/src/pages/SignupPage.js`)
- Fields: Name, email, phone, password, confirm password
- Validation:
  - Name: Required, min 2 characters
  - Email: Valid email format
  - Phone: Valid phone format with min 10 digits
  - Password: Min 8 chars, uppercase, number
  - Password match confirmation
- Real-time validation feedback
- Toast notifications for success/error

#### Login Page (`frontend/src/pages/LoginPage.js`)
- Fields: Email, password
- "Remember me" functionality
- "Forgot password" link
- Toast notifications
- Redirect to dashboard on success

#### Forgot Password Page (`frontend/src/pages/ForgotPasswordPage.js`)
- Email input
- Sends reset link
- Displays token for testing (remove in production)
- Clear messaging about email sent
- Option to try another email

#### Change Password Page (`frontend/src/pages/ChangePasswordPage.js`)
- Current password verification
- New password with validation
- Confirm password field
- Protected route (requires authentication)
- Redirects to login if not authenticated

### 3. Protected Route Component
**File**: `frontend/src/components/ProtectedRoute.js`

- Wraps routes that require authentication
- Redirects to login if not authenticated
- Shows loading state while checking auth
- Preserves location for post-login redirect

### 4. Toast Notification System
**Files**: 
- `frontend/src/components/Toast.js`
- `frontend/src/components/Toast.css`

Features:
- Auto-dismiss after 4 seconds
- Success, error, warning, info types
- Smooth animations
- Dismissible by button click
- Fixed position (top-right)
- Dark mode support

### 5. TopNavbar Updates
Enhanced with:
- User profile dropdown
- Change password link
- Logout button
- User name and email display
- Auto-close on click outside
- Conditional rendering based on auth state

## Security Features

### Backend
1. **Password Security**:
   - Bcrypt hashing with 12 rounds
   - Passwords never returned in API responses
   - Constant-time comparison for verification

2. **Token Security**:
   - JWT with HS256 algorithm
   - 24-hour expiration
   - Secure signature verification
   - Token claims validation

3. **API Protection**:
   - Bearer token authentication
   - HTTPBearer dependency injection
   - Proper HTTP status codes
   - Error messages don't leak sensitive info

### Frontend
1. **Storage**:
   - Tokens in localStorage (consider upgrading to httpOnly cookies)
   - User data stored with token
   - Cleanup on logout

2. **Validation**:
   - Client-side input validation
   - Email format validation
   - Password strength requirements
   - Confirmation matching

3. **Communication**:
   - HTTPS in production (enforced via CORS)
   - Content-Type validation
   - Proper error handling

## Configuration

### Environment Variables
Backend:
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=predictpod
SECRET_KEY=your-secret-key-change-in-production
CORS_ORIGINS=http://localhost:3000
```

Frontend:
```
REACT_APP_BACKEND_URL=http://localhost:8000
```

### Token Configuration
Located in `backend/services/auth_utils.py`:
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7
```

## Testing

### Sign-up Flow
1. Navigate to `/signup`
2. Fill in all fields (validation triggers on input)
3. Submit form
4. Toast shows success message
5. Redirected to dashboard

### Login Flow
1. Navigate to `/login`
2. Enter email and password
3. Optionally check "Remember me"
4. Submit form
5. Redirected to dashboard

### Password Reset Flow
1. Click "Forgot password" on login page
2. Enter email
3. Receive reset token (in demo, shows in UI)
4. Use token to reset password
5. Can login with new password

### Protected Routes
1. Try accessing `/` without authentication
2. Redirected to `/login`
3. Login successfully
4. Access all protected routes
5. Logout clears session

## File Structure

```
Backend:
backend/
├── models/
│   └── user.py
├── repositories/
│   └── user_repository.py
├── routes/
│   └── auth.py
├── services/
│   ├── auth_utils.py
│   └── auth_service.py
└── server.py (updated)

Frontend:
frontend/src/
├── context/
│   └── AuthContext.js
├── pages/
│   ├── SignupPage.js
│   ├── LoginPage.js
│   ├── ForgotPasswordPage.js
│   └── ChangePasswordPage.js
├── components/
│   ├── Toast.js
│   ├── Toast.css
│   ├── ProtectedRoute.js
│   └── TopNavbar.js
└── App.js (updated)
```

## Future Enhancements

1. **Email Verification**:
   - Send verification email on signup
   - Verify email before account activation

2. **Refresh Tokens**:
   - Implement refresh token rotation
   - Longer-lived refresh tokens

3. **2FA/MFA**:
   - Two-factor authentication
   - SMS or authenticator app support

4. **Session Management**:
   - Device tracking
   - Session revocation
   - Login history

5. **Rate Limiting**:
   - Brute-force protection on login
   - Signup attempt limiting

6. **OAuth Integration**:
   - Google login
   - GitHub login
   - Facebook login

7. **Security Improvements**:
   - HttpOnly cookies for tokens
   - CSRF protection
   - Content Security Policy headers
   - API key management

## Troubleshooting

### "Invalid token" error
- Clear localStorage and reload
- Check backend SECRET_KEY configuration
- Verify token expiration

### Password validation fails
- Check password requirements (min 8 chars, uppercase, number)
- Ensure no extra spaces
- Verify password confirmation matches

### CORS errors on auth requests
- Check CORS_ORIGINS environment variable
- Verify frontend URL is in whitelist
- Check backend is running

### Database connection issues
- Verify MongoDB is running
- Check MONGO_URL configuration
- Ensure database name is correct

## Support
For issues or questions, refer to:
- Backend docs: `backend/routes/auth.py`
- Frontend docs: `frontend/src/context/AuthContext.js`
- Main README: `README.md`
