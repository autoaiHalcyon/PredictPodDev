# PredictPod - Probability Intelligence Terminal

A Bloomberg-style probability intelligence terminal for prediction markets, starting with NBA games from Kalshi.

## Features

- **Real-time NBA Data**: Live game scores from ESPN
- **Probability Engine**: Dynamic win probability calculations using logistic regression model
- **Signal Engine**: Composite trading signals with portfolio-aware recommendations
- **Live Charts**: Market vs Fair probability, Edge, and Volatility visualizations
- **Paper Trading**: Full position lifecycle with risk management
- **WebSocket Updates**: Real-time data streaming every 3-5 seconds
- **Rate Limiting**: API abuse protection (100 requests/minute)
- **Health Monitoring**: Comprehensive health checks with DB connectivity verification

## Tech Stack

- **Frontend**: React 19, Recharts, TailwindCSS, shadcn/ui
- **Backend**: FastAPI (Python), WebSockets, Pydantic
- **Database**: MongoDB
- **APIs**: ESPN (live scores), Kalshi (mocked for paper trading)

---

## Quick Start (Development)

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local development)
- Python 3.11+ (for local development)

### Running with Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd predictpod

# Start all services
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8001/api
```

### Running Locally

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your settings

# Start the server
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
yarn install

# Copy environment variables
cp .env.example .env

# Start development server
yarn start
```

---

## Production Deployment

### 1. Environment Variables

#### Backend (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_URL` | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net` |
| `DB_NAME` | Database name | `predictpod` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `https://predictpod.example.com` |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `100` |
| `RATE_LIMIT_WINDOW` | Rate limit window (seconds) | `60` |

**IMPORTANT**: Never use `CORS_ORIGINS=*` in production. Always specify exact origins.

#### Frontend (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `REACT_APP_BACKEND_URL` | Backend API URL | `https://api.predictpod.example.com` |

---

### 2. MongoDB Production Setup (MongoDB Atlas Recommended)

1. **Create MongoDB Atlas Cluster**:
   - Go to [MongoDB Atlas](https://www.mongodb.com/atlas)
   - Create a new cluster (M10+ recommended for production)
   - Choose your region for low latency

2. **Configure Security**:
   ```
   - Database Access: Create a user with readWriteAnyDatabase role
   - Network Access: Add your server IP(s) to allowlist
   - Enable TLS/SSL (enabled by default on Atlas)
   ```

3. **Connection String**:
   ```bash
   MONGO_URL=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
   ```

4. **Required Indexes** (automatically created on startup):
   ```javascript
   // Time-series optimization
   db.probability_ticks.createIndex({ "game_id": 1, "timestamp": -1 })
   db.probability_ticks.createIndex({ "timestamp": -1 })
   db.trades.createIndex({ "created_at": -1 })
   db.trades.createIndex({ "game_id": 1, "created_at": -1 })
   ```

---

### 3. SSL/TLS Configuration

#### Option A: Cloudflare (Recommended for Simplicity)

1. Add your domain to Cloudflare
2. Set SSL mode to "Full (Strict)"
3. Enable "Always Use HTTPS"
4. Point DNS to your server

#### Option B: AWS ALB + ACM

1. Request certificate in AWS Certificate Manager
2. Create Application Load Balancer
3. Configure HTTPS listener with ACM certificate
4. Forward to backend target group (port 8001)

#### Option C: Nginx with Let's Encrypt

```nginx
# /etc/nginx/sites-available/predictpod
server {
    listen 80;
    server_name predictpod.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name predictpod.example.com;

    ssl_certificate /etc/letsencrypt/live/predictpod.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/predictpod.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

Install certificate:
```bash
sudo certbot --nginx -d predictpod.example.com
```

---

### 4. Deployment Commands

```bash
# Build and start services
docker-compose -f docker-compose.yml up -d --build

# Check health
curl https://your-domain.com/api/health

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Scale if needed
docker-compose up -d --scale backend=2
```

---

### 5. Health Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Full health check with DB connectivity, uptime, tick count |
| `GET /api/health/ws` | WebSocket status and connection count |
| `GET /api/` | Basic API info and status |

Example health response:
```json
{
  "status": "healthy",
  "uptime_seconds": 3600,
  "components": {
    "database": { "status": "healthy", "connected": true },
    "espn_adapter": { "status": "healthy" },
    "kalshi_adapter": { "status": "healthy", "mode": "MOCKED (Paper Trading)" }
  },
  "metrics": {
    "total_ticks_stored": 10000,
    "paper_trading_mode": true,
    "live_trading_enabled": false
  }
}
```

---

### 6. Rate Limiting

The API implements rate limiting to prevent abuse:
- **Default**: 100 requests per 60 seconds per IP
- **Exempt**: Health check endpoints (`/api/health`, `/api/health/ws`)
- **Response**: HTTP 429 when limit exceeded

Configure via environment:
```bash
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

---

## Port Configuration

| Service | Port |
|---------|------|
| Frontend | 3000 |
| Backend | 8001 |
| MongoDB | 27017 |

---

## Project Structure

```
predictpod/
├── backend/
│   ├── adapters/           # External API adapters (ESPN, Kalshi)
│   ├── models/             # Data models
│   ├── repositories/       # Database repositories
│   ├── services/           # Business logic (Probability, Signal, Trade engines)
│   ├── server.py           # FastAPI application
│   ├── config.py           # Configuration
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # React components (charts, panels, ui)
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom hooks (WebSocket)
│   │   └── services/       # API service
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Testing

```bash
# Run backend tests
cd backend
pytest tests/ -v

# Run frontend build check
cd frontend
yarn build
```

---

## Deployment Checklist

- [ ] Set `MONGO_URL` to production MongoDB Atlas connection string
- [ ] Set `CORS_ORIGINS` to exact production domain(s) - NO wildcards
- [ ] Set `REACT_APP_BACKEND_URL` to production API URL
- [ ] Configure SSL/TLS (Cloudflare, ALB, or Nginx + Let's Encrypt)
- [ ] Verify MongoDB IP allowlist includes server IP
- [ ] Test health endpoints after deployment
- [ ] Verify rate limiting is working
- [ ] Confirm "PAPER TRADING MODE" banner is visible
- [ ] Set up monitoring and alerting

---

## Current Limitations

- **Kalshi API**: Currently **MOCKED** for paper trading. Live trading requires real API integration.
- **Pre-game Edge**: Edge is 0.0% for scheduled games (expected - Fair = Market before game starts)
- **Clutch Mode**: Only activates during live games in Q4 < 5:00

---

## License

Proprietary - All rights reserved
