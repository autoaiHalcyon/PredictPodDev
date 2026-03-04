# Authentication System - Integration & Setup Guide

## Integration Overview
This document provides step-by-step instructions for integrating and running the complete authentication system.

## Pre-Integration Checklist

### Backend Requirements
- [x] Python 3.8+
- [x] MongoDB instance running
- [x] FastAPI installed
- [x] Motor (async MongoDB driver) installed
- [x] PyJWT installed
- [x] python-jose installed
- [x] Bcrypt installed
- [x] Email-validator installed
- [x] Pydantic and pydantic-settings installed

### Frontend Requirements
- [x] Node.js 14+
- [x] React 18+
- [x] React Router v6+ installed
- [x] Lucide React (icons)

## Backend Integration Steps

### 1. Verify Dependencies
All required packages are already in `requirements.txt`. Verify they're present:

```bash
# Check for these packages:
grep -E "PyJWT|python-jose|bcrypt|email-validator|passlib" backend/requirements.txt
```

Expected output:
```
PyJWT==2.11.0
python-jose==3.5.0
bcrypt==4.1.3
email-validator==2.3.0
passlib[bcrypt]==1.7.4  # (may vary)
```

### 2. Environment Configuration
Create or update `backend/.env`:

```env
# MongoDB Configuration
MONGO_URL=mongodb://localhost:27017
DB_NAME=predictpod

# JWT Configuration
SECRET_KEY=your-secret-key-change-in-production-2024

# CORS Configuration
CORS_ORIGINS=http://localhost:3000

# Additional Settings
DEBUG=True
LOG_LEVEL=INFO
```

⚠️ **Important**: Change `SECRET_KEY` before deploying to production!

### 3. Database Setup
MongoDB collections will be created automatically on first run:

```bash
cd backend

# Ensure MongoDB is running
# Windows: mongod.exe
# Mac: brew services start mongodb-community
# Linux: sudo systemctl start mongod

# Start the backend server
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The server will:
- Create `users` collection
- Create `password_reset_tokens` collection
- Create necessary indexes
- Log initialization messages

### 4. Verify Backend Routes
Check that auth routes are available:

```bash
# Health check
curl http://localhost:8000/api/health

# Should return:
# {"status": "running", "db_ping": true, ...}

# Try signup
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+1234567890",
    "password": "TestPass123"
  }'
```

✅ Success: Returns access token and user information

## Frontend Integration Steps

### 1. Environment Configuration
Create or update `frontend/.env`:

```env
REACT_APP_BACKEND_URL=http://localhost:8000
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
```

### 2. Verify Dependencies
React Router should already be installed. Verify:

```bash
cd frontend

# Check for required packages
npm list react-router-dom

# Should show: react-router-dom@6.x.x
```

If not installed:
```bash
npm install react-router-dom@latest lucide-react
```

### 3. Start Frontend Development Server
```bash
cd frontend

# Install dependencies (if needed)
npm install

# Start development server
npm start

# Opens at http://localhost:3000
```

### 4. Verify Frontend Routes
Browser should automatically redirect to login page:
- `http://localhost:3000/login` - Login page
- `http://localhost:3000/signup` - Sign-up page
- `http://localhost:3000/forgot-password` - Forgot password

## Complete Integration Test

### 1. Test Sign-up Flow
1. Open `http://localhost:3000`
2. Should redirect to `/login`
3. Click "Sign Up"
4. Fill form:
   - Name: "Test User"
   - Email: "testuser@example.com"
   - Phone: "+1 (234) 567-8900"
   - Password: "TestPass123"
   - Confirm: "TestPass123"
5. Click "Sign Up"
6. Should see success toast
7. Should redirect to dashboard

### 2. Test Login Flow
1. After signup, you should be logged in
2. Click user avatar (top-right)
3. Click "Log Out"
4. Should redirect to login
5. Enter credentials from signup
6. Click "Log In"
7. Should see success toast
8. Should redirect to dashboard

### 3. Test Change Password
1. Click user avatar
2. Click "Change Password"
3. Enter current password: "TestPass123"
4. Enter new password: "NewPass456"
5. Confirm: "NewPass456"
6. Click "Change Password"
7. Should see success toast
8. Should redirect to dashboard

### 4. Test Forgot Password
1. Go to login page
2. Click "Forgot?"
3. Enter email: "testuser@example.com"
4. Copy displayed token
5. Scroll to "Try Another Email" (or go back to login)
6. Once token received, can reset password

### 5. Test Protected Routes
1. Clear localStorage in DevTools
2. Refresh page
3. Should redirect to login
4. Login again
5. Should access dashboard

## Troubleshooting Integration

### Backend Won't Start

**Error**: `Address already in use`
```bash
# Kill process on port 8000
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :8000
kill -9 <PID>
```

**Error**: `MongoDB connection refused`
```bash
# Start MongoDB
# Windows: C:\Program Files\MongoDB\Server\bin\mongod.exe
# Mac: brew services start mongodb-community
# Linux: sudo systemctl start mongod

# Test connection
mongosh mongodb://localhost:27017/predictpod
```

**Error**: `Module not found`
```bash
# Install all dependencies
pip install -r requirements.txt

# Upgrade pip if needed
pip install --upgrade pip
```

#### Frontend Won't Start

