# Local Development Setup Guide

## Quick Start (Docker Compose)

The easiest way to get started is with Docker Compose:

```bash
# Navigate to project root
cd linkplease-assignment

# Set your API key (get from https://pseudogram-api.onrender.com/v1/keygen)
export PSEUDOGRAM_API_KEY="your-api-key"

# Start all services
docker-compose up

# Services available at:
# - Backend API: http://localhost:8000
# - Frontend: http://localhost:3000
# - PostgreSQL: localhost:5432 (linkplease/linkplease)
```

To stop:
```bash
docker-compose down
```

---

## Manual Setup (Local Development)

### 1. Prerequisites

```bash
# Python 3.11+
python --version

# Node.js 18+
node --version

# PostgreSQL 15+
psql --version

# Git
git --version
```

### 2. Database Setup

```bash
# Option A: Using Docker (recommended for local)
docker run --name linkplease-db \
  -e POSTGRES_DB=linkplease \
  -e POSTGRES_USER=linkplease \
  -e POSTGRES_PASSWORD=linkplease \
  -p 5432:5432 \
  -d postgres:15-alpine

# Option B: Using local PostgreSQL
createdb -U postgres linkplease
psql -U postgres -d linkplease -c "CREATE USER linkplease WITH PASSWORD 'linkplease';"
psql -U postgres -d linkplease -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO linkplease;"
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://linkplease:linkplease@localhost:5432/linkplease
PSEUDOGRAM_API_KEY=your-api-key-here
PSEUDOGRAM_BASE_URL=https://pseudogram-api.onrender.com
WEBHOOK_SECRET=your-webhook-secret
VERIFY_WEBHOOK_SIGNATURE=false
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
DEBUG=true
LOG_LEVEL=DEBUG
EOF

# Run migrations (tables created on startup)
# Run the API server
uvicorn app.main:app --reload --port 8000

# In another terminal:
# Run the worker
python -m app.worker
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:5173 in browser
```

---

## Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_webhooks.py

# Run with verbose output
pytest -v

# Run only specific test
pytest tests/test_webhooks.py::test_webhook_signature_verification -v
```

---

## Environment Variables

Create `.env` file in backend directory:

```env
# Database
DATABASE_URL=postgresql://linkplease:linkplease@localhost:5432/linkplease

# API Keys (NEVER commit these)
PSEUDOGRAM_API_KEY=your-api-key-here
WEBHOOK_SECRET=your-secret-here

# API Configuration
PSEUDOGRAM_BASE_URL=https://pseudogram-api.onrender.com
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
VERIFY_WEBHOOK_SIGNATURE=false

# Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

Create `.env.local` in frontend directory:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## Testing Locally

### Manual Testing

1. Create a rule:
```bash
curl -X POST http://localhost:8000/rules \
  -H "Content-Type: application/json" \
  -d '{"keyword": "HELLO", "dm_message": "Hi there!"}'
```

2. Send a webhook event:
```bash
python -m tests.webhook_test
```

3. Check stats:
```bash
curl http://localhost:8000/stats
```

### Automated Testing

```bash
# Run all tests
cd backend
pytest

# Run with coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Debugging

### Backend Logs

```bash
# In development (already verbose)
uvicorn app.main:app --reload

# Check worker logs
python -m app.worker
```

### Database Inspection

```bash
# Connect to PostgreSQL
psql -U linkplease -d linkplease -h localhost

# Useful queries:
SELECT * FROM rules;
SELECT * FROM events ORDER BY created_at DESC;
SELECT * FROM deliveries ORDER BY updated_at DESC;
SELECT * FROM rate_limit_buckets;
```

### Frontend Debugging

1. Open browser DevTools (F12)
2. Network tab: see API calls
3. Console tab: see errors
4. React DevTools extension: inspect components

---

## Common Issues

### "connection refused" to PostgreSQL
```bash
# Check if running
docker ps | grep postgres

# Start if needed
docker start linkplease-db

# Or run locally
pg_ctl start -D /usr/local/var/postgres
```

### "Module not found" errors
```bash
cd backend
pip install -r requirements.txt  # Re-install

cd frontend
npm install  # Re-install
```

### Webhook signature verification failing
```
Set VERIFY_WEBHOOK_SIGNATURE=false in .env for local testing
```

### Port already in use
```bash
# Find process using port
lsof -i :8000  # Backend
lsof -i :5173  # Frontend
lsof -i :5432  # Database

# Kill process
kill -9 <PID>
```

### Database migration issues
```bash
# Reset database (loses data!)
dropdb linkplease
createdb linkplease

# Recreate user
psql -U postgres -d linkplease -c "CREATE USER linkplease WITH PASSWORD 'linkplease';"
```

---

## Production-Like Testing

### 500-Event Load Test

```bash
# Start all services (docker-compose or manually)

# In backend directory:
python -m pytest tests/ -v

# Or test directly:
python tests/load_test_500_events.py
```

### Docker Build Testing

```bash
# Build images
docker-compose build

# Run stack
docker-compose up

# Watch logs
docker-compose logs -f backend
docker-compose logs -f worker
docker-compose logs -f frontend
```

---

## Git Workflow

```bash
# Clone repository
git clone https://github.com/your-user/linkplease-assignment
cd linkplease-assignment

# Create feature branch
git checkout -b feature/my-feature

# Make changes, commit
git add .
git commit -m "Implement feature"

# Push to GitHub
git push origin feature/my-feature

# Create pull request
```

---

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- ES7+ React/Redux/React-Native snippets
- Prettier
- SQLTools

`.vscode/settings.json`:
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "ms-python.python"
  },
  "[typescript]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

### PyCharm

- Mark `backend` as Sources Root
- Mark `frontend` as Excluded
- Run Python console with virtual environment

---

## Performance Optimization

### Backend
- Database connections: pool_size=20, max_overflow=40
- Worker concurrency: Adjust WORKER_CONCURRENCY
- Rate limiting: Tune RATE_LIMIT_REQUESTS

### Frontend
- Enable production build: `npm run build`
- Check bundle size: `npm run build -- --analyze`

---

## Useful Commands

```bash
# Backend

# Run server
uvicorn app.main:app --reload

# Run worker
python -m app.worker

# Run tests
pytest
pytest --cov=app tests/

# Format code
black app/

# Lint code
pylint app/

# Frontend

# Development server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Lint
npm run lint

# Docker

# Build all images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

---

## Next Steps

1. Get API key from https://pseudogram-api.onrender.com/v1/keygen
2. Set PSEUDOGRAM_API_KEY in .env
3. Start PostgreSQL
4. Run backend and worker
5. Run frontend
6. Visit http://localhost:5173
7. Create a rule
8. Send test webhook event
9. Check stats and deliveries

For production deployment, see [render.yaml](./render.yaml) and README.md.
