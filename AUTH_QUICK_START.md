# Authentication Quick Start Guide

## Overview
This guide provides quick setup and usage instructions for the newly implemented authentication system in PredictPod.

## Prerequisites
- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:3000`
- MongoDB running and configured
- All dependencies installed

## Quick Setup

### 1. Backend Setup
The authentication service is already integrated into the main server. No additional setup needed beyond:

```bash
cd backend

# Ensure all dependencies are installed
pip install -r requirements.txt

# Run the server
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The authentication routes will be available at `/api/auth/*`

### 2. Frontend Setup
The authentication context and pages are already integrated:

```bash
cd frontend

# Install dependencies if needed
npm install

# Start development server
npm start
```

The app will automatically redirect unauthenticated users to `/login`.

## API Endpoints Quick Reference

### Public Endpoints
| Method | Endpoint | Body | Response |
|--------|----------|------|----------|
| POST | `/api/auth/signup` | `{name, email, phone, password}` | `{access_token, user}` |
| POST | `/api/auth/login` | `{email, password}` | `{access_token, user}` |
| POST | `/api/auth/forgot-password` | `{email}` | `{message, reset_token}` |
| POST | `/api/auth/reset-password` | `{token, new_password}` | `{message}` |

### Protected Endpoints (require Bearer token)
| Method | Endpoint | Authorization | Response |
|--------|----------|----------------|----------|
| GET | `/api/auth/profile` | Bearer {token} | `{user_info}` |
| POST | `/api/auth/change-password` | Bearer {token} | `{message}` |
| POST | `/api/auth/verify-token` | Bearer {token} | `{valid, user}` |

## User Flows

### Sign-up Flow
```
1. User visits /signup
2. Fills in: Name, Email, Phone, Password (8+ chars, uppercase, number)
3. Form validates on input
4. Click "Sign Up"
5. Toast shows success/error
6. Auto-redirects to dashboard on success
7. User logged in automatically
```

### Login Flow
```
1. User visits /login
2. Enters Email and Password
3. Optionally checks "Remember me"
4. Click "Log In"
5. Toast shows success/error
6. Auto-redirects to dashboard on success
7. Email saved if "Remember me" was checked
```

### Change Password
```
1. Click user avatar in top-right
2. Click "Change Password"
3. Enter current password, new password, confirm
4. Validates password strength
5. Click "Change Password"
6. Success message shows
7. Redirects to dashboard
```

### Forgot Password
```
1. Click "Forgot?" on login page
2. Enter email
3. Receive reset token (for testing)
4. Copy token or use from email
5. Enter new password with token
6. Password reset complete
7. Can login with new password
```

## Testing Guide

### Test Sign-up
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "password": "SecurePass123"
  }'
```

### Test Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123"
  }'
```

### Test Protected Route (with token)
```bash
curl -X GET http://localhost:8000/api/auth/profile \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Frontend Routes

### Public Routes
- `/login` - Login page
- `/signup` - Sign-up page
- `/forgot-password` - Forgot password page

### Protected Routes
- `/` - Dashboard (requires auth)
- `/all-games` - All games (requires auth)
- `/strategy-command-center` - Strategy center (requires auth)
- `/trades` - Trades (requires auth)
- `/portfolio` - Portfolio (requires auth)
- `/settings` - Settings (requires auth)
- `/change-password` - Change password (requires auth)

## Toast Notifications

The app uses toast notifications for all feedback:

### Success Messages
- ✓ Sign-up successful
- ✓ Login successful
- ✓ Password changed successfully
- ✓ Password reset link sent

### Error Messages
- ✗ Invalid email or password
- ✗ Email already registered
- ✗ Passwords do not match
- ✗ Password requirements not met

Notes:
- Auto-dismiss after 4 seconds
- Click X to dismiss manually
- Multiple toasts can appear
- Located in top-right corner

## Password Requirements

For registration and password changes:
- **Minimum length**: 8 characters
- **Must contain**:
  - At least 1 uppercase letter (A-Z)
  - At least 1 number (0-9)
- **Examples**:
  - ✓ SecurePass123
  - ✓ MyPassword2024
  - ✗ password123 (no uppercase)
  - ✗ PASSWORD (no number)

## Security Considerations

### For Deployment
- [ ] Change SECRET_KEY in backend/.env
- [ ] Enable HTTPS in production
- [ ] Use httpOnly cookies instead of localStorage (future)
- [ ] Implement rate limiting on auth endpoints
- [ ] Enable CORS only for trusted domains
- [ ] Set up email verification
- [ ] Consider 2FA implementation

### Best Practices
- Never commit .env with secrets
- Rotate SECRET_KEY regularly
- Monitor login attempts
- Implement account lockout after failed attempts
- Use HTTPS only in production
- Keep dependencies updated

## Troubleshooting

### Issue: "Cannot GET /login"
**Solution**: Ensure frontend is running and routes are configured correctly

### Issue: "Network Error" on login
**Solution**: 
- Verify backend is running
- Check REACT_APP_BACKEND_URL in .env
- Verify CORS origins in backend

### Issue: "Invalid token" on refresh
**Solution**:
- Clear browser localStorage
- Reload page
- Login again

### Issue: Password validation keeps failing
**Solution**:
- Password must be 8+ characters
- Must include uppercase letter
- Must include number
- No leading/trailing spaces

### Issue: Email already registered
**Solution**:
- Create account with different email
- Use "Forgot password" if you forgot your credentials
- Contact support if email was accidentally registered

## Development Tips

### Debug Authentication
```javascript
// In browser console
localStorage.getItem('authToken')  // View token
localStorage.getItem('authUser')   // View user info
```

### Test Protected Routes
1. Login successfully
2. Open browser DevTools
3. Go to localStorage
4. Delete authToken and authUser
5. Refresh page
6. Should redirect to login

### Toggle User Dropdown (TopNavbar)
1. Click user avatar in top-right
2. See dropdown menu with options
3. Click outside to close

## Environment Variables

### Backend (.env)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=predictpod
SECRET_KEY=your-secret-key-change-in-production
CORS_ORIGINS=http://localhost:3000
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=http://localhost:8000
```

## Files Modified/Created

### Backend
- ✓ models/user.py (NEW)
- ✓ repositories/user_repository.py (NEW)
- ✓ services/auth_utils.py (NEW)
- ✓ services/auth_service.py (NEW)
- ✓ routes/auth.py (NEW)
- ✓ server.py (UPDATED)

### Frontend
- ✓ context/AuthContext.js (NEW)
- ✓ pages/SignupPage.js (NEW)
- ✓ pages/LoginPage.js (NEW)
- ✓ pages/ForgotPasswordPage.js (NEW)
- ✓ pages/ChangePasswordPage.js (NEW)
- ✓ pages/AuthPages.css (NEW)
- ✓ components/ProtectedRoute.js (NEW)
- ✓ components/Toast.js (NEW)
- ✓ components/Toast.css (NEW)
- ✓ components/TopNavbar.js (UPDATED)
- ✓ App.js (UPDATED)

## Documentation

For more detailed information:
- See [AUTH_IMPLEMENTATION.md](./AUTH_IMPLEMENTATION.md) for complete documentation
- Check inline code comments for implementation details
- Review API documentation in route files

## Support

For issues:
1. Check CORS configuration
2. Verify environment variables
3. Check browser console for errors
4. Check backend logs
5. Verify MongoDB connection

## Next Steps

1. Test all authentication flows
2. Set up email service for password reset emails
3. Implement 2FA
4. Add refresh token rotation
5. Set up monitoring for failed logins
6. Configure production environment variables
