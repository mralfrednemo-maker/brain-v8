# Vendor Selection: Enterprise Observability Platform

## Context

We are a 200-person B2B SaaS company running a Kubernetes-based microservices architecture (38 services, 3 clusters, ~2,400 pods at peak). Our current observability stack is a patchwork of Prometheus + Grafana for metrics, ELK for logs, and Jaeger for traces. The team spends approximately 15 hours per week on observability maintenance and the tooling regularly fails during the incidents when we need it most.

Budget: $180,000/year. Timeline: must be operational within 90 days.

## Choose between these three options:

**Option A: Datadog Enterprise**
Full-stack observability with unified metrics, logs, traces, and APM. Per-host pricing model. Strong Kubernetes integration. Established vendor with broad ecosystem support. Estimated annual cost at our scale: $156,000.

**Option B: Grafana Cloud Pro**
Managed Grafana stack with Mimir (metrics), Loki (logs), and Tempo (traces). Open-source foundations with commercial support. Lower per-unit costs but requires more internal configuration. Estimated annual cost: $84,000.

**Option C: New Relic Full Platform**
All-in-one platform with user-based pricing (recently changed from host-based). Strong APM and error tracking. AI-powered anomaly detection. Estimated annual cost at our team size: $132,000.

## Decision criteria

Pick one. We cannot run two platforms — the whole point is consolidation. The winning vendor must handle metrics, logs, and distributed traces in a single pane. Consider: total cost of ownership (not just license), Kubernetes-native support quality, alert reliability during incidents, team ramp-up time, and vendor lock-in risk.
