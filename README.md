# LinkPlease Assignment

A full-stack implementation of the LinkPlease assignment with a FastAPI backend, PostgreSQL database, durable delivery worker, PseudoGram integration, and React frontend.

## Overview

The system receives comment-created webhook events, matches comments against active keyword rules, creates durable DM delivery jobs, and sends DMs asynchronously through the PseudoGram API.

The implementation focuses on reliability requirements including:

- Durable webhook event persistence
- Idempotent webhook processing
- Duplicate delivery protection
- Asynchronous DM delivery through a worker
- Database-backed rate limiting
- Retry and exponential backoff handling
- Delivery status tracking
- Reconciliation with the external PseudoGram API
- Health and statistics endpoints
- Docker-based local development
- React frontend dashboard

## Live Deployment

The system is deployed and active in production:
- **Deployed Frontend URL**: [https://linkplease-frontend.onrender.com](https://linkplease-frontend.onrender.com) (configured via CORS origin policy)
- **Deployed Backend Base URL**: [https://linkplease-backend-vdr4.onrender.com](https://linkplease-backend-vdr4.onrender.com)

---

## API Contract

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/webhook` | Receive comment events |
| `POST` | `/rules` | Create keyword/DM rules |
| `GET` | `/stats` | Retrieve delivery statistics |

A health endpoint is also available: `GET /health`.

Interactive API documentation: `http://localhost:8000/docs`

---

## Architecture

```text
PseudoGram webhook
        |
        v
FastAPI /webhook
        |
        v
PostgreSQL event persistence
        |
        v
Active rule matching
        |
        v
Durable delivery queue
        |
        v
Background worker
        |
        v
PseudoGram DM API
        |
        v
Delivery reconciliation
        |
        v
PostgreSQL delivery status
```

---

## Reliability Features

### Durable webhook processing

Webhook events are persisted to PostgreSQL before the endpoint returns success.

Each event has a unique `event_id`, preventing the same webhook event from being processed multiple times.

### Duplicate delivery protection

A database uniqueness constraint protects against duplicate deliveries for the same rule and user combination.

Duplicate attempts are recorded and exposed through `/stats`.

### Asynchronous delivery

The webhook endpoint does not synchronously send DMs.

Instead, matching comments create durable delivery records. The worker processes these records independently.

### Rate limiting

DM sends use database-backed rate-limit reservation before making the outbound API request.

### Retry handling

Temporary failures are retried using exponential backoff with configurable limits.

Permanent failures are marked as failed and are not retried indefinitely.

### Idempotent external requests

DM requests include an idempotency key derived from the rule, user, and comment information (`rule_id:user_id:comment_id`).

### Delivery reconciliation

After a DM is accepted by PseudoGram, the worker periodically checks its external status.

The PseudoGram client accepts successful DM-send responses returned by the API, including HTTP `200` and `202` responses, and requires a valid `dm_id`.

The delivery is ultimately marked `DELIVERED` after the external status API confirms delivery.

### Detailed Features & Failures Documentation
For a complete breakdown of all reliability features, see [FEATURES.md](FEATURES.md). For detailed failure analysis and known architectural limitations, see [FAILURES.md](FAILURES.md).

---

## Case-Insensitive Keyword Matching

Rule keywords are normalized before matching.

For example, a rule created with `COLLEGEPRICE` matches:

- `COLLEGEPRICE please`
- `collegeprice please`
- `CollegePrice please`
- `CoLlEgEpRiCe please`

---

## Local Development

### Prerequisites

- Docker Desktop
- Git
- PowerShell or another terminal

### Environment Configuration

Create a local `.env` file in the project root.

Use `.env.example` as the template:

```powershell
Copy-Item .env.example .env
```

Then set the required PseudoGram API key in `.env`.

> **Important:** Do not commit `.env`. The repository's `.gitignore` excludes local environment files.

### Start the Application

From the project root:

```powershell
docker compose up -d
docker compose ps
```

Expected services:

- PostgreSQL
- Backend
- Worker
- Frontend

### Backend

- Backend: `http://localhost:8000`
- Swagger documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Frontend

- Frontend: `http://localhost:3000`

### Stop the Stack

```powershell
docker compose down
```

---

## Useful API Endpoints (Production Validation)

You can query the deployed production endpoints using PowerShell:

### Health Check (`GET /health`)
```powershell
Invoke-RestMethod "https://linkplease-backend-vdr4.onrender.com/health"
```

### Statistics (`GET /stats`)
```powershell
Invoke-RestMethod "https://linkplease-backend-vdr4.onrender.com/stats"
```

### Automation Rules (`GET /rules`)
```powershell
Invoke-RestMethod "https://linkplease-backend-vdr4.onrender.com/rules"
```

### Create Automation Rule (`POST /rules`)
```powershell
$body = @{
    keyword = "PRICING"
    dm_message = "Hi there! Our pricing starts at $10/month. Check it out!"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://linkplease-backend-vdr4.onrender.com/rules" -Method Post -ContentType "application/json" -Body $body
```

### Deliveries History (`GET /deliveries`)
```powershell
Invoke-RestMethod "https://linkplease-backend-vdr4.onrender.com/deliveries"
```

---

## Testing

### Backend Tests

The backend test suite uses a local SQLite test database for isolated tests and does not depend on the PostgreSQL container.

Run from the project root:

```powershell
docker compose exec backend pytest -q
```

Latest verified result:

```text
43 passed, 5 warnings
```

### Frontend Build

From the frontend directory:

```powershell
npm install
npm run build
```

---

## Local Integration Verification

The application was verified locally using PostgreSQL and the running Docker worker.

Verified behavior includes:

- Backend health check
- Rule creation
- Webhook ingestion
- Event persistence
- Keyword matching
- Asynchronous worker processing
- PseudoGram DM sending
- Delivery reconciliation
- Duplicate delivery protection
- Statistics reporting
- Real PseudoGram API-key configuration
- Case-insensitive keyword matching

Successful end-to-end tests resulted in deliveries reaching `DELIVERED`.

The statistics endpoint reported successful deliveries with zero failed or queued deliveries after processing.

---

## Production Simulator Verification

The final deployed implementation was validated using the live PseudoGram simulator:

- **Simulator Run ID**: `run_9514dea6b916`
- **Events Generated**: `500`
- **Webhook Delivery Attempts**: `536` (includes duplicate/redelivery tests)
- **Accepted Webhook Requests**: `536/536` returned `HTTP 200` (100% verification success rate)
- **Expected Unique Recipient Count**: `0`
- **Test Duration**: Approximately **71 seconds**
- **Stats Ingestion State**: Production statistics matched the expected simulator state.

*Expected Recipients Note*: The expected unique recipient count was zero because the only active production rule keyword was `TEST`, while the simulator's generated comments did not contain the word `TEST`.

---

## Security

Secrets are not stored in source-controlled files.

Docker Compose uses environment-variable interpolation:

```yaml
PSEUDOGRAM_API_KEY: ${PSEUDOGRAM_API_KEY}
```

The actual `.env` file is excluded by `.gitignore`.

Only `.env.example` is committed, containing placeholder values.

Webhook signature verification uses the exact raw request body and HMAC-SHA256. The deployed verifier follows the signing behavior observed from the live PseudoGram simulator, including deriving the signing key from the Base64 prefix of the configured PSEUDOGRAM_API_KEY when applicable.

---

## Project Structure

```text
linkplease-assignment/
├── backend/
│   ├── app/
│   └── tests/
├── frontend/
├── docker-compose.yml
├── render.yaml
├── .env.example
├── .gitignore
├── COMPLETENESS_CHECKLIST.md
├── FAILURES.md
├── FEATURES.md
├── IMPLEMENTATION_REPORT.md
├── LOCAL_SETUP.md
└── README.md
```

### Key files

- `backend/` - FastAPI backend, database models, worker, queue, API client, and tests
- `frontend/` - React frontend
- `docker-compose.yml` - local Docker configuration
- `render.yaml` - Render deployment configuration
- `.env.example` - safe environment-variable template
- `.gitignore` - excludes secrets and generated files
- `COMPLETENESS_CHECKLIST.md` - implementation checklist
- `FAILURES.md` - failure and verification notes
- `FEATURES.md` - implementation features list
- `IMPLEMENTATION_REPORT.md` - implementation details
- `LOCAL_SETUP.md` - local setup information

---

## Deployment

The repository includes `render.yaml` for deployment configuration.

Deployment verification has been performed against the live deployed services.

---

## Notes

This repository was developed and tested as a local and deployed full-stack implementation of the LinkPlease assignment.

The actual PseudoGram API was tested using the provided integration flow, and the worker successfully processed deliveries through to `DELIVERED`.