**Error**: `yarn webpack error`
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm start
```

**Error**: `Port 3000 already in use`
```bash
# Kill process on port 3000
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :3000
kill -9 <PID>
```

### Login Not Working

**Error**: `Cannot POST /api/auth/login`
- [ ] Backend is running on port 8000
- [ ] CORS origins include `http://localhost:3000`
- [ ] `REACT_APP_BACKEND_URL` is correct in .env

**Error**: `Invalid email or password`
- [ ] Verify user was created in signup
- [ ] Check MongoDB for user document: `db.users.findOne({email: "..."})`
- [ ] Ensure password is entered correctly

**Error**: `Network error`
- [ ] Check backend console for errors
- [ ] Verify CORS middleware is configured
- [ ] Check browser network tab for actual error

### Protected Routes Not Working

**Error**: `Redirects to login even when logged in`
- [ ] Check localStorage for `authToken` and `authUser`
- [ ] Verify token hasn't expired
- [ ] Check backend SECRET_KEY matches token

**Error**: `Loading state stuck`
- [ ] Check browser console for errors
- [ ] Verify token verification endpoint works
- [ ] Check backend logs

## Performance Optimization

### Backend Optimization
1. **Database Indexing**: Already configured in UserRepository
2. **Connection Pooling**: Motor handles this automatically
3. **Async Operations**: All DB operations are async
4. **Rate Limiting**: Configured in server.py (500 req/60s)

### Frontend Optimization
1. **Code Splitting**: Auth pages are lazy-loaded
2. **Memoization**: Context avoids unnecessary re-renders
3. **localStorage**: Reduces auth verification calls
4. **CSS**: Only loads for visible components

## Monitoring & Logging

### Backend Logs
Check logs for:
- Authentication failures
- Invalid tokens
- Database errors
- CORS issues

```bash
# View logs
tail -f backend/startup.log
```

### Frontend Debug
Enable debug logging:

```javascript
// In browser console
localStorage.setItem('debug', 'auth:*')
```

## Database Inspection

### View Registered Users
```bash
# Connect to MongoDB
mongosh mongodb://localhost:27017/predictpod

# List all users
db.users.find().pretty()

# Find by email
db.users.findOne({email: "testuser@example.com"})

# Check password hash
db.users.findOne({email: "testuser@example.com"}).hashed_password
```

### Reset Database
```bash
# Drop users collection to start fresh
mongosh mongodb://localhost:27017/predictpod

use predictpod
db.users.deleteMany({})
db.password_reset_tokens.deleteMany({})

# Will be recreated on next auth request
```

## Security Verification

### Check Password Hashing
```bash
# MongoDB
db.users.findOne({email: "test@example.com"})
# Should see hashed_password starting with $2b$ (bcrypt format)
```

### Verify JWT Token
```javascript
// Decode token in browser console
const token = localStorage.getItem('authToken')
JSON.parse(atob(token.split('.')[1]))  // Payload
```

## Production Deployment Checklist

### Pre-Deployment
- [ ] Update SECRET_KEY in backend/.env
- [ ] Update CORS_ORIGINS for production domain
- [ ] Enable HTTPS only
- [ ] Set up email service for password resets
- [ ] Configure rate limiting
- [ ] Set up monitoring and alerts
- [ ] Enable database backups
- [ ] Review security headers

### Deployment Steps
1. Set environment variables on production server
2. Install dependencies: `pip install -r requirements.txt`
3. Run database migrations (if any)
4. Start backend: `gunicorn server:app`
5. Build frontend: `npm run build`
6. Deploy frontend to CDN or server
7. Configure reverse proxy (nginx)
8. Enable SSL/TLS certificates
9. Test all auth flows in production
10. Monitor logs and errors

### Post-Deployment
- [ ] Monitor auth failures
- [ ] Check performance metrics
- [ ] Review error logs
- [ ] Set up alerts for failures
- [ ] Backup database regularly

## Rollback Procedure

If issues occur in production:

1. **Revert frontend**:
   ```bash
   git revert <commit>
   npm run build
   # Deploy previous build
   ```

2. **Revert backend**:
   ```bash
   git revert <commit>
   # Restart application
   ```

3. **Database rollback** (if needed):
   ```bash
   # MongoDB backup/restore
   mongorestore --uri="mongodb://..." --archive=backup.archive
   ```

## Support & Maintenance

### Regular Maintenance
- Update dependencies quarterly
- Review and update SECRET_KEY annually
- Monitor failed login attempts
- Clean up expired password reset tokens
- Review access logs

### Common Issues Resolution
1. Clear browser cache and localStorage
2. Restart both backend and frontend
3. Verify MongoDB connection
4. Check network with DevTools
5. Review server logs

### Getting Help
1. Check AUTH_QUICK_START.md for common issues
2. Review AUTH_IMPLEMENTATION.md for technical details
3. Check code comments in implementation files
4. Review API responses for error details

## Maintenance Scripts

### Health Check
```bash
# Check all services
curl http://localhost:8000/api/health
curl http://localhost:3000/  # Should not error
```

### Database Cleanup
```bash
# Remove expired password reset tokens
mongosh mongodb://localhost:27017/predictpod

use predictpod
db.password_reset_tokens.deleteMany({expires_at: {$lt: new Date()}})
```

### Backup Database
```bash
mongodump --uri="mongodb://localhost:27017/predictpod" --out=./backup
```

---

**Last Updated**: February 23, 2026
**Version**: 1.0
**Status**: Ready for Production
