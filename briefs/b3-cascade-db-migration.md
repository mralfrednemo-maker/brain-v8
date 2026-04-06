# Evaluate and Recommend: Database Migration Strategy for Legacy Monolith

## Background

Our core product runs on a 9-year-old PostgreSQL 11 monolith database (single primary, 2 read replicas) serving a B2B insurance platform. The database holds 4.2 TB of production data, processes 8,000 transactions per second during business hours, and has accumulated 847 tables with complex cross-schema foreign key relationships.

PostgreSQL 11 reaches end of life in November 2026. Our DBA team (2 people) has been patching it manually since the last community update.

## What we need

First, assess the technical risk of staying on PostgreSQL 11 past EOL — determine the factual severity of continuing without upstream security patches, considering our compliance obligations (SOC 2 Type II, annual PCI-DSS assessment for payment processing module).

Then, recommend which migration path we should take. The options are not fully defined — we need the analysis to surface what the realistic paths are and which one best fits our constraints.

## Constraints

- Zero planned downtime during business hours (06:00-22:00 EST, Mon-Sat)
- Must maintain referential integrity across all 847 tables
- Payment processing module cannot be degraded during migration
- DBA team capacity: 2 FTEs, no external contractors approved yet
- Budget ceiling: $400,000 including any tooling, temporary infrastructure, and overtime

## Known complicating factors

- 23 stored procedures contain business logic that is not documented elsewhere
- The read replicas use logical replication with custom publication filters
- Three downstream analytics pipelines consume the WAL stream directly
- Our largest table (claim_events) has 1.8 billion rows with no partition strategy
