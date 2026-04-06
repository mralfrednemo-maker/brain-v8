# Technology Decision: Redis vs. PostgreSQL for Session Storage

## Context

We are building a new web application. We need to choose a session storage backend for user authentication sessions. We use server-side session storage (not stateless JWTs) because we require session revocation capability — users can log out from any device and their sessions must be invalidated within 1 second under normal operating conditions. Planned failover windows (e.g., RDS Multi-AZ failover, ElastiCache failover) are acceptable exceptions to this SLA — the sub-1s revocation applies to normal operation, not during infrastructure failover events.

Peak concurrent sessions: 50,000. Required session lookup latency: under 5ms P99 during normal operation. Sessions expire after 24 hours.

Our team has strong PostgreSQL expertise. We have no existing Redis deployment. The application is deployed on AWS.

## Options

**Option A: Redis (AWS ElastiCache, multi-node with replica)**
- In-memory key-value store designed for this exact use case
- Sub-millisecond GET/SET operations at scale
- Built-in TTL support eliminates manual session cleanup
- Multi-node configuration (1 primary + 1 replica); automatic failover in ~30s (acceptable per above)
- Cost: ~$300/month for a two-node ElastiCache cluster
- Additional operational overhead: new technology, separate cluster to manage

**Option B: PostgreSQL (existing RDS Multi-AZ instance)**
- Familiar to the team, no new infrastructure
- Connection pooling via PgBouncer: currently 100 pooled connections, can be scaled to 500 for session workload
- Measured latency in staging: 1.5-3ms at 20,000 concurrent connections on the session table
- Requires a background job to clean expired sessions
- Risk: at 50,000 peak sessions with per-request validation (95% read traffic), CPU load will increase from current 40% — estimated 60-70% at peak based on our load test extrapolation
- No additional infrastructure cost; reuses existing RDS instance

## Known facts

1. Redis GET/SET operations handle >100,000 ops/second at sub-millisecond latency. Well-established across deployments.
2. Our current RDS (db.t3.medium, Multi-AZ) runs at 40% CPU peak. Load tests project 60-70% CPU at target session load with PgBouncer at 500 connections.
3. A db.t3.medium instance has 2 vCPU and 4GB RAM — adequate for 500 PgBouncer connections and the projected session workload based on our load test data.
4. AWS ElastiCache multi-node Redis (primary + replica) costs ~$300/month.
5. Session access pattern: 95% reads (validation per request), 5% writes (login/logout/revocation).
6. The sub-5ms P99 SLA is contractually binding with enterprise customers under normal operation.
7. Redis 30s failover window is an accepted exception to the revocation SLA per our SLA contract.

## What we need

Recommend Option A or Option B for session storage. This is a well-defined technical trade-off with sufficient facts provided. We expect the models to converge on a recommendation.
