# LinkPlease assignment repository

This repository contains a backend + frontend implementation for the LinkPlease assignment. The source of truth for requirements is this README and the assignment brief in the workspace; this implementation is intended to satisfy the required API contract and the backend reliability guarantees described there.

## Status summary

- IMPLEMENTED: rule creation, webhook ingest, durable event persistence, database duplicate protections, status tracking, stats endpoint, and frontend dashboard wiring.
- TESTED LOCALLY: backend unit tests under SQLite; frontend production build.
- TESTED WITH POSTGRES: not executed in this environment.
- TESTED AGAINST REAL PSEUDOGRAM: not executed because credentials were unavailable in this session.
- DEPLOYMENT VERIFIED: not executed here.

## Required API contract

- POST /webhook
- POST /rules
- GET /stats

The implementation keeps these exact routes and required response shapes.

## Important implementation notes

- Webhook requests are verified using the raw request body and an HMAC-SHA256 comparison.
- Duplicate event_id values are protected by a database unique constraint.
- Same rule + user pairs are protected by a unique database constraint to prevent logical duplicate sends.
- The external DM API is called only by the worker, not synchronously from the webhook request path.
- Rate-limit reservation is performed atomically in the database before the outbound HTTP send.
- Delivery status is treated as accepted/queued at 202 and only counted as sent when confirmed as delivered by GET /v1/dm/{dm_id}.

## Local verification commands

From the backend directory:

```bash
python -m pytest -q
```

From the frontend directory:

```bash
npm install
npm run build
```

## Real PseudoGram integration note

Real PseudoGram integration test not executed because credentials were unavailable.

## Repository limitations

This repo is suitable for local validation and is aligned with the assignment contract, but real-network deployment and live simulator validation are not proven in this session.

— Ayush