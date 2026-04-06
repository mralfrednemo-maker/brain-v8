#!/usr/bin/env python3
"""
brain-v3-orchestrator.py — Brain V3 pipeline with demand-driven research + controller-level fixes.

Changes from V1:
  - Free-form brief input (no Layer 0/1 validation)
  - Search mode classification at startup: full / minimal / skip
  - R1→R2 research gate: Gap Extractor (Haiku) + Brave Search
  - R2→R3 research gate: Disagreement Extractor (Haiku) + Sonar Pro (full mode only)
  - Cumulative evidence injection into R2, R3, R4 prompts
  - Evidence NOT injected into Hermes synthesis prompt
  - Conditional output format (not mandatory sections)

V3 controller-level fixes (no changes to brains, gates, prompts, LLMs, or outcome format):
  - Fix 1: Cross-domain evidence rejection in EvidenceLedger.admit()
  - Fix 2: Ungrounded-statistic detector (log + interventional, post-round)
  - Fix 3: Between-round position-drift detector (log-only)
  - Fix 4: Explicit option preservation tracking (Haiku at startup + post-round scan)
  - Fix 5: Post-synthesis confidence adjustment in YAML frontmatter
  - Fix 6: Finance-context gate on ticker detection in search router
  - Fix 7: Expanded stoplist (infra/business/regulatory acronyms)

Round structure (unchanged from V1):
  Round 1: 4 LLMs in parallel  (r1, reasoner, glm5, kimi)
  Round 2: 3 LLMs in parallel  (r1, reasoner, glm5)
  Round 3: 2 LLMs in parallel  (r1, reasoner)
  Round 4: 2 LLMs in parallel  (r1, reasoner)

Usage:
  python3 brain-v2-orchestrator.py --brief /path/to/brief.md [--outdir /tmp/brain-xxx] [--rounds 1-4]
"""

import argparse
import json
import re
import subprocess
import os
import signal
import sys
import threading
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, "/home/node/.openclaw/workspace/scripts")
from brave_search import brave_search as _brave_search_formatted

MAX_ROUNDS = 4
SYNTHESIS_FINAL_STATUSES = {"COMPLETE"}
SYNTHESIS_MODEL = "anthropic/claude-sonnet-4-6"
HERMES_TIMEOUT_S = 7200
HERMES_STATUS_PATH = Path("/tmp/hermes-status.txt")

# ── OpenRouter / LLM config ───────────────────────────────────────────────────
OPENROUTER_API_KEY = "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"
HAIKU_MODEL = "anthropic/claude-haiku-4-5"
SONAR_MODEL = "perplexity/sonar-pro"

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path("/home/node/.openclaw/workspace/scripts")
INVOKE = {
    "r1":       SCRIPTS_DIR / "invoke-descartes.sh",
    "reasoner": SCRIPTS_DIR / "invoke-arch-reasoner.sh",
    "glm5":     SCRIPTS_DIR / "invoke-glm5.sh",
    "kimi":     SCRIPTS_DIR / "invoke-arch-kimi.sh",
}

PRIMARY_MODELS = {
    "r1":       "deepseek/deepseek-r1-0528",
    "reasoner": "deepseek-reasoner",
    "glm5":     "z-ai/glm-5",
    "kimi":     "moonshotai/kimi-k2",
}

ROUND1_MODELS   = ["r1", "reasoner", "glm5", "kimi"]
ROUND2_MODELS   = ["r1", "reasoner", "glm5"]
ROUND234_MODELS = ["r1", "reasoner"]

TIMEOUTS = {"r1": 720, "reasoner": 720, "glm5": 480, "kimi": 480}  # DeepSeek models (r1/reasoner) get 12min; others doubled to 8min

MIN_RESPONSE_BYTES = 500
INTER_ROUND_COOLDOWN_S = 15
COOLDOWN_PER_TRANSITION = {"r1_to_r2": 15, "r2_to_r3": 35, "r3_to_r4": 10}
WALL_CLOCK_BUDGET_S = 3600  # 60 min — accommodates retries with 720s timeouts

MODEL_MAX_RETRIES = {"r1": 2, "reasoner": 2, "glm5": 2, "kimi": 2}  # 2 retries = 3 total attempts
MODEL_RETRY_COOLDOWN_S = {"r1": 10, "reasoner": 10, "glm5": 10, "kimi": 10}  # 10s between retries
MODEL_MAX_TOKENS = {  # Passed as BRAIN_MAX_TOKENS env var to invoke scripts
    "r1": 30000,       # Thinking model — needs large budget for chain-of-thought
    "reasoner": 30000, # Thinking model — needs large budget for chain-of-thought
    "glm5": 16384,     # Standard model
    "kimi": 16384,     # Standard model
}

MAX_EVIDENCE_ITEMS = 10
MAX_BRAVE_QUERIES_FULL = 5
MAX_BRAVE_QUERIES_MINIMAL = 2
MAX_SONAR_QUERIES = 2

# ── Search mode classification helpers (transplanted from Chamber V3) ─────────

_HYPO_CLASSIFIER_COMMON_WORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "but", "is", "are", "was", "be", "by", "from", "that", "this", "it",
    "as", "if", "with", "not", "which", "their", "they", "have", "has",
    "been", "will", "can", "may", "should", "could", "would", "its",
    "we", "us", "do", "any", "all", "more", "than", "when", "how",
    "what", "who", "why", "where", "our", "your", "my", "his", "her",
    "there", "here", "then", "so", "no", "yes", "also",
    "about", "some", "into", "over", "after", "before", "while", "during",
})

_SECURITY_CLASS_TERMS_BASE = frozenset({
    "RCE", "XSS", "SQLI", "SQL", "CSRF", "SSRF", "LFI", "RFI", "XXE",
    "IDOR", "SSTI", "DOS", "DDOS", "UAF", "OOB", "BOF", "APT",
    "CVE", "CWE", "IOC", "TTP", "ATT", "CKM", "MITRE",
    "API", "JWT", "SAML", "LDAP", "SMB", "HTTP", "HTTPS",
    "TLS", "SSL", "SSH", "VPN", "IP", "TCP", "UDP",
    "POC", "CMD", "SYN", "ACK", "ACL", "IAM", "MFA",
    "EXEC", "VULN", "EXPLOIT", "PAYLOAD", "BYPASS", "FUZZ",
    "WAF", "IDS", "IPS", "SIEM", "SOC", "EDR", "XDR", "MDR",
    "SAST", "DAST", "RASP", "RBAC", "DMZ", "CDN", "DNS", "SDK",
    "OAUTH", "PKI", "PEM", "CVSS", "OWASP", "NIST", "CISA",
    "CKT", "TTPS", "IOA", "DLP", "CASB", "UEBA", "SOAR",
})

# V3 Fix 7: Infra/cloud acronyms — never treat as financial tickers
_INFRA_CLASS_TERMS = frozenset({
    "EKS", "GKE", "AKS", "ECS", "EC2", "RDS", "VPC", "ALB", "NLB", "ELB",
    "ASG", "AMI", "GCE", "GCS", "ACI", "ACR", "ARO", "ADF", "CDK", "SAM",
    "CLI", "SQS", "SNS", "SES", "DMS", "EMR", "MSK", "EFS", "FSX", "KMS",
    "HSM", "STS", "SSM", "NAT", "IGW", "TGW", "BGP", "OSPF", "MPLS", "LXC",
    "OCI", "OVH", "ARM", "GPU", "TPU", "NPU", "CPU", "RAM", "SSD", "NVME",
    "IOPS", "QPS", "TPS", "RPO", "RTO", "SLA", "SLO", "SLI", "K8S", "K8",
    "HELM", "ISTIO", "ETCD", "S3",
})

# V3 Fix 7: Business/regulatory/currency/general acronyms — hard stoplist
_BUSINESS_CLASS_TERMS = frozenset({
    "ARR", "MRR", "NRR", "CAC", "LTV", "GMV", "DAU", "MAU",
    "KPI", "OKR", "ROI", "NPS", "TAM", "SAM", "SOM", "MVP",
    "JIT", "AOT", "OOM", "TTL", "FIFO", "LIFO", "CRUD", "REST",
    "IDE", "TDD", "BDD", "ETL", "ELT", "CDC",
    "HIPAA", "GDPR", "CCPA", "SOX", "FERPA", "COPPA", "GLBA",
    "FISMA", "ITAR", "PII", "PHI", "PCI", "DORA", "NYDFS",
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "AUD", "CAD", "CHF",
    "CEO", "CTO", "CFO", "COO", "CIO", "CISO", "CSO",
    "SVP", "EVP", "PMO", "SRE", "DBA",
    "FAQ", "TBD", "WIP", "EOD", "ETA", "FYI",
    "SAAS", "PAAS", "IAAS", "CICD",
    "NLP", "LLM", "AGI", "RAG", "GPT", "CNN", "RNN", "GAN",
})

# V3 Fix 7: Merged stoplist
_SECURITY_CLASS_TERMS = _SECURITY_CLASS_TERMS_BASE | _INFRA_CLASS_TERMS | _BUSINESS_CLASS_TERMS

# V3 Fix 6: Finance-context signals — uppercase tokens only promoted to ticker
# if the brief contains at least one finance-domain signal
_FINANCE_CONTEXT_SIGNALS = frozenset({
    "stock", "share", "equity", "fund", "etf", "portfolio", "exchange",
    "nyse", "nasdaq", "s&p", "dow", "market cap", "dividend", "yield",
    "trading", "invest", "broker", "securities", "ticker", "holdings",
    "options", "futures", "derivatives", "hedge", "mutual fund",
    "expense ratio", "aum", "bond", "treasury", "ipo", "earnings",
})

_RELEVANCE_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "was", "be", "by", "at", "from", "that", "this", "it",
    "as", "if", "but", "not", "which", "their", "they", "have", "has",
    "been", "will", "can", "may", "should", "could", "would", "its",
    "our", "we", "us", "do", "any", "all", "more", "than", "when", "how",
})

_DOMAIN_SHORTTERMS = frozenset(t.lower() for t in _SECURITY_CLASS_TERMS) | frozenset({
    "rce", "xss", "api", "waf", "ids", "ips", "dos", "poc", "c2",
    "acl", "iam", "mfa", "vpn", "tls", "ssl", "ssh", "dns", "cdn",
    "sdk", "jwt", "pki", "pem", "soc", "edr", "xdr", "mdr",
})

_OFF_DOMAIN_SIGNALS = frozenset({
    "fema", "emergency management", "ai adoption", "public sector",
    "government", "federal agency", "municipal", "nonprofit",
    "homeland", "disaster response", "disaster relief",
})

# V3 Fix 1: Domain-family signal sets for cross-domain evidence rejection
_DOMAIN_FAMILY_MEDICAL = frozenset({
    "toxicological", "toxicology", "clinical triage", "clinical deterioration",
    "poisoning", "overdose", "serum levels", "nomogram", "acetaminophen",
    "pharmacokinetic", "pharmacological", "drug absorption",
    "emergency medicine", "patient", "diagnosis", "pathology", "symptom",
    "epidemiological", "morbidity", "mortality rate", "surgical",
    "therapeutic", "dosage", "bioavailability", "ingestion",
})
_DOMAIN_FAMILY_SECURITY = frozenset({
    "exploit", "vulnerability", "cve", "rce", "payload", "malware",
    "ransomware", "botnet", "lateral movement", "privilege escalation",
    "authentication bypass", "waf", "firewall", "intrusion", "breach",
    "patch", "zero-day", "proof-of-concept", "attack surface",
})
_DOMAIN_FAMILY_FINANCE = frozenset({
    "portfolio", "etf", "equity", "bond", "dividend", "yield",
    "expense ratio", "aum", "ticker", "mutual fund", "hedge fund",
    "options", "futures", "derivatives", "credit default",
})
_DOMAIN_FAMILY_INFRASTRUCTURE = frozenset({
    "kubernetes", "k8s", "redis", "postgres", "postgresql", "mysql",
    "mongodb", "database", "cluster", "pod", "container", "docker",
    "oomkill", "oom", "memory leak", "cpu spike", "latency", "throughput",
    "load balancer", "nginx", "haproxy", "cdn", "cache", "auto-scaling",
})
_DOMAIN_FAMILY_COMPLIANCE = frozenset({
    "hipaa", "gdpr", "pci", "sox", "ferpa", "ccpa", "phi", "pii",
    "breach notification", "regulatory", "compliance", "audit",
    "data protection", "privacy", "disclosure",
})
_DOMAIN_FAMILY_ENGINEERING = frozenset({
    "test suite", "test coverage", "technical debt", "code quality",
    "feature freeze", "sprint", "velocity", "ci/cd", "pipeline",
    "deployment", "release", "staging", "canary", "rollback",
    "schema drift", "regression test", "refactor",
})
_DOMAIN_FAMILY_AI_POLICY = frozenset({
    "bias", "false positive rate", "content moderation", "fairness",
    "demographic", "disparity", "threshold adjustment", "model retrain",
    "training data", "ai act", "algorithmic", "discrimination",
})
_DOMAIN_FAMILY_OPERATIONS = frozenset({
    "traffic spike", "ddos", "bot traffic", "auto-scaling", "scaling",
    "load", "capacity", "rate limiting", "throttl", "cdn",
    "cache hit", "backend response", "under attack mode",
})

def _detect_task_domain(topic_class: str, task: str) -> str:
    """V3 Fix 1: Detect which decision-class domain a task belongs to."""
    combined = f"{topic_class} {task}".lower()
    scores = {
        "security": sum(1 for kw in _DOMAIN_FAMILY_SECURITY if kw in combined),
        "infrastructure": sum(1 for kw in _DOMAIN_FAMILY_INFRASTRUCTURE if kw in combined),
        "compliance": sum(1 for kw in _DOMAIN_FAMILY_COMPLIANCE if kw in combined),
        "engineering": sum(1 for kw in _DOMAIN_FAMILY_ENGINEERING if kw in combined),
        "ai_policy": sum(1 for kw in _DOMAIN_FAMILY_AI_POLICY if kw in combined),
        "operations": sum(1 for kw in _DOMAIN_FAMILY_OPERATIONS if kw in combined),
        "finance": sum(1 for kw in _DOMAIN_FAMILY_FINANCE if kw in combined),
        "medical": sum(1 for kw in _DOMAIN_FAMILY_MEDICAL if kw in combined),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "unknown"

def _detect_evidence_domain(text: str) -> str:
    """V3 Fix 1: Detect which domain family an evidence snippet belongs to."""
    text = text.lower()
    scores = {
        "security": sum(1 for kw in _DOMAIN_FAMILY_SECURITY if kw in text),
        "medical": sum(1 for kw in _DOMAIN_FAMILY_MEDICAL if kw in text),
        "finance": sum(1 for kw in _DOMAIN_FAMILY_FINANCE if kw in text),
        "infrastructure": sum(1 for kw in _DOMAIN_FAMILY_INFRASTRUCTURE if kw in text),
        "compliance": sum(1 for kw in _DOMAIN_FAMILY_COMPLIANCE if kw in text),
        "engineering": sum(1 for kw in _DOMAIN_FAMILY_ENGINEERING if kw in text),
        "ai_policy": sum(1 for kw in _DOMAIN_FAMILY_AI_POLICY if kw in text),
        "operations": sum(1 for kw in _DOMAIN_FAMILY_OPERATIONS if kw in text),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "unknown"

_SELF_REF_PATTERNS = re.compile(
    r'\b(this\s+CVE|this\s+vulnerability|this\s+organization|this\s+company|'
    r'our\s+API|our\s+system)\b',
    re.IGNORECASE,
)
_DOLLAR_AMOUNT_PATTERN = re.compile(r'\$[\d,]+(?:\.\d+)?[KMBkm]?\b')
_ORG_INTERNAL_PATTERN = re.compile(
    r'\b(?:organization|company|firm|org)\b.{0,25}\b(?:internal|risk\s+policy|cost\s+estimate|'
    r'policy\s+document|budget|headcount)\b'
    r'|'
    r'\b(?:our|the)\s+(?:internal|policy|risk\s+management|cost\s+model)\b',
    re.IGNORECASE,
)
_CONV_PREFIX_PATTERN = re.compile(
    r'^(?:Clarification\s+on\s+(?:whether|if)\s+'
    r'|Explanation\s+of\s+why\s+'
    r'|Documentation\s+(?:showing|that|of)\s+'
    r'|Evidence\s+that\s+'
    r'|Proof\s+that\s+'
    r'|Confirmation\s+(?:that|of)\s+'
    r'|Information\s+(?:about|on)\s+'
    r')',
    re.IGNORECASE,
)

# V2 opinion-only patterns — skip research for pure reasoning/evaluation requests
_OPINION_PATTERNS = [
    r'\bevaluate\s+this\b',
    r'\bwhich\s+is\s+better\s+reasoning\b',
    r'\bstronger\s+argument\b',
    r'\banalyze\s+the\s+logic\s+of\b',
    r'\bphilosophical\s+implications\b',
    r'\bis\s+this\s+argument\s+valid\b',
    r'\bgiven\s+only\s+the\s+information\s+above\b',
]


# ── Evidence Ledger ───────────────────────────────────────────────────────────

class EvidenceLedger:
    """Lightweight evidence ledger for Brain V2 (no Pydantic, no async)."""

    def __init__(self, task: str):
        self.task = task
        self.topic_class: str = ""
        self.topic_keywords: set = set()
        self.task_domain: str = ""              # V3 Fix 1: cached task domain
        self.cross_domain_rejections: int = 0   # V3 Fix 1: counter
        self.items: list = []          # list of dicts with evidence_id, topic, fact, url, confidence
        self.content_hashes: dict = {} # content_key -> eid
        self.seen_urls: set = set()
        self.seen_brave_queries: set = set()
        self.counter: int = 0
        self.research_phases: list = []  # log of research phase summaries
        # V3 Fixes 2/3/4: tracking fields
        self.ungrounded_stats_by_round: dict = {}   # Fix 2
        self.position_fingerprints: dict = {}       # Fix 3
        self.explicit_options: list = []             # Fix 4
        self.option_drops_by_round: dict = {}       # Fix 4
        # Search-gate observability diagnostics (v6 transplant)
        self.search_mode: str = ""
        self.run_id: str = ""
        self.search_diag_router_confidence: str = ""
        self.search_diag_training_only_skips: int = 0
        self.search_diag_live_evidence_candidates: int = 0
        self.search_diag_live_retrieval_attempted: bool = False
        self.search_mode_escalated: bool = False
        self.search_diag_upfront_mode: str = ""  # immutable snapshot of mode before escalation
        self.search_mode_origin: str = ""  # "hard_rule" (regex CLEAR) or "llm_tiebreaker" (LLM override)
        # Phase 1 roadmap: gap tracking
        self.gaps_detected: list = []    # {gap_id, round, source, text}
        self.gaps_queried: list = []     # {gap_id, query_text, engine}
        self.gaps_dropped: list = []     # {gap_id, reason}
        # Phase 1 roadmap: decision provenance
        self.decisions: list = []        # {decision_type, trigger, inputs, reason, timestamp}
        # Phase 1 roadmap: execution state
        self.execution_events: list = [] # {type, stage, detail}
        # Phase 3A: position tracking
        self.model_positions_by_round: dict = {}   # {round_num: {model: position_record}}
        self.position_changes: list = []           # {model, from_round, to_round, ...}
        self.extracted_options: list = []           # for open-ended briefs (frozen after R1)
        # Phase 3A: evidence citation tracking
        self.evidence_citations_by_round: dict = {} # {round_num: {evidence_id: [model_names]}}
        # Phase 3A/4: state transitions
        self.state_transitions: list = []          # {from_state, to_state, trigger, timestamp}
        # V4: Blocker lifecycle ledger (reduced disagreement lifecycle, adapted from Chamber V10)
        # Each blocker: {blocker_id, kind, source_dimension, detected_round, status,
        #                status_history, models_involved, evidence_ids, resolution_note}
        # Statuses: OPEN, RESOLVED, DEFERRED, DROPPED
        self.blocker_ledger: list = []             # list of blocker dicts
        self.blocker_counter: int = 0
        self.blocker_id_map: dict = {}             # source_dimension -> blocker_id (dedup)
        # V6 Fix 1: Evidence contradiction tracking
        # Each: {contradiction_id, evidence_ids: [eid_a, eid_b], topic, severity,
        #         status: UNRESOLVED|RESOLVED|DOWNGRADED, detected_round}
        self.contradiction_ledger: list = []
        self.contradiction_counter: int = 0
        # V6 Fix 3: Minority argument carry-forward
        # Each: {round_dropped, model, position, argument_summary, evidence_cited, addressed_by}
        self.minority_archive: list = []
        # V6 Fix 4: Cap discard tracking
        self._cap_discards: int = 0

    def next_id(self) -> str:
        self.counter += 1
        return f"E{self.counter:03d}"

    def admit(self, topic: str, fact: str, url: str, confidence: str = "MEDIUM",
             log=None, first_available_round: int = 0) -> str | None:
        """Admit an evidence item. Returns canonical ID or None if deduped / ceiling hit / cross-domain.

        V5: Cap hits logged explicitly.
        V6: Cap eviction — when at cap, incoming evidence with higher task-keyword
        overlap evicts the weakest existing item instead of being silently discarded.
        """
        if url and url in self.seen_urls:
            return None
        content_key = f"{topic[:80].strip().lower()}||{fact[:120].strip().lower()}"
        if content_key in self.content_hashes:
            return None
        # V3 Fix 1: Cross-domain evidence rejection
        if not self.topic_class:
            self.topic_class = _extract_topic_class(self.task)
        if not self.task_domain:
            self.task_domain = _detect_task_domain(self.topic_class, self.task)
        if self.task_domain != "unknown":
            ev_text = f"{topic} {fact}".lower()
            ev_domain = _detect_evidence_domain(ev_text)
            if ev_domain != "unknown" and ev_domain != self.task_domain:
                self.cross_domain_rejections += 1
                if log is not None:
                    log.log(
                        f"  [EVIDENCE-REJECTED-CROSSDOMAIN] topic=\"{topic[:60]}\" "
                        f"task_domain={self.task_domain} ev_domain={ev_domain}"
                    )
                return None

        # V6: Evidence cap with priority-based eviction
        # Priority ranking: cited-by-multiple > tied-to-controlling-claim >
        # tied-to-contradiction > tied-to-blocker > recent+high-quality > rest
        if len(self.items) >= MAX_EVIDENCE_ITEMS:
            if not self.topic_keywords:
                self.topic_keywords = _extract_topic_keywords(self.task)
            incoming_text = f"{topic} {fact}".lower()
            incoming_score = self._evidence_priority_score(
                topic, fact, confidence, first_available_round
            )

            # Find weakest existing item by priority score
            weakest_idx = None
            weakest_score = incoming_score
            for i, item in enumerate(self.items):
                item_score = self._evidence_priority_score(
                    item["topic"], item["fact"], item["confidence"],
                    item.get("first_available_round", 0)
                )
                if item_score < weakest_score:
                    weakest_score = item_score
                    weakest_idx = i

            if weakest_idx is not None:
                evicted = self.items[weakest_idx]
                if log is not None:
                    log.log(
                        f"  [EVIDENCE-EVICTED] {evicted['evidence_id']} "
                        f"(priority={weakest_score}) replaced by incoming "
                        f"\"{topic[:50]}\" (priority={incoming_score}) "
                        f"at cap={MAX_EVIDENCE_ITEMS}"
                    )
                for ck, eid in list(self.content_hashes.items()):
                    if eid == evicted["evidence_id"]:
                        del self.content_hashes[ck]
                        break
                if evicted.get("url"):
                    self.seen_urls.discard(evicted["url"])
                self.items.pop(weakest_idx)
            else:
                if log is not None:
                    log.log(
                        f"  [EVIDENCE-CAP-HIT] All {MAX_EVIDENCE_ITEMS} items have "
                        f"higher priority. Discarding \"{topic[:50]}\""
                    )
                self._cap_discards += 1
                return None

        eid = self.next_id()
        self.items.append({
            "evidence_id": eid,
            "topic": topic[:100],
            "fact": fact[:500],  # V6: increased from 300 to 500 for Brave extra excerpts
            "url": url,
            "confidence": confidence,
            "first_available_round": first_available_round,
            "cited_by_models": [],
        })
        self.content_hashes[content_key] = eid
        if url:
            self.seen_urls.add(url)

        # V6 Fix 1: Contradiction detection — check new item against existing items
        self._check_contradiction(eid, topic, fact, first_available_round, log)

        return eid

    def _evidence_priority_score(self, topic: str, fact: str, confidence: str,
                                  first_available_round: int) -> int:
        """V6 Fix 4: Compute priority score for evidence item.
        
        Priority ranking:
          +10: cited by multiple models
          +5:  cited by one model
          +3:  tied to active blocker/gap
          +3:  tied to contradiction
          +2:  HIGH confidence
          +1:  MEDIUM confidence
          +1:  recent (first_available_round >= 2)
          base: keyword overlap with task
        """
        score = 0
        item_text = f"{topic} {fact}".lower()

        # Check citation (look up in items list)
        for item in self.items:
            if item["topic"][:100] == topic[:100]:
                citations = item.get("cited_by_models", [])
                if len(citations) >= 2:
                    score += 10
                elif len(citations) >= 1:
                    score += 5
                break

        # Tied to active blocker
        for blk in self.blocker_ledger:
            if blk["status"] == "OPEN":
                blk_text = blk.get("detail", "").lower()
                if blk_text and any(kw in item_text for kw in blk_text.split()[:5] if len(kw) >= 4):
                    score += 3
                    break

        # Tied to contradiction
        for ctr in self.contradiction_ledger:
            if topic[:100] in [self._get_topic_by_eid(eid) for eid in ctr.get("evidence_ids", [])]:
                score += 3
                break

        # Confidence
        if confidence == "HIGH":
            score += 2
        elif confidence == "MEDIUM":
            score += 1

        # Recency
        if first_available_round >= 2:
            score += 1

        # Base: keyword overlap
        if self.topic_keywords:
            score += sum(1 for kw in self.topic_keywords if kw in item_text)

        return score

    def _get_topic_by_eid(self, eid: str) -> str:
        for item in self.items:
            if item["evidence_id"] == eid:
                return item["topic"][:100]
        return ""

    def _check_contradiction(self, new_eid: str, topic: str, fact: str,
                              detected_round: int, log=None):
        """V6 Fix 1: Check if newly admitted evidence contradicts existing items.

        Contradiction detected when:
          - Two items share significant subject overlap (topic keywords)
          - They contain different numeric values for the same kind of metric
        
        Produces a contradiction record. Does NOT reject — both items stay,
        but the contradiction is surfaced to models and proof.
        """
        new_text = f"{topic} {fact}".lower()
        new_numbers = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', new_text))
        if not new_numbers:
            return

        new_kw = {w for w in re.findall(r'[a-z]{4,}', new_text)}

        for item in self.items:
            if item["evidence_id"] == new_eid:
                continue
            existing_text = f"{item['topic']} {item['fact']}".lower()
            existing_kw = {w for w in re.findall(r'[a-z]{4,}', existing_text)}

            # Subject overlap: need at least 3 shared keywords
            shared_kw = new_kw & existing_kw
            if len(shared_kw) < 3:
                continue

            # Check for different numbers on same-subject items
            existing_numbers = set(re.findall(r'\b\d+(?:\.\d+)?%?\b', existing_text))
            # Numbers present in both but with different values = potential contradiction
            # (same number in both = agreement, not contradiction)
            if new_numbers and existing_numbers and new_numbers != existing_numbers:
                # At least one number differs — check if the difference is meaningful
                # (not just different metrics in the same text)
                shared_numbers = new_numbers & existing_numbers
                diff_new = new_numbers - existing_numbers
                diff_existing = existing_numbers - new_numbers
                if diff_new and diff_existing:
                    self.contradiction_counter += 1
                    ctr_id = f"CTR{self.contradiction_counter:03d}"
                    shared_topic = ", ".join(sorted(shared_kw)[:5])
                    record = {
                        "contradiction_id": ctr_id,
                        "evidence_ids": [item["evidence_id"], new_eid],
                        "topic": shared_topic,
                        "severity": "HIGH" if len(shared_kw) >= 5 else "MEDIUM",
                        "status": "UNRESOLVED",
                        "detected_round": detected_round,
                        "detail": (
                            f"{item['evidence_id']} says {', '.join(sorted(diff_existing)[:3])} "
                            f"vs {new_eid} says {', '.join(sorted(diff_new)[:3])} "
                            f"on topic: {shared_topic}"
                        )[:200],
                    }
                    self.contradiction_ledger.append(record)
                    if log is not None:
                        log.log(
                            f"  [EVIDENCE-CONTRADICTION] {ctr_id}: "
                            f"{item['evidence_id']} vs {new_eid} — "
                            f"topic={shared_topic} severity={record['severity']}"
                        )


# ── Search mode classification (v6 transplant) ───────────────────────────────

# Domain substance patterns — real domain content in hypothetically-framed tasks.
# If a task uses hypothetical framing but contains these, it's BORDERLINE (not training_only).
_DOMAIN_SUBSTANCE_PATTERN = re.compile(
    r'\b(?:'
    r'remote\s*code\s*execution|buffer\s*overflow|sql\s*injec|cross.site\s*scripting|'
    r'path\s*traversal|privilege\s*escalat|memory\s*corrupt|arbitrary\s*code|'
    r'denial.of.service|race\s*condition|heap\s*overflow|stack\s*overflow|'
    r'authentication\s*bypass|command\s*inject|deserialization|use.after.free|'
    r'vulnerability|exploit|malware|ransomware|phishing|'
    r'etf|fund|portfolio|expense\s*ratio|holdings|aum|dividend|yield|'
    r'server|database|application|network|endpoint|firewall|encryption|'
    r'certificate|authorization|authentication|inject|bypass|overflow|'
    r'cve|regulation|compliance|audit|risk\s*assessment'
    r')\b',
    re.IGNORECASE,
)

_ETF_KEYWORDS = frozenset({
    "etf", "fund", "ticker", "portfolio", "holdings", "aum", "expense ratio",
    "equity", "bond", "index", "vanguard", "ishares", "spdr", "nasdaq", "s&p",
    "dividend", "yield", "sector", "allocation", "rebalance",
})


def _has_domain_substance(task: str) -> bool:
    """Return True if task contains domain-specific content beyond pure hypothetical framing.

    Used to distinguish "pure hypothetical" (no domain substance → training_only) from
    "hypothetical framing + real domain content" (BORDERLINE → LLM tiebreaker).
    """
    task_lower = task.lower()
    if any(kw in task_lower for kw in _ETF_KEYWORDS):
        return True
    if _DOMAIN_SUBSTANCE_PATTERN.search(task):
        return True
    return False


def _classify_search_mode(task: str, log=None) -> tuple:
    """Regex-only classification. Returns (mode, confidence).

    mode: 'full' | 'minimal' | 'training_only'
    confidence: 'CLEAR' | 'BORDERLINE' | 'AMBIGUOUS'

    - 'full' / CLEAR     : CVE ID / ticker / regulation found
    - 'full' / BORDERLINE: only proper-noun identifiers found
    - 'minimal' / BORDERLINE: hypothetical framing + domain substance detected
    - 'training_only' / CLEAR: pure hypothetical, no domain substance
    - 'minimal' / AMBIGUOUS  : no identifiers, no hypothetical markers

    Note: "choose between" removed from hypothetical markers (v6 fix) — concrete
    operational briefs with action options were misrouting to training_only.
    """
    identifiers: list = []
    identifier_reasons: list = []
    hypothetical_markers: list = []

    # CVE ID detection — MUST have the numeric year and sequence (not bare "CVE")
    cve_matches = re.findall(r'\bCVE-\d{4}-\d{4,7}\b', task, re.IGNORECASE)
    for m in cve_matches:
        identifiers.append(m)
        identifier_reasons.append(f"CVE-ID:{m}")

    # Ticker symbol detection: 2-5 uppercase letters, not common words, not security class terms
    # V3 Fix 6: Require finance context before promoting any token to ticker
    # V6 Fix 8: Filter code-token false positives (Python keywords, variable names, config keys)
    _CODE_TOKEN_PATTERNS = re.compile(
        r'(?:def |class |import |from |return |self\.|__\w+__|'
        r'\.py\b|\.json\b|\.txt\b|\.md\b|"""|\'\'\''
        r'|#\s*--|#\s*──|^\s*#)', re.MULTILINE
    )
    _is_code_brief = bool(_CODE_TOKEN_PATTERNS.search(task[:2000]))
    _CODE_FALSE_POSITIVES = frozenset({
        "YAML", "JSON", "HTML", "NONE", "TRUE", "FALSE", "NULL", "SELF",
        "PATH", "FILE", "LIST", "DICT", "TYPE", "INIT", "MAIN", "ARGS",
        "OPEN", "READ", "TEXT", "TEMP", "COPY", "MODE", "DATA", "ITEM",
        "PASS", "FAIL", "HIGH", "LOW", "CLEAR", "FIRED", "BLOCKED",
    })

    _ticker_detected = False
    if not identifiers:
        task_lower_for_finance = task.lower()
        has_finance_context = any(sig in task_lower_for_finance for sig in _FINANCE_CONTEXT_SIGNALS)
        ticker_candidates = re.findall(r'\b([A-Z]{2,5})\b', task)
        for t in ticker_candidates[:15]:
            if (
                t.lower() not in _HYPO_CLASSIFIER_COMMON_WORDS
                and t.upper() not in _SECURITY_CLASS_TERMS
                and t.upper() not in _CODE_FALSE_POSITIVES
                and len(t) >= 2
            ):
                # V6 Fix 8: Skip if brief looks like code
                if _is_code_brief and not has_finance_context:
                    if log is not None:
                        log.log(f"  [SEARCH-ROUTER-SIGNAL] type=ticker_skipped token={t} reason=code_brief_detected")
                    continue
                if has_finance_context:
                    identifiers.append(t)
                    identifier_reasons.append(f"ticker:{t}")
                    _ticker_detected = True
                    break
                else:
                    if log is not None:
                        log.log(f"  [SEARCH-ROUTER-SIGNAL] type=ticker_skipped token={t} reason=no_finance_context")

    # Proper noun: two or more consecutive Title-Cased words
    # V6 Fix 8: Cap proper nouns from code briefs to prevent config headings being treated as entities
    proper_noun_matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', task)
    _max_proper_nouns = 3 if _is_code_brief else 10
    for pn in proper_noun_matches[:_max_proper_nouns]:
        # V6 Fix 8: Skip obvious code/config headings
        if any(code_kw in pn.lower() for code_kw in ("class ", "def ", "import ", "type ")):
            continue
        identifiers.append(pn)
        identifier_reasons.append(f"proper-noun:{pn}")

    # Regulation/standard numbers
    reg_matches = re.findall(r'\b(?:NIST|ISO|PCI|SOC|GDPR|HIPAA|FedRAMP)\s+[\w\-\.]+', task, re.IGNORECASE)
    for rm in reg_matches:
        identifiers.append(rm)
        identifier_reasons.append(f"regulation:{rm}")

    # Hypothetical marker detection — "choose between" intentionally excluded (v6 fix)
    _HYPO_PATTERNS = [
        r'\bhypothetical\b', r'\bscenario\b',
        r'\bwhat\s+if\b', r'\bimagine\b', r'\bsuppose\b',
    ]
    for pat in _HYPO_PATTERNS:
        matches = re.findall(pat, task, re.IGNORECASE)
        hypothetical_markers.extend(matches)

    # Opinion-only pattern detection (V2 addition)
    for pat in _OPINION_PATTERNS:
        matches = re.findall(pat, task, re.IGNORECASE)
        hypothetical_markers.extend(matches)

    identifiers = list(dict.fromkeys(identifiers))
    identifier_reasons = list(dict.fromkeys(identifier_reasons))
    hypothetical_markers = list(dict.fromkeys(m.lower() for m in hypothetical_markers))

    if identifiers:
        mode = "full"
        reason = f"concrete identifiers found: {identifier_reasons}"
        has_strong_id = any(
            r.startswith("CVE-ID:") or r.startswith("regulation:")
            for r in identifier_reasons
        )
        if not has_strong_id and _ticker_detected:
            has_strong_id = True  # V3 Fix 6: finance context was already verified
        routing_confidence = "CLEAR" if has_strong_id else "BORDERLINE"
    elif hypothetical_markers:
        if _has_domain_substance(task):
            mode = "minimal"  # regex best-guess; LLM may override
            reason = (
                f"hypothetical markers present but domain substance detected: "
                f"markers={hypothetical_markers}"
            )
            routing_confidence = "BORDERLINE"
        else:
            mode = "training_only"
            reason = f"hypothetical markers present, no domain substance: markers={hypothetical_markers}"
            routing_confidence = "CLEAR"
    else:
        mode = "minimal"
        reason = "no concrete identifiers and no hypothetical markers"
        routing_confidence = "AMBIGUOUS"

    hard_ceiling = mode == "training_only"

    if log is not None:
        for sig in identifier_reasons:
            log.log(f"  [SEARCH-ROUTER-SIGNAL] type=identifier signal={sig}")
        for hm in hypothetical_markers:
            log.log(f"  [SEARCH-ROUTER-SIGNAL] type=hypothetical_marker signal={hm}")
        if not identifier_reasons and not hypothetical_markers:
            log.log("  [SEARCH-ROUTER-SIGNAL] type=none — no classifiable signals found (default fallback)")
        log.log(
            f"  [SEARCH-ROUTER] selected_mode={mode} routing_confidence={routing_confidence} "
            f"hard_live_retrieval_ceiling={hard_ceiling} "
            f"decision_basis={reason!r}"
        )
        log.log(f"  [SEARCH-MODE] Classified as: {mode} — reason: {reason}")

    return mode, routing_confidence


def _llm_search_tiebreaker(task: str, log=None) -> tuple:
    """Sync LLM call to resolve BORDERLINE/AMBIGUOUS search mode.

    Returns (mode, rationale). Mode is one of: "full", "minimal", "training_only".
    Falls back to "minimal" on any error — never raises.
    """
    system_prompt = (
        "You are a search routing classifier. Your job is to decide whether a task query "
        "requires live web search.\n\n"
        "Definitions:\n"
        "- full: task references specific real-world identifiable entities (named CVEs, "
        "company names, specific products, regulation numbers, financial instruments like "
        "ETF tickers) where live web search would return authoritative, current information.\n"
        "- minimal: task has concrete domain content but no specific searchable identifiers; "
        "web context might help but training knowledge is the primary source.\n"
        "- training_only: purely hypothetical or abstract scenario with no real-world referents; "
        "web search would return nothing relevant; training knowledge is fully sufficient.\n\n"
        "Respond ONLY with a JSON object — no markdown, no explanation outside JSON:\n"
        '{"mode": "full|minimal|training_only", "rationale": "<one concise sentence>"}'
    )
    user_prompt = f"Task: {task}\n\nClassify the search mode."
    payload = json.dumps({
        "model":       "anthropic/claude-sonnet-4-6",  # Match Chamber judge model (Sonnet, not Haiku — more conservative, consistent routing)
        "messages":    [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens":  256,
    }).encode("utf-8")
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer":  "https://openclaw.ai",
        "X-Title":       "Brain-V2-SearchRouter",
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload, headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON in LLM response: {text[:200]!r}")
        parsed = json.loads(json_match.group())
        mode = parsed.get("mode", "minimal")
        rationale = parsed.get("rationale", "")
        if mode not in ("full", "minimal", "training_only"):
            mode = "minimal"
        if log is not None:
            log.log(f"  [SEARCH-ROUTER] tiebreaker_decision mode={mode} rationale={rationale!r}")
        return mode, rationale
    except Exception as exc:
        if log is not None:
            log.log(f"  [SEARCH-ROUTER] tiebreaker_error={exc!r} fallback=minimal")
        return "minimal", f"tiebreaker error fallback: {exc}"


def _resolve_search_mode(task: str, log=None) -> tuple:
    """Hybrid two-layer search mode resolution (sync).

    Layer 1: Regex hard gate. CLEAR confidence → return immediately (no LLM cost).
    Layer 2: Sync LLM tiebreaker for BORDERLINE or AMBIGUOUS confidence.

    Returns (mode, routing_confidence, mode_origin).
    mode_origin: "hard_rule" if decided by regex CLEAR gate, "llm_tiebreaker" if LLM override.
    """
    mode, confidence = _classify_search_mode(task, log)

    if confidence == "CLEAR":
        return mode, confidence, "hard_rule"

    # BORDERLINE or AMBIGUOUS → invoke LLM tiebreaker
    if log is not None:
        log.log(
            f"  [SEARCH-ROUTER] regex_result mode={mode} confidence={confidence} "
            f"→ invoking LLM tiebreaker"
        )

    llm_mode, llm_rationale = _llm_search_tiebreaker(task, log)

    if llm_mode != mode and log is not None:
        log.log(
            f"  [SEARCH-ROUTER] tiebreaker_override regex_mode={mode} "
            f"llm_mode={llm_mode} rationale={llm_rationale!r}"
        )

    return llm_mode, confidence, "llm_tiebreaker"


def classify_search_mode(brief: str, log=None) -> str:
    """Classify brief into search_mode: 'full', 'minimal', or 'training_only'.

    - 'full'          : concrete real-world identifiers (CVE IDs, tickers, proper nouns, reg numbers)
    - 'minimal'       : no concrete identifiers, no hypothetical markers
    - 'training_only' : hypothetical scenario with no concrete identifiers and no domain substance

    Backward-compatible public wrapper. Returns mode string.
    Internally uses two-layer hybrid: regex gate + LLM tiebreaker for BORDERLINE/AMBIGUOUS.
    """
    mode, _confidence, _origin = _resolve_search_mode(brief, log)
    return mode


# ── Search-gate mid-run escalation and observability ─────────────────────────

def _maybe_escalate_search_mode(
    ledger: "EvidenceLedger",
    log: "Logger | None",
    cycle: int,
    open_objections: list = None,
) -> None:
    """Mid-run escalation: training_only → minimal (one-time, one-way).

    Two parallel trigger paths (either can fire):

    Path A (conservative, original): ALL must be true:
      - training_only mode, not already escalated
      - cycle >= 1
      - search_diag_training_only_skips >= 2
      - >= 2 open objections with evidence gaps

    Path B (tiebreaker-override exception): ALL must be true:
      - training_only mode, not already escalated
      - routing confidence was AMBIGUOUS (not CLEAR/BORDERLINE)
      - mode origin was llm_tiebreaker (not hard_rule)
      - at least 1 retrieval skip under training_only
      - current phase has live evidence need: either open_objections with
        evidence gaps in THIS call, or live_evidence_candidate_events >= 1
        with at least 1 gap signal in THIS call

    Path B exists because: when the regex classifier was uncertain (AMBIGUOUS)
    and the LLM tiebreaker locked training_only, the lock was a judgment call,
    not a hard structural rule. If the run later surfaces concrete evidence
    needs, the lock should yield. Path A is the conservative backstop for
    other scenarios.

    Fires at most once per run. Always logs [SEARCH-ESCALATION] with result.
    """
    # ── Pre-checks common to both paths ──
    if ledger.search_mode != "training_only":
        _emit_escalation_decision(ledger, log, cycle, "NOT_ELIGIBLE",
                                  "current mode is not training_only", open_objections)
        return
    if ledger.search_mode_escalated:
        _emit_escalation_decision(ledger, log, cycle, "NOT_ELIGIBLE",
                                  "already escalated this run", open_objections)
        return

    # ── Gather evidence-gap signals from current phase ──
    current_gap_count = 0
    current_gap_ids = []
    if open_objections:
        evidence_gap_objs = [
            o for o in open_objections
            if getattr(o, "requested_evidence", None) or getattr(o, "type", "") == "evidence_gap"
        ]
        current_gap_count = len(evidence_gap_objs)
        current_gap_ids = [getattr(o, "objection_id", str(i)) for i, o in enumerate(evidence_gap_objs[:5])]

    # ── Path A: conservative (original logic) ──
    path_a_eligible = (
        cycle >= 1
        and ledger.search_diag_training_only_skips >= 2
        and current_gap_count >= 2
    )

    # ── Path B: tiebreaker-override exception ──
    path_b_eligible = (
        ledger.search_diag_router_confidence == "AMBIGUOUS"
        and ledger.search_mode_origin == "llm_tiebreaker"
        and ledger.search_diag_training_only_skips >= 1
        and (current_gap_count >= 1 or (
            ledger.search_diag_live_evidence_candidates >= 1
            and current_gap_count >= 1
        ))
    )

    if path_a_eligible or path_b_eligible:
        # ── FIRE escalation ──
        ledger.search_mode = "minimal"
        ledger.search_mode_escalated = True
        trigger_path = "path_A" if path_a_eligible else "path_B"
        if log is not None:
            log.log(
                f"  [SEARCH-ESCALATION] result=FIRED training_only→minimal "
                f"trigger={trigger_path} cycle={cycle + 1} "
                f"routing_confidence={ledger.search_diag_router_confidence} "
                f"mode_origin={ledger.search_mode_origin} "
                f"retrieval_skips={ledger.search_diag_training_only_skips} "
                f"current_gap_count={current_gap_count} "
                f"current_gap_ids={current_gap_ids} "
                f"live_evidence_candidates={ledger.search_diag_live_evidence_candidates} "
                f"note=one-time-escalation-never-to-full"
            )
        ledger.decisions.append({
            "decision_type": "search_escalation",
            "trigger": trigger_path,
            "inputs": {"cycle": cycle + 1, "gap_count": current_gap_count,
                       "skips": ledger.search_diag_training_only_skips},
            "reason": f"FIRED training_only→minimal via {trigger_path}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # ── NOT triggered — log why ──
        reasons = []
        if cycle < 1:
            reasons.append("cycle<1")
        if ledger.search_diag_training_only_skips < 1:
            reasons.append(f"skips={ledger.search_diag_training_only_skips}<1")
        if current_gap_count < 1:
            reasons.append(f"current_gaps={current_gap_count}<1")
        # Path A specific
        if ledger.search_diag_training_only_skips < 2:
            reasons.append(f"path_A: skips={ledger.search_diag_training_only_skips}<2")
        if current_gap_count < 2:
            reasons.append(f"path_A: gaps={current_gap_count}<2")
        # Path B specific
        if ledger.search_diag_router_confidence != "AMBIGUOUS":
            reasons.append(f"path_B: confidence={ledger.search_diag_router_confidence}≠AMBIGUOUS")
        if ledger.search_mode_origin != "llm_tiebreaker":
            reasons.append(f"path_B: origin={ledger.search_mode_origin}≠llm_tiebreaker")
        _emit_escalation_decision(ledger, log, cycle, "BLOCKED",
                                  "; ".join(reasons), open_objections)
        ledger.decisions.append({
            "decision_type": "search_escalation",
            "trigger": "blocked",
            "inputs": {"cycle": cycle + 1, "gap_count": current_gap_count,
                       "skips": ledger.search_diag_training_only_skips},
            "reason": f"BLOCKED: {'; '.join(reasons)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


def _emit_escalation_decision(
    ledger: "EvidenceLedger",
    log: "Logger | None",
    cycle: int,
    result: str,
    reason: str,
    open_objections: list = None,
) -> None:
    """Always emit [SEARCH-ESCALATION] with result=FIRED|BLOCKED|NOT_ELIGIBLE.

    Provides full audit trail for every escalation evaluation point.
    """
    if log is None:
        return

    current_gap_count = 0
    if open_objections:
        current_gap_count = sum(
            1 for o in open_objections
            if getattr(o, "requested_evidence", None) or getattr(o, "type", "") == "evidence_gap"
        )

    log.log(
        f"  [SEARCH-ESCALATION] result={result} cycle={cycle + 1} "
        f"routing_confidence={ledger.search_diag_router_confidence} "
        f"mode_origin={ledger.search_mode_origin} "
        f"retrieval_skips={ledger.search_diag_training_only_skips} "
        f"current_gap_count={current_gap_count} "
        f"live_evidence_candidates={ledger.search_diag_live_evidence_candidates} "
        f"reason={reason!r}"
    )


def _maybe_emit_live_evidence_candidate(
    ledger: "EvidenceLedger",
    log: "Logger | None",
    cycle: int,
    open_objections: list = None,
    audit=None,
) -> None:
    """Emit [LIVE-EVIDENCE-CANDIDATE] when training_only run shows evidence gaps.

    Observability only — does not change any behavior.
    """
    if ledger.search_mode != "training_only":
        return

    missing_from_audit: list = getattr(audit, "missing_evidence", [])[:5] if audit else []
    evidence_gap_objs: list = [
        getattr(o, "objection_id", str(i))
        for i, o in enumerate(open_objections or [])
        if getattr(o, "requested_evidence", None)
    ]

    if not missing_from_audit and not evidence_gap_objs:
        return

    ledger.search_diag_live_evidence_candidates += 1
    if log is not None:
        log.log(
            f"  [LIVE-EVIDENCE-CANDIDATE] cycle={cycle + 1} current_mode=training_only "
            f"live_evidence_benefit_candidate=true "
            f"missing_evidence_from_auditor={missing_from_audit} "
            f"objections_with_evidence_gaps={evidence_gap_objs} "
            f"retrieval_skipped_count_so_far={ledger.search_diag_training_only_skips}"
        )


def _emit_search_diagnostics(ledger: "EvidenceLedger", log: "Logger") -> None:
    """Emit [SEARCH-DIAGNOSTICS] end-of-run summary for search-gate observability."""
    upfront_mode = ledger.search_diag_upfront_mode or ledger.search_mode
    final_mode = ledger.search_mode
    confidence = ledger.search_diag_router_confidence or "UNKNOWN"
    training_only_skips = ledger.search_diag_training_only_skips
    live_candidates = ledger.search_diag_live_evidence_candidates
    live_attempted = ledger.search_diag_live_retrieval_attempted

    escalation_candidate = (
        upfront_mode == "training_only"
        and training_only_skips > 0
        and live_candidates > 0
    )

    log.log(
        f"  [SEARCH-DIAGNOSTICS] run_id={ledger.run_id} "
        f"upfront_selected_mode={upfront_mode} "
        f"final_mode={final_mode} "
        f"routing_confidence={confidence} "
        f"mode_origin={ledger.search_mode_origin or 'unknown'} "
        f"hard_live_retrieval_ceiling={upfront_mode == 'training_only'} "
        f"escalated={ledger.search_mode_escalated} "
        f"live_retrieval_ever_attempted={live_attempted} "
        f"training_only_retrieval_skips={training_only_skips} "
        f"live_evidence_candidate_events={live_candidates} "
        f"escalation_candidate={escalation_candidate} "
        f"note={'Run is a credible candidate for future mid-run mode escalation review' if escalation_candidate else 'No escalation signal'}"
    )


# ── Evidence-gap signal extraction from free-text model outputs ──────────────
# Brain V2 models produce free-text, not structured objections. This helper
# scans model outputs for explicit evidence-gap language and produces
# lightweight signal objects compatible with _maybe_escalate_search_mode().
#
# Two-stage detection (V2.4):
#   Stage 1: Fast regex scan (zero cost, deterministic)
#   Stage 2: Guarded Haiku fallback (semantic, ~3s, only when regex finds 0
#            gaps AND the run is in the specific failure scenario where better
#            detection can trigger escalation)

_EVIDENCE_GAP_PATTERNS = [
    re.compile(r'[Nn]o (?:data|evidence|concrete data|specific data|empirical data) (?:on|for|about|regarding) (.{10,80}?)(?:[,\.]|$)'),
    re.compile(r'[Nn]o (?:concrete|specific|empirical) (?:evidence|data) (?:provides?|supports?|confirms?) (.{10,80}?)(?:[,\.]|$)'),
    re.compile(r'(?:uncited|unverified|not verified|not cited|lacks? citation) (.{10,60}?)(?:[,\.]|$)', re.IGNORECASE),
    re.compile(r'[Cc]ritical gap:?\s*(.{10,80}?)(?:[,\.]|$)'),
    re.compile(r'[Ee]vidence gap:?\s*(.{10,80}?)(?:[,\.]|$)'),
    re.compile(r'(?:no|without|lacking) (?:reliable|authoritative|verified) (?:source|data|evidence) (?:on|for|about) (.{10,80}?)(?:[,\.]|$)', re.IGNORECASE),
]

_HAIKU_GAP_FALLBACK_PROMPT = """\
You are reviewing outputs from AI analysts debating a decision.

Your ONLY job: identify specific empirical claims that are:
1. Stated as fact (with numbers, percentages, time estimates, or named sources)
2. Material to the recommendation or disagreement
3. Not supported by any cited evidence in the text
4. Externally verifiable (could be checked via web search)

Do NOT flag:
- Value judgments or opinions
- Hypothetical reasoning or conditional logic
- Generic statements like "more data would help"
- Claims that are clearly labeled as estimates or assumptions

Output ONLY valid JSON (no markdown, no explanation):
{{"claims": ["<claim 1>", "<claim 2>", "<claim 3>"]}}

Maximum 3 claims. If none qualify, output: {{"claims": []}}

ANALYST OUTPUTS:
{combined_outputs}
"""


class EvidenceGapSignal:
    """Lightweight stand-in for Chamber's Objection, for escalation compatibility."""
    def __init__(self, objection_id: str, gap_text: str, requested_evidence: list):
        self.objection_id = objection_id
        self.requested_evidence = requested_evidence
        self.type = "evidence_gap"
        self.gap_text = gap_text


def _haiku_gap_fallback(
    model_outputs: dict,
    ledger: "EvidenceLedger",
    log: "Logger | None",
    round_num: int,
) -> list:
    """Stage 2: Guarded Haiku fallback for evidence-gap detection.

    Only called when:
      - Stage 1 regex found 0 gaps
      - ledger.search_mode == "training_only"
      - ledger.search_mode_origin == "llm_tiebreaker"
      - ledger.search_diag_router_confidence == "AMBIGUOUS"
      - ledger.search_diag_training_only_skips >= 1

    Returns list of EvidenceGapSignal objects (max 3). On any failure,
    returns empty list — never fails the run.
    """
    combined = ""
    for model_name, text in model_outputs.items():
        truncated = text[:3000] if text and len(text) > 3000 else (text or "")
        combined += f"\n### {model_name}:\n{truncated}\n"

    if not combined.strip():
        return []

    if log is not None:
        log.log(f"  [HAIKU-GAP-FALLBACK] round={round_num} — regex found 0 gaps, invoking Haiku semantic detector")

    prompt = _HAIKU_GAP_FALLBACK_PROMPT.format(combined_outputs=combined)

    try:
        raw = call_haiku(prompt, max_tokens=500)
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if not json_match:
            if log is not None:
                log.log(f"  [HAIKU-GAP-FALLBACK] round={round_num} — no JSON in Haiku response")
            return []

        parsed = json.loads(json_match.group())
        claims = parsed.get("claims", [])
        if not isinstance(claims, list):
            return []

        # Cap at 3, filter empty strings
        claims = [c.strip() for c in claims[:3] if isinstance(c, str) and c.strip()]

        signals = []
        for i, claim in enumerate(claims):
            sig = EvidenceGapSignal(
                objection_id=f"GAP-R{round_num}-HK{i+1:02d}",
                gap_text=claim,
                requested_evidence=[claim[:120]],
            )
            signals.append(sig)
            ledger.gaps_detected.append({
                "gap_id": sig.objection_id, "round": round_num,
                "source": "haiku_fallback", "text": claim[:120],
            })
            if log is not None:
                log.log(
                    f"  [EVIDENCE-GAP-DETECTED] source=haiku_fallback round={round_num} "
                    f"gap=\"{claim[:80]}\""
                )

        if log is not None:
            log.log(f"  [HAIKU-GAP-FALLBACK] round={round_num} — returned {len(signals)} gap(s)")
        return signals

    except Exception as exc:
        if log is not None:
            log.log(f"  [HAIKU-GAP-FALLBACK] round={round_num} — error (non-fatal): {exc}")
        return []


def _extract_evidence_gap_signals(
    model_outputs: dict,
    ledger: "EvidenceLedger",
    log: "Logger | None",
    round_num: int = 0,
) -> list:
    """Scan free-text model outputs for evidence gaps. Two-stage detection.

    Stage 1: Fast regex scan (always runs).
    Stage 2: Guarded Haiku fallback (only when regex finds 0 AND the run is
             in the specific failure scenario where semantic detection matters).

    Returns list of EvidenceGapSignal objects compatible with
    _maybe_escalate_search_mode() and _maybe_emit_live_evidence_candidate().
    """
    # ── Stage 1: regex scan ──
    signals = []
    seen_gaps = set()
    counter = 0

    for model_name, text in model_outputs.items():
        if not text:
            continue
        for pattern in _EVIDENCE_GAP_PATTERNS:
            for match in pattern.finditer(text):
                gap_phrase = match.group(1).strip().rstrip('.,;:')
                # V6 Fix 8: Validate gap phrase before promoting
                # Drop malformed fragments (too short, looks like code, just punctuation)
                if len(gap_phrase) < 10:
                    continue
                if len(gap_phrase.split()) < 3:
                    continue
                # Drop gap phrases that look like code fragments
                if any(c in gap_phrase for c in ('()', '{}', '[]', '=', '_', '//')):
                    continue
                # Dedup by first 40 chars lowered
                dedup_key = gap_phrase[:40].lower()
                if dedup_key in seen_gaps:
                    continue
                seen_gaps.add(dedup_key)
                counter += 1
                sig = EvidenceGapSignal(
                    objection_id=f"GAP-R{round_num}-{counter:02d}",
                    gap_text=gap_phrase,
                    requested_evidence=[gap_phrase[:120]],
                )
                signals.append(sig)
                ledger.gaps_detected.append({
                    "gap_id": sig.objection_id, "round": round_num,
                    "source": "regex", "text": gap_phrase[:120],
                })
                if log is not None:
                    log.log(
                        f"  [EVIDENCE-GAP-DETECTED] source=regex round={round_num} model={model_name} "
                        f"gap=\"{gap_phrase[:80]}\""
                    )

    if log is not None:
        log.log(f"  [EVIDENCE-GAP-SUMMARY] round={round_num} regex_gaps={len(signals)}")

    # ── Stage 2: guarded Haiku fallback ──
    if len(signals) == 0:
        haiku_eligible = (
            ledger.search_mode == "training_only"
            and ledger.search_mode_origin == "llm_tiebreaker"
            and ledger.search_diag_router_confidence == "AMBIGUOUS"
            and ledger.search_diag_training_only_skips >= 1
        )
        if haiku_eligible:
            haiku_signals = _haiku_gap_fallback(model_outputs, ledger, log, round_num)
            signals.extend(haiku_signals)
        elif log is not None:
            reasons = []
            if ledger.search_mode != "training_only":
                reasons.append(f"mode={ledger.search_mode}")
            if ledger.search_mode_origin != "llm_tiebreaker":
                reasons.append(f"origin={ledger.search_mode_origin}")
            if ledger.search_diag_router_confidence != "AMBIGUOUS":
                reasons.append(f"confidence={ledger.search_diag_router_confidence}")
            if ledger.search_diag_training_only_skips < 1:
                reasons.append(f"skips={ledger.search_diag_training_only_skips}")
            log.log(
                f"  [HAIKU-GAP-FALLBACK] round={round_num} — not eligible: {'; '.join(reasons)}"
            )

    if log is not None:
        log.log(f"  [EVIDENCE-GAP-SUMMARY] round={round_num} total_gaps={len(signals)}")

    return signals


# ── Evidence quality helpers ──────────────────────────────────────────────────

def _relevance_keywords(text: str) -> set:
    words = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return {w for w in words if len(w) >= 4 and w not in _RELEVANCE_STOPWORDS}


def _extract_topic_class(task: str) -> str:
    sec_match = re.search(
        r'\b(remote\s+code\s+execution|buffer\s+overflow|sql\s+injection|'
        r'cross.site\s+scripting|path\s+traversal|privilege\s+escalation|'
        r'use.after.free|heap\s+overflow|stack\s+overflow|authentication\s+bypass|'
        r'command\s+injection|memory\s+corruption|arbitrary\s+code\s+execution|'
        r'denial.of.service|directory\s+traversal|integer\s+overflow|'
        r'race\s+condition|type\s+confusion|null\s+pointer|deserialization)\b',
        task, re.IGNORECASE,
    )
    if sec_match:
        vuln_type = sec_match.group(1).lower()
        comp_match = re.search(
            r'\bin\s+([\w][\w\s\-]{2,40}?)(?=\s+(?:that|which|where|when|allows|could|can|may|is|are)\b|[,\.\)]|$)',
            task[sec_match.end():sec_match.end() + 120], re.IGNORECASE,
        )
        if comp_match:
            return f"{vuln_type} in {comp_match.group(1).strip().lower()}"
        return vuln_type
    fin_match = re.search(
        r'\b(ETF|mutual\s+fund|bond|equity|stock|option|futures?|commodit(?:y|ies)|'
        r'portfolio|fixed.income|credit\s+default\s+swap|emerging\s+market)\b',
        task, re.IGNORECASE,
    )
    if fin_match:
        return fin_match.group(1).lower()
    return "the topic under analysis"


def _extract_topic_keywords(task: str) -> set:
    words = re.sub(r"[^a-z0-9\s]", " ", task.lower()).split()
    keywords: set = set()
    for w in words:
        if w in _RELEVANCE_STOPWORDS:
            continue
        if len(w) >= 5 or w in _DOMAIN_SHORTTERMS:
            keywords.add(w)
    return keywords


def _sanitize_query(query: str, ledger: EvidenceLedger, log=None) -> str | None:
    """6-guard query sanitizer (transplanted from Chamber V3)."""
    # Guard 1: self-reference substitution
    if _SELF_REF_PATTERNS.search(query):
        if not ledger.topic_class:
            ledger.topic_class = _extract_topic_class(ledger.task)
        substituted = _SELF_REF_PATTERNS.sub(ledger.topic_class, query).strip()
        substituted = re.sub(r'\s{2,}', ' ', substituted)
        substituted = re.sub(r'^[\s,\-–—:]+|[\s,\-–—:]+$', '', substituted)
        if log and substituted != query:
            log.log(f"  [QUERY-REWRITE-SELFREF] {query[:80]} → {substituted[:80]}")
        query = substituted

    # Guard 2: org-internal block
    if _ORG_INTERNAL_PATTERN.search(query):
        if log:
            log.log(f"  [QUERY-SKIP-PRIVATE] {query[:80]}")
        return None

    # Guard 3: conversational prefix strip
    conv_match = _CONV_PREFIX_PATTERN.match(query)
    if conv_match:
        cleaned = query[conv_match.end():].strip()
        if log:
            log.log(f"  [QUERY-REWRITE-CONV] {query[:80]} → {cleaned[:80]}")
        query = cleaned

    # Guard 4: short-query block
    if len(query.split()) < 4:
        if log:
            log.log(f"  [QUERY-SKIP-SHORT] {repr(query)}")
        return None

    # Guard 5: internal-number detector
    dollar_matches = _DOLLAR_AMOUNT_PATTERN.findall(query)
    if dollar_matches:
        existing_facts = " ".join(item["fact"] for item in ledger.items)
        for dv in dollar_matches:
            if dv in existing_facts:
                if log:
                    log.log(f"  [QUERY-SKIP-INTERNAL] {query[:80]}")
                return None

    # Guard 6: truncation at 120 chars at word boundary
    if len(query) > 120:
        truncated = query[:120]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        if log:
            log.log(f"  [QUERY-TRUNCATED] {query[:80]}…")
        query = truncated

    return query if query.strip() else None


def _is_relevant_result(result: dict, query: str, signal_text: str = "") -> bool:
    query_kw = _relevance_keywords(query) | _relevance_keywords(signal_text)
    result_text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    result_kw = _relevance_keywords(result_text)
    return len(query_kw & result_kw) >= 1


def _is_evidence_relevant(topic: str, fact: str, ledger: EvidenceLedger) -> bool:
    if not ledger.topic_keywords:
        ledger.topic_keywords = _extract_topic_keywords(ledger.task)
    if not ledger.topic_keywords:
        return True
    search_text = f"{topic} {fact}".lower()
    score = sum(1 for kw in ledger.topic_keywords if kw in search_text)
    if score >= 1:
        return True
    combined = search_text
    if any(sig in combined for sig in _OFF_DOMAIN_SIGNALS):
        return False
    return True  # ambiguous but no clear off-domain signal → admit


# ── Evidence block builder ────────────────────────────────────────────────────

def build_evidence_block(ledger: EvidenceLedger) -> str:
    # V5: Check for ungrounded warnings even if no evidence items
    all_flagged = []
    for rnd in sorted(ledger.ungrounded_stats_by_round.keys()):
        for fig in ledger.ungrounded_stats_by_round[rnd]:
            all_flagged.append(fig)

    if not ledger.items and not all_flagged:
        return ""

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = []

    if ledger.items:
        lines.extend([
            f"[RESEARCH CONTEXT — Web-verified evidence, {today}]",
            "",
            "The following evidence was retrieved to ground this round's analysis.",
            "Reference evidence IDs where relevant. If evidence contradicts a prior view, address the discrepancy.",
            "",
        ])
        for item in ledger.items[:MAX_EVIDENCE_ITEMS]:
            lines.append(f"{{{item['evidence_id']}}} [{item['confidence']}] {item['topic']}")
            lines.append(f"Fact: {item['fact']}")
            if item.get("url"):
                lines.append(f"Source: {item['url']}")
            lines.append("")

    # V6 Fix 1: Inject contradiction warnings
    unresolved_ctrs = [c for c in ledger.contradiction_ledger if c["status"] == "UNRESOLVED"]
    if unresolved_ctrs:
        lines.append("")
        lines.append("[EVIDENCE CONTRADICTIONS — unresolved conflicts in admitted evidence]")
        lines.append("The following evidence items present conflicting claims. You MUST address")
        lines.append("each contradiction: resolve it, declare which is more credible, or flag uncertainty.")
        for ctr in unresolved_ctrs[:5]:
            lines.append(f"  - {ctr['contradiction_id']}: {ctr['detail']}")
        lines.append("[END EVIDENCE CONTRADICTIONS]")
        lines.append("")

    # V6 Fix 3: Inject minority view carry-forward
    active_minorities = [m for m in ledger.minority_archive if not m.get("addressed_by")]
    if active_minorities:
        lines.append("")
        lines.append("[MINORITY VIEWS — preserved from dropped models]")
        lines.append("The following minority arguments were made by models no longer in the active roster.")
        lines.append("You MUST explicitly address each one: agree, refute with evidence, or acknowledge as unresolved.")
        for mv in active_minorities:
            lines.append(
                f"  - [{mv['model']} R{mv['round_dropped']}] Position: {mv['position']} — "
                f"{mv['argument_summary'][:200]}"
            )
            if mv.get("evidence_cited"):
                lines.append(f"    Evidence cited: {', '.join(mv['evidence_cited'][:5])}")
        lines.append("[END MINORITY VIEWS]")
        lines.append("")

    # V5: Inject ungrounded figure warnings from previous rounds
    # This makes the detector interventional — models see what was flagged
    # and can self-correct in the next round
    if all_flagged:
        lines.append("")
        lines.append("[UNGROUNDED FIGURE WARNINGS — from prior round analysis]")
        lines.append("The following figures appeared in prior rounds WITHOUT evidence citation.")
        lines.append("If you use any of these figures, you MUST either cite evidence or label them as estimates.")
        for fig in all_flagged[:8]:
            lines.append(f"  - figure=\"{fig['figure']}\" (model={fig['model']}, R{fig['round']})")
        lines.append("[END UNGROUNDED WARNINGS]")
        lines.append("")

    # Evidence discipline section — adapted to whether evidence exists
    if ledger.items:
        lines.append("[EVIDENCE DISCIPLINE]")
        lines.append("Any specific number, percentage, probability, or dollar figure in your analysis")
        lines.append("MUST cite an evidence ID (E001-E999) from the Research Context above.")
        lines.append("If no evidence supports a figure, explicitly label it as an estimate or assumption.")
        lines.append("Do not present ungrounded figures as established facts.")
        lines.append("[END RESEARCH CONTEXT]")
    else:
        # No evidence items, but ungrounded warnings were emitted above
        lines.append("[EVIDENCE DISCIPLINE]")
        lines.append("No web-verified evidence is available for this round.")
        lines.append("Any specific number, percentage, probability, or dollar figure in your analysis")
        lines.append("MUST be explicitly labeled as an estimate or assumption.")
        lines.append("Do not present ungrounded figures as established facts.")
        lines.append("[END EVIDENCE DISCIPLINE]")

    return "\n".join(lines)


# ── Prompt Templates ──────────────────────────────────────────────────────────

GAP_EXTRACTION_PROMPT = """\
You are a research coordinator for an AI deliberation system.

Below are the outputs of {n} AI analysts who independently assessed the same topic.
Your job is to extract search queries that will provide verified factual grounding
for the next round of deliberation.

EXTRACT ONLY:
1. Specific verifiable claims (names, numbers, tickers, dates, percentages, named entities)
2. Points where analysts clearly disagree on verifiable facts (not opinions)
3. Explicit uncertainty markers where an analyst admits a fact needs verification

DO NOT EXTRACT:
- Opinions, predictions, or recommendations
- General knowledge that doesn't need lookup ("gravity exists")
- Reasoning, logic, or analytical frameworks
- Claims the models agree on

Output ONLY valid JSON (no markdown fences):
{{
  "queries": [
    {{"signal": "verifiable_claim", "claim": "XYZ has expense ratio 0.59%", "query": "XYZ ETF expense ratio 2026"}},
    {{"signal": "disagreement", "claim": "Model A says AUM is $5B, Model B says $2B", "query": "XYZ fund AUM 2025"}},
    {{"signal": "uncertainty", "claim": "Analyst unsure if regulation is in effect", "query": "GDPR Article 17 status 2026"}}
  ]
}}

Maximum {max_queries} queries. Prioritize: verifiable_claim > disagreement > uncertainty.
If no verifiable claims, disagreements, or uncertainties found, output: {{"queries": []}}

ANALYST OUTPUTS:
{combined_outputs}
"""

DISAGREEMENT_EXTRACTION_PROMPT = """\
You are reviewing Round 2 outputs from AI analysts who challenged each other's views.
Identify at most 2 specific factual disputes that require citation-backed resolution.

A factual dispute is: one analyst explicitly challenges a specific fact stated by another
(not an opinion difference — a verifiable fact like a number, date, or event).

Output ONLY valid JSON (no markdown fences):
{{
  "disputes": [
    {{
      "dispute": "Model A claims X; Model B claims Y",
      "query": "precise search query to resolve this dispute"
    }}
  ]
}}

Maximum 2 disputes. Only include genuinely contested verifiable facts.
If no factual disputes found, output: {{"disputes": []}}

ROUND 2 OUTPUTS:
{r2_outputs}
"""

ROUND2_PROMPT = """\
Below attached you will find the views of 4 LLMs as an answer to the
following prompt:

[ORIGINAL PROMPT]
{brief}

Given the original prompt, you need to analyze these views in a skeptical
yet objective and constructive way and produce a complete report with your views.
Focus your analysis on the core question in the original prompt. For each prior view:
1. Identify which arguments directly address the core question and which are tangential.
2. Challenge assumptions — name specific logical flaws if present.
3. Note where views agree (genuine convergence) vs where they disagree (and why).
4. Take a clear position where the evidence supports one. Do not hedge for the sake of balance.

Find the views below:

[LLM 1]
{r1_view1}

[LLM 2]
{r1_view2}

[LLM 3]
{r1_view3}

[LLM 4]
{r1_view4}
"""

ROUND3_PROMPT = """\
Below attached you will find the views of 3 LLMs from Round 2 as an answer to the
following prompt:

[ORIGINAL PROMPT]
{brief}

Given the original prompt, you need to analyze these views in a skeptical
yet objective and constructive way and produce a complete report with your views.
Focus your analysis on the core question in the original prompt. For each prior view:
1. Identify which arguments directly address the core question and which are tangential.
2. Challenge assumptions — name specific logical flaws if present.
3. Note where views agree (genuine convergence) vs where they disagree (and why).
4. Take a clear position where the evidence supports one. Do not hedge for the sake of balance.

Find the views below:

[LLM 1]
{r2_view1}

[LLM 2]
{r2_view2}

[LLM 3]
{r2_view3}
"""

ROUND4_PROMPT = """\
Below attached you will find the views of 2 LLMs from Round 3 as an answer to the
following prompt:

[ORIGINAL PROMPT]
{brief}

Given the original prompt, you need to analyze these views in a skeptical
yet objective and constructive way and produce a complete report with your views.
Focus your analysis on the core question in the original prompt. For each prior view:
1. Identify which arguments directly address the core question and which are tangential.
2. Challenge assumptions — name specific logical flaws if present.
3. Note where views agree (genuine convergence) vs where they disagree (and why).
4. Take a clear position where the evidence supports one. Do not hedge for the sake of balance.

Find the views below:

[LLM 1]
{r3_view1}

[LLM 2]
{r3_view2}
"""

SYNTHESIS_PROMPT_WITH_DELTA = """\
Below attached you will find the final views of two LLMs (Round {final_round}) as an answer to the
following prompt:

[ORIGINAL PROMPT]
{brief}

Given the original prompt, you need to analyze these views in a skeptical yet objective
and constructive way and produce the FINAL REPORT with your views.

SYNTHESIS DISCIPLINE: Your report must answer the core question in the original prompt.
Create the final document using ONLY the arguments explicitly present in
[LLM 1 — ROUND {final_round} FINAL POSITION] and [LLM 2 — ROUND {final_round} FINAL POSITION] below.
DO NOT INVENT NEW ARGUMENTS. DO NOT introduce reasoning, conclusions, or positions that are not
directly stated in those two outputs. If the analysts drifted toward secondary topics, correct the
drift — but only by selecting from what they actually wrote, never by adding your own analysis.

Find the Round {final_round} views below:

[LLM 1 — ROUND {final_round} FINAL POSITION]
{curr_descartes}

[LLM 2 — ROUND {final_round} FINAL POSITION]
{curr_socrates}

════════════════════════════════════════════════════════════════
SECOND TASK — DELTA REPORT
Write this as a completely separate document AFTER the main report.
The Round {prev_round} views below are PROVIDED FOR THE DELTA REPORT ONLY.
DO NOT use them in the main report above. DO NOT let them influence your synthesis.
════════════════════════════════════════════════════════════════

[LLM 1 — ROUND {prev_round} — FOR DELTA ONLY]
{prev_descartes}

[LLM 2 — ROUND {prev_round} — FOR DELTA ONLY]
{prev_socrates}

After completing the main Deliberation Report, append the following as a standalone section.

DELTA EVALUATION CONTEXT: The purpose of this delta report is to help us calibrate
over time whether running Round {final_round} produced real analytical value beyond
Round {prev_round}. To make that judgment meaningful, you must evaluate against the
original question — not just whether the text changed, but whether the change moved
the needle on answering what was actually asked.

The original question is reproduced here for your reference:

[ORIGINAL QUESTION]
{brief_objective}

---BEGIN DELTA REPORT---

# Delta Report: Round {prev_round} → Round {final_round}

## 1. Position Changes
Did either model change its position between Round {prev_round} and Round {final_round}?
List specific claims or conclusions that shifted. If none changed, say so explicitly.

## 2. New Arguments Relevant to the Brief
What arguments appeared in Round {final_round} that were absent in Round {prev_round}
AND are directly relevant to the original question?
Ignore cosmetic rewording or tangential additions. If none, say so explicitly.

## 3. Convergence
Did the two models converge further or diverge between rounds?
One sentence verdict + brief justification.

## 4. Round Verdict
**Was Round {final_round} worth running, given the original question?**
Verdict: **YES / MARGINAL / NO** — two sentences maximum justifying the verdict.

---END DELTA REPORT---
"""

# V2: Conditional output format (not mandatory sections)
OUTPUT_FORMAT_INSTRUCTION = """

Use the following output structure WHERE APPLICABLE. Skip sections that do not fit the
nature of the question. Not all sections are required for every brief.

Start your report with this YAML frontmatter block (fill in the bracketed values):

---
type: deliberation-report
version: 2
tool: brain
run_id: [will be filled by orchestrator]
timestamp: [will be filled by orchestrator]
rounds_completed: [will be filled by orchestrator]
rounds_requested: [will be filled by orchestrator]
consensus_level: [you determine: strong | partial | split]
outcome: [you determine: CONSENSUS | PARTIAL_CONSENSUS | NO_CONSENSUS]
confidence: [you determine: high | medium | low]
---

Then use these sections IN THIS ORDER (skip any that don't apply):

# Deliberation Report: [Brief Title — max 10 words]

## TL;DR
[2-3 sentences MAXIMUM. What was asked, what was concluded, and why.]

## Verdict
| Question | Position | Confidence | Consensus |
|----------|----------|------------|-----------|
| [Key question] | [Clear answer] | HIGH/MED/LOW | All agreed / Contested |

## Consensus Map

### Agreed (all models converged independently)
1. [Finding]

### Contested (models held different positions)
1. [Point] — Position A: [who + reasoning] / Position B: [who + reasoning]

### Evolved (positions that changed across rounds — omit if single-round run)
1. [What shifted and what caused the shift]

## Key Findings

### Finding 1: [Title]
**Conclusion:** [One sentence]
**Evidence:** [Supporting reasoning from the models]
**Confidence:** HIGH / MEDIUM / LOW
**Dissent:** [Any dissenting view, or "None"]

## Risk Factors (omit if no significant risks identified)
| Risk | Severity | Mitigation |
|------|----------|------------|
| [Risk] | HIGH/MED/LOW | [What to do about it] |

## Action Items (omit if no executable actions arise)
- [ ] **[ACTION-1]:** [Specific executable action] -> Assignee: [Agent/Christos]

## Round Evolution (omit if single-round run)
| Round | Key Development | Triggered By |
|-------|----------------|--------------|
| R1 | [Initial positions] | Original brief |

## Provenance
- Run ID: [from metadata]
- Models: [from metadata]
- Fallbacks: [from metadata]
- Wall clock: [from metadata]
"""


# ── Logger ────────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self, path: Path):
        self._fh   = open(path, "w", buffering=1)
        self._lock = threading.Lock()

    def log(self, msg: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        with self._lock:
            print(line, flush=True)
            self._fh.write(line + "\n")

    def close(self):
        with self._lock:
            self._fh.close()


def write_proof(outdir: Path, proof: dict) -> None:
    (outdir / "proof.json").write_text(json.dumps(proof, indent=2))


def emit_model_failure(round_num: int, model_name: str, error_type: str, outdir: Path) -> None:
    print(f"[BRAIN ERROR] Round {round_num}: Model '{model_name}' failed.", file=sys.stderr)
    print(f"[BRAIN ERROR] Reason: {error_type}", file=sys.stderr)
    print("[BRAIN ERROR] This is not recoverable — aborting Brain run.", file=sys.stderr)
    print(f"[BRAIN ERROR] Run directory preserved at: {outdir}", file=sys.stderr)
    sys.exit(4 + round_num - 2)


# ── LLM callers ───────────────────────────────────────────────────────────────

def call_haiku(prompt: str, max_tokens: int = 1500) -> str:
    """Lightweight Haiku call via OpenRouter. ~5s."""
    payload = json.dumps({
        "model":       HAIKU_MODEL,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens":  max_tokens,
    }).encode("utf-8")
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer":  "https://openclaw.ai",
        "X-Title":       "Brain-V2-Extractor",
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload, headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return json.dumps({"queries": [], "disputes": [], "error": str(e)})


def call_sonar(query: str, max_tokens: int = 1500) -> str:
    """Sonar Pro call via OpenRouter. Returns raw text with citations."""
    prompt = (
        f"Search the web and provide factual, citation-backed answers for this query:\n\n{query}\n\n"
        "For each finding, provide:\n"
        "1. A clear factual statement with specific numbers/dates\n"
        "2. The source URL\n"
        "3. The title of the source\n\n"
        "Return 3-5 distinct findings. Be specific with numbers, dates, and sources."
    )
    payload = json.dumps({
        "model":       SONAR_MODEL,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens":  max_tokens,
    }).encode("utf-8")
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer":  "https://openclaw.ai",
        "X-Title":       "Brain-V2-SonarDeep",
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload, headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=80) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return None  # Caller must check for None (was: silent error string)


# ── Research functions ────────────────────────────────────────────────────────

def _brave_search_raw(query: str, log=None) -> list:
    """Call Brave Search API. Returns list of {title, url, snippet} dicts.
    Returns None on failure (not empty list) so callers can distinguish
    'no results' from 'search broken'.
    V6: Extracts extra_snippets from Brave API for deeper evidence context."""
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({
        "q": query,
        "count": 5,
    })
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": "BSAGt5BmT-3lMJzBnBOglSoYYs0ev1D",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=24) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for item in data.get("web", {}).get("results", []):
            snippet = item.get("description", "")
            # V6 Fix 6: Append extra excerpts for deeper context
            extra = item.get("extra_snippets", [])
            if extra and isinstance(extra, list):
                extra_text = " ".join(s.strip() for s in extra[:3] if isinstance(s, str) and s.strip())
                if extra_text:
                    snippet = f"{snippet} {extra_text}"[:500]
            results.append({
                "title":   item.get("title", ""),
                "url":     item.get("url", ""),
                "snippet": snippet,
            })
        return results
    except Exception as exc:
        if log:
            log.log(f"  [BRAVE-ERROR] Query failed: {exc}")
        return None  # None = failure, [] = no results


def gap_extract_and_brave(
    round_num: int,
    model_outputs: dict,
    ledger: EvidenceLedger,
    search_mode: str,
    log: Logger,
) -> None:
    """R1→R2 research gate: Gap Extractor (Haiku) + Brave Search.
    Admits evidence items directly into ledger."""

    log.log(f"\n── R{round_num}→R{round_num+1} Research Phase (Brave) ──")

    if search_mode == "training_only":
        ledger.search_diag_training_only_skips += 1
        open_ids = []  # no objection data in Brain V2 Brave gate
        log.log(
            f"  [SEARCH-MODE-LOCK] engine=brave current_mode=training_only "
            f"retrieval_skipped=gap_extract_and_brave skip_reason=hard_ceiling_training_only "
            f"open_objections_count=0 open_objection_ids={open_ids} "
            f"skip_count_this_run={ledger.search_diag_training_only_skips}"
        )
        return

    ledger.search_diag_live_retrieval_attempted = True
    max_queries = MAX_BRAVE_QUERIES_FULL if search_mode == "full" else MAX_BRAVE_QUERIES_MINIMAL

    combined = ""
    for model_name, text in model_outputs.items():
        truncated = text[:3000] if len(text) > 3000 else text
        combined += f"\n### {model_name}:\n{truncated}\n"

    if not combined.strip():
        log.log("  [RESEARCH] No model outputs to analyze — skipping")
        return

    log.log(f"  Gap extraction via Haiku (max_queries={max_queries})...")
    prompt = GAP_EXTRACTION_PROMPT.format(
        n=len(model_outputs),
        max_queries=max_queries,
        combined_outputs=combined,
    )
    raw = call_haiku(prompt)

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        log.log("  [RESEARCH] Could not parse gap extraction response")
        return

    try:
        extracted = json.loads(json_match.group())
    except json.JSONDecodeError:
        log.log("  [RESEARCH] JSON parse error in gap extraction")
        return

    queries_raw = extracted.get("queries", [])
    if not queries_raw:
        log.log("  [RESEARCH] No queries extracted — skipping Brave")
        return

    log.log(f"  {len(queries_raw)} query candidate(s) from extractor:")
    for q in queries_raw:
        log.log(f"    [{q.get('signal','?')}] {q.get('query','?')[:80]}")

    admitted_count = 0
    _brave_failures = 0
    _brave_attempts = 0
    for i, q_item in enumerate(queries_raw[:max_queries]):
        query = q_item.get("query", "").strip()
        signal_text = q_item.get("claim", "")

        if not query:
            continue

        # Sanitize
        query = _sanitize_query(query, ledger, log)
        if query is None:
            continue

        # Dedup
        q_norm = query.lower().strip()
        if q_norm in ledger.seen_brave_queries:
            log.log(f"  [BRAVE-DEDUP] Skipping duplicate query: {query[:60]}")
            continue
        ledger.seen_brave_queries.add(q_norm)
        _brave_attempts += 1

        log.log(f"  [BRAVE] Query {i+1}: {query[:80]}")
        results = _brave_search_raw(query, log=log)
        if results is None:
            _brave_failures += 1
            log.log(f"  [BRAVE-ERROR] Query {i+1} failed ({_brave_failures}/{_brave_attempts} failed)")
            continue
        log.log(f"  [BRAVE] Got {len(results)} results")

        for result in results:
            if not _is_relevant_result(result, query, signal_text):
                continue
            if not _is_evidence_relevant(result["title"], result["snippet"], ledger):
                continue

            eid = ledger.admit(
                topic=result["title"],
                fact=result["snippet"][:250],
                url=result["url"],
                confidence="MEDIUM",
                log=log,
                first_available_round=round_num + 1,
            )
            if eid:
                log.log(f"  [EVIDENCE-ADMITTED] source=brave id={eid} topic={result['title'][:60]}")
                admitted_count += 1

    # V5: Fail loudly if ALL Brave queries failed (search is systematically broken)
    if _brave_attempts > 0 and _brave_failures == _brave_attempts:
        log.log(f"  [BRAVE-SEARCH-UNAVAILABLE] ALL {_brave_attempts} queries failed — search is broken, aborting")
        raise RuntimeError(
            f"Brave Search unavailable: all {_brave_attempts} queries failed. "
            "Cannot produce evidence-backed results without search. Aborting."
        )

    log.log(f"  [BRAVE] Research phase complete: {admitted_count} evidence item(s) admitted")
    ledger.research_phases.append({
        "phase": f"R{round_num}→R{round_num+1}",
        "method": "brave",
        "queries_attempted": min(len(queries_raw), max_queries),
        "items_admitted": admitted_count,
    })


def disagreement_extract_and_sonar(
    model_outputs: dict,
    ledger: EvidenceLedger,
    log: Logger,
    gap_signals: list = None,
) -> None:
    """R2→R3 research gate: Sonar Pro deep evidence.

    V2.5 query construction: gap-first, disagreement-second.
      1. If gap_signals are available, convert them directly into Sonar queries
         (these are the concrete empirical unknowns the gap detector found).
      2. If query slots remain (MAX_SONAR_QUERIES not filled), backfill with
         disagreement-extracted queries from Haiku (the original V2.0 path).

    This ensures Sonar targets the actual contested claims rather than
    meta-level model disagreements about confidence or framing.
    """

    log.log("\n── R2→R3 Research Phase (Sonar Pro) ──")

    combined = ""
    for model_name, text in model_outputs.items():
        truncated = text[:3000] if len(text) > 3000 else text
        combined += f"\n### {model_name}:\n{truncated}\n"

    if not combined.strip():
        log.log("  [SONAR] No R2 outputs to analyze — skipping")
        return

    # ── Stage 1: Gap-anchored queries (primary) ──
    gap_queries = []
    if gap_signals:
        # Build topic class for query context
        if not ledger.topic_class:
            ledger.topic_class = _extract_topic_class(ledger.task)
        topic_ctx = ledger.topic_class

        for sig in gap_signals[:MAX_SONAR_QUERIES]:
            gap_text = getattr(sig, "gap_text", "") or ""
            if not gap_text or len(gap_text.split()) < 3:
                continue
            # Build a scenario-anchored query from the gap text + topic class
            query = f"{topic_ctx} {gap_text}".strip()
            query = " ".join(query.split()[:14])  # cap at 14 words
            query = _sanitize_query(query, ledger, log)
            if query is None:
                continue
            # Dedup
            q_norm = query.lower().strip()
            if q_norm in ledger.seen_brave_queries:
                log.log(f"  [SONAR-DEDUP] Skipping gap query: {query[:60]}")
                continue
            ledger.seen_brave_queries.add(q_norm)
            gap_queries.append(query)
            ledger.gaps_queried.append({
                "gap_id": getattr(sig, "objection_id", "?"),
                "query_text": query[:120], "engine": "sonar",
            })
            log.log(f"  [SONAR-GAP-QUERY] From {getattr(sig, 'objection_id', '?')}: {query[:80]}")
        # Track gaps dropped due to slot exhaustion
        for sig in gap_signals[MAX_SONAR_QUERIES:]:
            gap_id = getattr(sig, "objection_id", "?")
            ledger.gaps_dropped.append({
                "gap_id": gap_id, "reason": f"slot_limit({MAX_SONAR_QUERIES})",
            })
            log.log(f"  [GAP-QUERY-DROPPED] gap_id={gap_id} reason=slot_limit({MAX_SONAR_QUERIES})")

    if gap_queries:
        log.log(f"  {len(gap_queries)} gap-anchored query/queries built")

    # ── Stage 2: Disagreement-derived queries (backfill) ──
    disagreement_queries = []
    remaining_slots = MAX_SONAR_QUERIES - len(gap_queries)

    if remaining_slots > 0:
        log.log("  Disagreement extraction via Haiku (backfill)...")
        prompt = DISAGREEMENT_EXTRACTION_PROMPT.format(r2_outputs=combined)
        raw = call_haiku(prompt)

        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                extracted = json.loads(json_match.group())
                disputes = extracted.get("disputes", [])
                if disputes:
                    log.log(f"  {len(disputes)} dispute(s) identified (backfill candidates):")
                    for d in disputes:
                        log.log(f"    {d.get('dispute', '?')[:80]}")

                    for dispute in disputes[:remaining_slots]:
                        query = dispute.get("query", "").strip()
                        if not query:
                            continue
                        query = _sanitize_query(query, ledger, log)
                        if query is None:
                            continue
                        # Dedup
                        query_words = query.lower().split()
                        query_prefix = " ".join(query_words[:8])
                        is_dup = any(
                            " ".join(seen.split()[:8]) == query_prefix
                            for seen in ledger.seen_brave_queries
                        )
                        if is_dup:
                            log.log(f"  [SONAR-DEDUP] Skipping backfill: {query[:60]}")
                            continue
                        disagreement_queries.append(query)
                        log.log(f"  [SONAR-BACKFILL-QUERY] {query[:80]}")
                else:
                    log.log("  [SONAR] No factual disputes found for backfill")
            except json.JSONDecodeError:
                log.log("  [SONAR] JSON parse error in disagreement extraction (backfill)")
        else:
            log.log("  [SONAR] Could not parse disagreement extraction response (backfill)")
    else:
        log.log(f"  [SONAR] Gap queries fill all {MAX_SONAR_QUERIES} slots — skipping disagreement backfill")

    # ── Execute queries: gap-anchored first, then disagreement backfill ──
    all_queries = gap_queries + disagreement_queries
    if not all_queries:
        log.log("  [SONAR] No viable queries — skipping Sonar")
        return

    log.log(f"  Executing {len(all_queries)} Sonar query/queries ({len(gap_queries)} gap + {len(disagreement_queries)} backfill)")
    ledger.search_diag_live_retrieval_attempted = True  # V3 telemetry: Sonar is live retrieval

    admitted_count = 0
    _sonar_failures = 0
    _sonar_attempts = 0
    for i, query in enumerate(all_queries[:MAX_SONAR_QUERIES]):
        source_label = "gap" if i < len(gap_queries) else "backfill"
        log.log(f"  [SONAR] Query {i+1} ({source_label}): {query[:80]}")
        _sonar_attempts += 1
        raw_text = call_sonar(query)

        if raw_text is None:
            _sonar_failures += 1
            log.log(f"  [SONAR-ERROR] Query {i+1} failed ({_sonar_failures}/{_sonar_attempts} failed)")
            continue

        # Parse Sonar response into evidence items
        chunks = re.split(r"\n\s*\d+[\.\)]\s*", raw_text)
        for chunk in chunks:
            chunk = chunk.strip()
            if len(chunk) < 20:
                continue
            url_match = re.search(r"https?://[^\s\)\]]+", chunk)
            url = url_match.group(0) if url_match else ""
            lines = chunk.split("\n")
            title = lines[0][:100].strip("*#- ")
            snippet = chunk[:280]

            if not _is_evidence_relevant(title, snippet, ledger):
                continue

            eid = ledger.admit(
                topic=title,
                fact=snippet,
                url=url,
                confidence="MEDIUM",
                log=log,
                first_available_round=3,  # Sonar fires between R2→R3
            )
            if eid:
                log.log(f"  [EVIDENCE-ADMITTED] source=sonar id={eid} topic={title[:60]}")
                admitted_count += 1

    # V5: Fail loudly if ALL Sonar queries failed
    if _sonar_attempts > 0 and _sonar_failures == _sonar_attempts:
        log.log(f"  [SONAR-SEARCH-UNAVAILABLE] ALL {_sonar_attempts} queries failed — Sonar is broken, aborting")
        raise RuntimeError(
            f"Sonar Pro unavailable: all {_sonar_attempts} queries failed. "
            "Cannot produce evidence-backed results without deep search. Aborting."
        )

    log.log(f"  [SONAR] Research phase complete: {admitted_count} evidence item(s) admitted")
    ledger.research_phases.append({
        "phase": "R2→R3",
        "method": "sonar",
        "queries_attempted": len(all_queries[:MAX_SONAR_QUERIES]),
        "gap_queries": len(gap_queries),
        "backfill_queries": len(disagreement_queries),
        "items_admitted": admitted_count,
    })


def r1_to_r2_research_and_cooldown(
    model_outputs: dict,
    ledger: EvidenceLedger,
    search_mode: str,
    outdir: Path,
    log: Logger,
    cooldown_s: int,
) -> None:
    """Run R1→R2 research phase DURING cooldown. Zero added wall time for short runs.

    V2.3 control flow: evaluate escalation BEFORE the Brave attempt for
    consistency with R2→R3 and R3→R4 wrappers. At cycle=0 with 0 skips,
    escalation will not fire, so this is a no-op reorder for uniformity.

    Order:
      1. Extract evidence gaps from R1 outputs
      2. Emit LIVE-EVIDENCE-CANDIDATE (observability)
      3. Evaluate escalation (won't fire at cycle=0, but logged)
      4. Run Brave gap extraction using ledger.search_mode
      5. Cooldown
    """
    t0 = time.time()

    # ── Step 1-3: evidence-gap detection + escalation (BEFORE research) ──
    gap_signals = _extract_evidence_gap_signals(model_outputs, ledger, log, round_num=1)
    _maybe_emit_live_evidence_candidate(ledger, log, cycle=0, open_objections=gap_signals)
    _maybe_escalate_search_mode(ledger, log, cycle=0, open_objections=gap_signals)

    # ── Step 4: Brave research using ledger.search_mode ──
    gap_extract_and_brave(1, model_outputs, ledger, ledger.search_mode, log)

    elapsed = time.time() - t0
    remaining = cooldown_s - elapsed
    if remaining > 0:
        log.log(f"  ⏳ Cooldown: {remaining:.0f}s remaining (research took {elapsed:.0f}s)")
        time.sleep(remaining)
    else:
        log.log(f"  ⏳ Research took {elapsed:.0f}s (exceeded {cooldown_s}s cooldown by {-remaining:.0f}s)")


def r2_to_r3_research_and_cooldown(
    model_outputs: dict,
    ledger: EvidenceLedger,
    search_mode: str,
    outdir: Path,
    log: Logger,
    cooldown_s: int,
) -> None:
    """Run R2→R3 research DURING cooldown.

    V2.3 control flow: evaluate escalation BEFORE the Sonar attempt so that
    a same-phase promotion (training_only → minimal) is immediately actionable.

    Order:
      1. Extract evidence gaps from R2 outputs
      2. Emit LIVE-EVIDENCE-CANDIDATE (observability)
      3. Evaluate escalation (may promote training_only → minimal)
      4. Run Sonar using ledger.search_mode (now reflects any promotion)
      5. Cooldown
    """
    t0 = time.time()

    # ── Step 1-3: evidence-gap detection + escalation (BEFORE research) ──
    gap_signals = _extract_evidence_gap_signals(model_outputs, ledger, log, round_num=2)
    _maybe_emit_live_evidence_candidate(ledger, log, cycle=1, open_objections=gap_signals)
    _maybe_escalate_search_mode(ledger, log, cycle=1, open_objections=gap_signals)

    # ── Step 4: Sonar research using the (possibly just-escalated) mode ──
    if ledger.search_mode in ("full", "minimal"):
        try:
            disagreement_extract_and_sonar(model_outputs, ledger, log, gap_signals=gap_signals)
        except Exception as exc:
            log.log(f"  [SONAR] Unexpected error (non-fatal): {exc}")
    else:
        log.log(f"  [RESEARCH] R2→R3 Sonar skipped — mode={ledger.search_mode}")

    elapsed = time.time() - t0
    remaining = cooldown_s - elapsed
    if remaining > 0:
        log.log(f"  ⏳ Cooldown: {remaining:.0f}s remaining (research took {elapsed:.0f}s)")
        time.sleep(remaining)
    else:
        log.log(f"  ⏳ Research took {elapsed:.0f}s (exceeded {cooldown_s}s cooldown by {-remaining:.0f}s)")


def r3_to_r4_research_and_cooldown(
    model_outputs: dict,
    ledger: EvidenceLedger,
    outdir: Path,
    log: Logger,
    cooldown_s: int,
) -> None:
    """R3→R4 research slot — fires Brave gap extraction when mode is minimal or full.

    New in V2.1: previously no research slot existed between R3 and R4.
    Models in R3 often flag explicit evidence gaps that this slot can now address.
    Post-research: emit evidence-gap observability + attempt escalation (last chance).
    """
    t0 = time.time()

    log.log(f"\n── R3→R4 Research Phase (Brave) ──")

    # Extract evidence gaps from R3 model outputs first (for escalation and query generation)
    gap_signals = _extract_evidence_gap_signals(model_outputs, ledger, log, round_num=3)

    # Attempt escalation before research (last chance for training_only → minimal)
    _maybe_emit_live_evidence_candidate(ledger, log, cycle=2, open_objections=gap_signals)
    _maybe_escalate_search_mode(ledger, log, cycle=2, open_objections=gap_signals)

    # Now run Brave with the (possibly escalated) search mode
    gap_extract_and_brave(3, model_outputs, ledger, ledger.search_mode, log)

    elapsed = time.time() - t0
    remaining = cooldown_s - elapsed
    if remaining > 0:
        log.log(f"  ⏳ Cooldown: {remaining:.0f}s remaining (research took {elapsed:.0f}s)")
        time.sleep(remaining)
    else:
        log.log(f"  ⏳ Research took {elapsed:.0f}s (exceeded {cooldown_s}s cooldown by {-remaining:.0f}s)")


def inter_round_cooldown(log: Logger, seconds: int = INTER_ROUND_COOLDOWN_S):
    log.log(f"  ⏳ Inter-round cooldown: {seconds}s")
    time.sleep(seconds)


# ── Model invocation (unchanged from V1) ─────────────────────────────────────

def invoke_hermes_synthesis(outdir: Path, synthesis_prompt_path: Path, log: Logger) -> dict:
    report_path = outdir / "hermes-final-report.md"
    session_id = str(uuid4())
    task = "\n".join([
        f"STEP SYNTHESIS: OUTDIR={outdir}/",
        "",
        "Run the Brain synthesis step only.",
        f"Read the prebuilt synthesis prompt from: {synthesis_prompt_path}",
        "Use that prompt as the synthesis input.",
        f"Write the final report to: {report_path}",
        "Update /tmp/hermes-status.txt as you progress.",
        "When complete, reply with a short confirmation that includes the report path.",
    ])
    cmd = [
        "node",
        "/app/openclaw.mjs",
        "agent",
        "--agent",  "hermes",
        "--session-id", session_id,
        "--message", task,
        "--timeout", str(HERMES_TIMEOUT_S),
        "--json",
    ]
    t0 = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=HERMES_TIMEOUT_S + 60)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            raise
    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - t0, 1)
        return {
            "status": "TIMEOUT",
            "elapsed_s": elapsed,
            "report_path": str(report_path) if report_path.exists() else None,
            "status_path": str(HERMES_STATUS_PATH) if HERMES_STATUS_PATH.exists() else None,
            "error": f"timeout after {elapsed}s",
        }
    except Exception as exc:
        elapsed = round(time.time() - t0, 1)
        return {
            "status": "ERROR",
            "elapsed_s": elapsed,
            "report_path": str(report_path) if report_path.exists() else None,
            "status_path": str(HERMES_STATUS_PATH) if HERMES_STATUS_PATH.exists() else None,
            "error": str(exc),
        }

    elapsed = round(time.time() - t0, 1)
    stdout = (stdout or "").strip()
    stderr = (stderr or "").strip()
    payload_text = None
    response_status = None

    if stdout:
        try:
            response = json.loads(stdout)
            response_status = response.get("status")
            payloads = ((response.get("result") or {}).get("payloads")) or []
            payload_text = "\n\n".join(
                p.get("text", "").strip()
                for p in payloads
                if isinstance(p, dict) and p.get("text")
            ).strip() or None
        except json.JSONDecodeError:
            payload_text = stdout

    if payload_text and not report_path.exists():
        report_path.write_text(payload_text)

    result = {
        "status": "COMPLETE" if proc.returncode == 0 and report_path.exists() else "FAILED",
        "elapsed_s": elapsed,
        "report_path": str(report_path) if report_path.exists() else None,
        "status_path": str(HERMES_STATUS_PATH) if HERMES_STATUS_PATH.exists() else None,
        "session_id": session_id,
        "response_status": response_status,
    }
    if proc.returncode != 0:
        result["error"] = stderr or stdout or f"exit {proc.returncode}"
    elif not report_path.exists():
        result["error"] = "Synthesis stage completed without writing a final report"
    if stderr:
        result["stderr"] = stderr
    return result


def is_retryable(result: dict) -> bool:
    error = result.get("error", "")
    if "timeout" in error.lower():
        return True
    if error.startswith("exit") and result.get("size", 0) == 0:
        return True
    return False


def _invoke_model_once(model: str, prompt: str, outdir: Path, prefix: str, log: Logger) -> dict:
    out_path = outdir / f"{prefix}-{model}.txt"
    err_path = outdir / f"{prefix}-{model}-stderr.txt"
    script   = INVOKE[model]
    timeout  = TIMEOUTS[model]
    t0 = time.time()

    # Pass max_tokens to invoke scripts via environment variable
    # Thinking models (r1, reasoner) need large token budgets for chain-of-thought
    env = os.environ.copy()
    env["BRAIN_MAX_TOKENS"] = str(MODEL_MAX_TOKENS.get(model, 8192))

    try:
        log.log(f"  → {model}: starting (timeout {timeout}s)")
        prompt_tmp = outdir / f"{prefix}-{model}-input.txt"
        prompt_tmp.write_text(prompt, encoding='utf-8')
        with open(out_path, "w") as fout, open(err_path, "w") as ferr:
            with open(str(prompt_tmp), "r", encoding='utf-8') as fin:
                proc = subprocess.Popen(
                    ["bash", str(script)],
                    stdin=fin,
                    stdout=fout,
                    stderr=ferr,
                    start_new_session=True,
                    env=env,
                )
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait()
                    raise

        elapsed = round(time.time() - t0, 1)
        size    = out_path.stat().st_size if out_path.exists() else 0

        actual_model = None
        if err_path.exists():
            stderr_text = err_path.read_text(errors="replace")
            import re as _re
            m = _re.search(r'\[MODEL_USED:\s*(.+?)\]', stderr_text)
            if m:
                actual_model = m.group(1).strip()
        if actual_model is None:
            actual_model = PRIMARY_MODELS.get(model, "unknown")

        expected_model = PRIMARY_MODELS.get(model, model)
        model_tag = f" [fallback: {actual_model}]" if actual_model != expected_model else ""

        if proc.returncode != 0:
            if size >= MIN_RESPONSE_BYTES:
                log.log(f"  ⚠ {model}: exit={proc.returncode} but {size}b output — degraded-success{model_tag}")
                return {"model": model, "ok": True, "elapsed": elapsed, "size": size,
                        "path": str(out_path), "actual_model": actual_model,
                        "warning": f"exit {proc.returncode}"}
            log.log(f"  ✗ {model}: exit={proc.returncode} | {elapsed}s | {size}b")
            return {"model": model, "ok": False, "elapsed": elapsed, "size": size,
                    "actual_model": actual_model, "error": f"exit {proc.returncode}"}

        if size < MIN_RESPONSE_BYTES:
            log.log(f"  ✗ {model}: too small ({size}b < {MIN_RESPONSE_BYTES}b) | {elapsed}s")
            return {"model": model, "ok": False, "elapsed": elapsed, "size": size,
                    "actual_model": actual_model, "error": f"response too small ({size}b)"}

        log.log(f"  ✓ {model}: {elapsed}s | {size}b{model_tag}")
        return {"model": model, "ok": True, "elapsed": elapsed, "size": size,
                "path": str(out_path), "actual_model": actual_model}

    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - t0, 1)
        log.log(f"  ✗ {model}: TIMEOUT after {elapsed}s")
        return {"model": model, "ok": False, "elapsed": elapsed, "size": 0, "error": "timeout"}
    except Exception as exc:
        elapsed = round(time.time() - t0, 1)
        log.log(f"  ✗ {model}: ERROR — {exc}")
        return {"model": model, "ok": False, "elapsed": elapsed, "size": 0, "error": str(exc)}


def invoke_model(model: str, prompt: str, outdir: Path, prefix: str, log: Logger) -> dict:
    max_retries = MODEL_MAX_RETRIES.get(model, 0)
    cooldown = MODEL_RETRY_COOLDOWN_S.get(model, 60)
    for attempt in range(max_retries + 1):
        result = _invoke_model_once(model, prompt, outdir, prefix, log)
        if result["ok"]:
            return result
        if attempt < max_retries and is_retryable(result):
            log.log(f"  ⟳ {model}: retry {attempt+1}/{max_retries} in {cooldown}s — {result.get('error', 'unknown')}")
            time.sleep(cooldown)
            continue
        return result
    return result


def run_parallel(models: list, prompt: str, outdir: Path, prefix: str, log: Logger) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {
            executor.submit(invoke_model, m, prompt, outdir, prefix, log): m
            for m in models
        }
        for future in as_completed(futures):
            m = futures[future]
            results[m] = future.result()
    return results


def read_file(path: Path, fallback: str) -> str:
    if path.exists():
        content = path.read_text(errors="replace").strip()
        if len(content) >= MIN_RESPONSE_BYTES:
            return content
    return fallback


def find_last_valid_view(model: str, up_to_round: int, outdir: Path, label: str) -> str:
    for rnd in range(up_to_round, 0, -1):
        path = outdir / f"r{rnd}-{model}.txt"
        if path.exists():
            content = path.read_text(errors="replace").strip()
            if len(content) >= MIN_RESPONSE_BYTES:
                return f"[From Round {rnd} — Round {up_to_round} unavailable]\n\n{content}"
    return f"[{label} — no valid response in any round]"


def build_synthesis_prompt(brief: str, outdir: Path, final_round: int) -> str:
    if final_round == 1:
        view_parts = []
        for i, m in enumerate(ROUND1_MODELS, 1):
            text = read_file(outdir / f"r1-{m}.txt", f"[Analyst {i} Round 1 not available]")
            view_parts.append(f"[LLM {i} -- ROUND 1]\n{text}")

        base = (
            "Below attached you will find the initial views of the analysts:\n\n"
            "[ORIGINAL PROMPT]\n" + brief + "\n\n"
            "Analyze these views and produce the FINAL REPORT.\n\n" +
            "\n\n".join(view_parts) +
            "\n\nProduce a complete final report synthesizing all perspectives."
        )
        return base + OUTPUT_FORMAT_INSTRUCTION
    else:
        n = final_round
        synth_models = ROUND234_MODELS if ROUND234_MODELS else ["r1", "reasoner"]
        m1 = synth_models[0] if len(synth_models) >= 1 else "r1"
        m2 = synth_models[1] if len(synth_models) >= 2 else "reasoner"

        curr_d = read_file(outdir / f"r{n}-{m1}.txt", None) or \
                 find_last_valid_view(m1, n, outdir, f"Analyst 1 Round {n}")
        curr_s = read_file(outdir / f"r{n}-{m2}.txt", None) or \
                 find_last_valid_view(m2, n, outdir, f"Analyst 2 Round {n}")
        prev_d = read_file(outdir / f"r{n-1}-{m1}.txt", None) or \
                 find_last_valid_view(m1, n-1, outdir, f"Analyst 1 Round {n-1}")
        prev_s = read_file(outdir / f"r{n-1}-{m2}.txt", None) or \
                 find_last_valid_view(m2, n-1, outdir, f"Analyst 2 Round {n-1}")

        # For free-form briefs, use first 400 chars as the delta objective
        brief_objective = brief[:400] if len(brief) > 400 else brief

        base = SYNTHESIS_PROMPT_WITH_DELTA.format(
            brief=brief,
            brief_objective=brief_objective,
            final_round=n,
            prev_round=n - 1,
            curr_descartes=curr_d,
            curr_socrates=curr_s,
            prev_descartes=prev_d,
            prev_socrates=prev_s,
        )
        return base + OUTPUT_FORMAT_INSTRUCTION


# ── Standalone Leverage Profile (SLP) — transplanted from Chamber V3 ─────────
# Deterministic option-weighting using structured dominance, no LLM call.
# Appended to synthesis report post-synthesis as a supplementary section.

SLP_IMPACT_BANDS = ("CRITICAL", "HIGH", "MODERATE", "LOW")
SLP_FEASIBILITY_BANDS = ("HIGH", "MODERATE", "LOW", "UNCERTAIN")
SLP_TIME_BANDS = ("IMMEDIATE", "NEAR_TERM", "FLEXIBLE", "UNCERTAIN")
SLP_REVERSIBILITY_BANDS = ("BOUNDED", "MANAGEABLE", "HEAVY", "SEVERE")
SLP_EVIDENCE_BANDS = ("STRONG", "ADEQUATE", "LIMITED", "WEAK")
SLP_HIGHLIGHT_CONFIDENCE = ("CLEAR", "MARGINAL", "INDETERMINATE")


def _slp_band_index(value: str, bands: tuple) -> int:
    try:
        return bands.index(value)
    except ValueError:
        return len(bands)


def _slp_materially_worse(a: str, b: str, bands: tuple) -> bool:
    return _slp_band_index(a, bands) > _slp_band_index(b, bands)


def _slp_derive_option(name: str, conclusion: str, arguments: str, evidence_count: int, log=None) -> dict:
    """Derive SLP dimensions for a single position/option from model output text.

    Uses the same text-signal heuristics as Chamber V3's _slp_derive_dimensions.
    """
    combined = f"{conclusion} {arguments}".lower()

    # ── standalone_impact ──
    definitive_signals = (
        "eliminat", "definitive", "root cause", "remediat",
        "removes the vulnerability", "fixes the vulnerability",
        "permanent fix", "complete fix", "full remediation",
    )
    partial_signals = (
        "partial", "compensat", "temporary", "bridge", "buys time",
        "reduces probability", "reduces risk", "not a fix",
        "insufficient alone", "limited coverage", "bypass rate",
    )
    containment_signals = (
        "shutdown", "kill", "take offline", "eliminates all attack surface",
        "full containment", "zero attack surface",
    )

    has_definitive = any(sig in combined for sig in definitive_signals)
    has_partial = any(sig in combined for sig in partial_signals)
    has_containment = any(sig in combined for sig in containment_signals)

    if has_definitive and not has_partial:
        impact = "CRITICAL"
    elif has_containment and not has_partial:
        impact = "HIGH"
    elif has_definitive and has_partial:
        impact = "HIGH"
    elif has_partial:
        impact = "MODERATE"
    else:
        impact = "MODERATE"

    # ── execution_feasibility ──
    feasibility_concerns = sum(1 for kw in ("fail", "rollback", "untested", "complex", "risk")
                               if kw in combined)
    if feasibility_concerns >= 3:
        feasibility = "LOW"
    elif feasibility_concerns >= 2:
        feasibility = "MODERATE"
    else:
        feasibility = "HIGH"

    # ── time_to_protective_effect ──
    has_immediate = any(kw in combined for kw in ("immediately", "instant", "within minutes", "30 min"))
    has_slow = any(kw in combined for kw in ("hours", "2-hour", "2 hour", "window", "staged"))
    if has_immediate and not has_slow:
        time_rating = "IMMEDIATE"
    elif has_immediate or "fast" in combined:
        time_rating = "NEAR_TERM"
    elif has_slow:
        time_rating = "NEAR_TERM"
    else:
        time_rating = "FLEXIBLE"

    # ── reversibility_downside ──
    # Action-downside signals (from conclusion/arguments)
    action_bounded = ("bounded", "recoverable", "rollback", "reversible", "revert", "restore")
    action_severe = ("shutdown", "full outage", "service unavailability", "irrecoverable",
                     "cannot roll back", "permanent")
    action_heavy = ("extended outage", "prolonged", "unpredictable", "cascading", "data loss")

    has_bounded = any(sig in combined for sig in action_bounded)
    has_severe = any(sig in combined for sig in action_severe)
    has_heavy = any(sig in combined for sig in action_heavy)

    if has_bounded and not has_severe:
        reversibility = "BOUNDED"
    elif has_severe:
        reversibility = "SEVERE"
    elif has_heavy:
        reversibility = "HEAVY"
    else:
        reversibility = "MANAGEABLE"

    # ── evidence_confidence ──
    if evidence_count >= 3:
        ev_conf = "ADEQUATE"
    elif evidence_count >= 1:
        ev_conf = "LIMITED"
    else:
        ev_conf = "WEAK"

    return {
        "name": name,
        "impact": impact,
        "feasibility": feasibility,
        "time": time_rating,
        "reversibility": reversibility,
        "evidence": ev_conf,
    }


def _slp_extract_positions_from_report(report_path: Path, r4_outputs: dict, log=None) -> list:
    """Extract competing positions from Hermes verdict table + R4 outputs.

    Uses regex parsing of the consistent Hermes verdict table format.
    Returns list of dicts with name, conclusion, arguments, evidence_count.
    """
    positions = []
    report_text = ""
    if report_path and report_path.exists():
        report_text = report_path.read_text()

    # Extract verdict table rows: | Question | Position | Confidence | Consensus |
    verdict_rows = re.findall(
        r'\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\w+)\s*\|\s*(.+?)\s*\|',
        report_text,
    )

    # Identify distinct position names from R4 conclusions
    position_names = set()
    for model_name, text in r4_outputs.items():
        if not text:
            continue
        # Extract [CONCLUSION] section
        conclusion_match = re.search(
            r'\[CONCLUSION\]\s*(.+?)(?=\[(?:CONFIDENCE|KEY ARGUMENTS)|$)',
            text, re.DOTALL | re.IGNORECASE,
        )
        if conclusion_match:
            conclusion = conclusion_match.group(1).strip()[:500]
            # Identify position type from conclusion
            conclusion_lower = conclusion.lower()
            if any(kw in conclusion_lower for kw in ("patch", "deploy.*patch", "emergency patch")):
                position_names.add("patch-first")
            if any(kw in conclusion_lower for kw in ("waf", "firewall rule", "web application firewall")):
                position_names.add("waf-first")
            if any(kw in conclusion_lower for kw in ("shutdown", "take offline", "full shutdown")):
                position_names.add("shutdown")

    # If we couldn't extract positions, try from the report consensus map
    if not position_names:
        # Look for position labels in Agreed/Contested/Evolved sections
        for label_pattern in [r'(?:patch|WAF|shutdown|deploy|rollback)', ]:
            matches = re.findall(label_pattern, report_text, re.IGNORECASE)
            for m in matches:
                position_names.add(m.lower())

    if not position_names:
        if log:
            log.log("  [SLP] Could not extract distinct positions from synthesis report")
        return []

    # Build position profiles from R4 model outputs
    for pos_name in position_names:
        # Gather all R4 text related to this position
        combined_conclusion = ""
        combined_arguments = ""
        evidence_refs = set()

        for model_name, text in r4_outputs.items():
            if not text:
                continue
            text_lower = text.lower()

            # Check if this model advocates this position
            is_advocate = False
            if pos_name == "patch-first" and any(kw in text_lower for kw in ("patch", "deploy the patch", "emergency patch")):
                conclusion_match = re.search(r'\[CONCLUSION\]\s*(.+?)(?=\[|$)', text, re.DOTALL | re.IGNORECASE)
                if conclusion_match and "patch" in conclusion_match.group(1).lower():
                    is_advocate = True
            elif pos_name == "waf-first" and "waf" in text_lower:
                conclusion_match = re.search(r'\[CONCLUSION\]\s*(.+?)(?=\[|$)', text, re.DOTALL | re.IGNORECASE)
                if conclusion_match and "waf" in conclusion_match.group(1).lower():
                    is_advocate = True
            elif pos_name == "shutdown" and "shutdown" in text_lower:
                conclusion_match = re.search(r'\[CONCLUSION\]\s*(.+?)(?=\[|$)', text, re.DOTALL | re.IGNORECASE)
                if conclusion_match and "shutdown" in conclusion_match.group(1).lower():
                    is_advocate = True

            if is_advocate:
                conclusion_match = re.search(r'\[CONCLUSION\]\s*(.+?)(?=\[|$)', text, re.DOTALL | re.IGNORECASE)
                if conclusion_match:
                    combined_conclusion += " " + conclusion_match.group(1).strip()
                args_match = re.search(r'\[KEY ARGUMENTS\]\s*(.+?)(?=\[|$)', text, re.DOTALL | re.IGNORECASE)
                if args_match:
                    combined_arguments += " " + args_match.group(1).strip()
                # Count evidence references
                evidence_refs.update(re.findall(r'\bE\d{3}\b', text))

        if combined_conclusion.strip():
            positions.append({
                "name": pos_name,
                "conclusion": combined_conclusion.strip(),
                "arguments": combined_arguments.strip(),
                "evidence_count": len(evidence_refs),
            })

    if log:
        log.log(f"  [SLP] Extracted {len(positions)} position(s): {[p['name'] for p in positions]}")

    return positions


def _build_slp_section(report_path: Path, r4_outputs: dict, evidence_count: int,
                       log=None, controller_outcome_class: str = None) -> str:
    """Build the SLP markdown section to append to synthesis report.

    Returns empty string if SLP cannot be derived (no positions found).
    Phase 3C: controller_outcome_class used for split cap instead of synthesis frontmatter.
    """
    positions = _slp_extract_positions_from_report(report_path, r4_outputs, log)
    if not positions:
        return ""

    # Derive SLP dimensions for each position
    profiles = []
    for pos in positions:
        profile = _slp_derive_option(
            name=pos["name"],
            conclusion=pos["conclusion"],
            arguments=pos["arguments"],
            evidence_count=pos["evidence_count"],
            log=log,
        )
        profiles.append(profile)
        if log:
            log.log(
                f"  [SLP] {profile['name']}: impact={profile['impact']} "
                f"feasibility={profile['feasibility']} time={profile['time']} "
                f"reversibility={profile['reversibility']} evidence={profile['evidence']}"
            )

    # ── Phase 3C: Check if controller classified a split outcome ──
    _synthesis_is_split = False
    if controller_outcome_class and controller_outcome_class in ("PARTIAL_CONSENSUS", "NO_CONSENSUS"):
        _synthesis_is_split = True
        if log:
            log.log(f"  [SLP] controller outcome={controller_outcome_class} — SLP highlight capped to INDETERMINATE")
    elif report_path and report_path.exists():
        # Fallback: read from synthesis frontmatter if no controller outcome provided
        _report_head = report_path.read_text(encoding="utf-8")[:1000]
        import re as _re_d
        _outcome_m = _re_d.search(r"^outcome:\s*(\S+)", _report_head, _re_d.MULTILINE)
        _consensus_m = _re_d.search(r"^consensus_level:\s*(\S+)", _report_head, _re_d.MULTILINE)
        _outcome = _outcome_m.group(1).strip() if _outcome_m else ""
        _consensus = _consensus_m.group(1).strip() if _consensus_m else ""
        if _outcome in ("PARTIAL_CONSENSUS", "NO_CONSENSUS") or _consensus in ("split", "none"):
            _synthesis_is_split = True
            if log:
                log.log(f"  [SLP] synthesis outcome={_outcome} consensus={_consensus} — SLP highlight capped to INDETERMINATE")

    # ── Structured dominance ──
    # Sort by impact (best first = lowest index)
    profiles.sort(key=lambda p: _slp_band_index(p["impact"], SLP_IMPACT_BANDS))

    highlight_name = None
    highlight_confidence = "INDETERMINATE"
    highlight_rationale = ""
    highlight_caveat = "Portfolio layering provides additional escalation and fallback options not captured by standalone assessment."

    if len(profiles) == 1:
        highlight_name = profiles[0]["name"]
        highlight_confidence = "CLEAR"
        if profiles[0]["evidence"] in ("LIMITED", "WEAK"):
            highlight_confidence = "MARGINAL"
        highlight_rationale = f"{highlight_name} is the only identified position."
    elif len(profiles) >= 2:
        best = profiles[0]
        others = profiles[1:]

        # Check tie on impact
        tied = [o for o in others if o["impact"] == best["impact"]]
        if tied:
            tied_names = [o["name"] for o in tied]
            highlight_rationale = (
                f"{best['name']} and {', '.join(tied_names)} share the same standalone impact "
                f"({best['impact']}). No clear single-action leader."
            )
        else:
            # Best leads on impact — check viability dimensions
            highlight_name = best["name"]
            highlight_confidence = "CLEAR"
            cap_reasons = []

            for other in others:
                if _slp_materially_worse(best["feasibility"], other["feasibility"], SLP_FEASIBILITY_BANDS):
                    cap_reasons.append(f"worse feasibility vs {other['name']}")
                if _slp_materially_worse(best["reversibility"], other["reversibility"], SLP_REVERSIBILITY_BANDS):
                    cap_reasons.append(f"worse reversibility vs {other['name']}")

            if len(cap_reasons) >= 2:
                highlight_confidence = "INDETERMINATE"
                highlight_name = None
                highlight_rationale = f"Best-impact option has material tradeoffs: {'; '.join(cap_reasons)}."
            elif cap_reasons:
                highlight_confidence = "MARGINAL"
                highlight_rationale = f"{best['name']} leads on impact ({best['impact']}) but qualified: {'; '.join(cap_reasons)}."
            else:
                highlight_rationale = f"{best['name']} leads on impact ({best['impact']}) with no material viability tradeoffs."

            # Evidence cap
            if best["evidence"] in ("LIMITED", "WEAK") and highlight_confidence == "CLEAR":
                highlight_confidence = "MARGINAL"
                cap_reasons.append(f"evidence is {best['evidence']}")
                highlight_rationale += f" Capped to MARGINAL: evidence is {best['evidence']}."

    # V3 Fix D: If Hermes reported a split, override to INDETERMINATE
    if _synthesis_is_split and highlight_confidence != "INDETERMINATE":
        if log:
            log.log(f"  [SLP] Overriding highlight from {highlight_confidence} to INDETERMINATE — synthesis reported split outcome")
        highlight_confidence = "INDETERMINATE"
        if highlight_name:
            highlight_rationale = (
                f"{highlight_name} leads on standalone dimensions, but the deliberation "
                f"reached a split verdict. SLP cannot be more decisive than the synthesis."
            )
            highlight_name = None

    # ── Build markdown ──
    lines = [
        "",
        "---",
        "",
        "## Standalone Leverage Assessment",
        "",
        "| Option | Impact | Feasibility | Time | Reversibility | Evidence |",
        "|--------|--------|-------------|------|---------------|----------|",
    ]
    for p in profiles:
        lines.append(f"| {p['name']} | {p['impact']} | {p['feasibility']} | {p['time']} | {p['reversibility']} | {p['evidence']} |")

    lines.append("")
    if highlight_name:
        lines.append(f"**Standalone highlight:** {highlight_name} ({highlight_confidence} confidence)")
    else:
        lines.append(f"**Standalone highlight:** None ({highlight_confidence})")
    lines.append(f"**Rationale:** {highlight_rationale}")
    lines.append(f"**Caveat:** {highlight_caveat}")
    lines.append("")

    section = "\n".join(lines)

    if log:
        log.log(
            f"  [SLP-FINAL] profiles={len(profiles)} "
            f"highlight={highlight_name or 'none'} ({highlight_confidence})"
        )

    return section


# ── Phase 3A: Position extraction (deterministic-first, Haiku on ambiguity) ──

def _extract_position_deterministic(model_name, conclusion_text, confidence_text,
                                     options_list, log=None):
    """Deterministic position extraction from [CONCLUSION] text.

    Returns a position record dict. Sets extraction_confidence to 'low' if
    no option can be matched — caller should escalate to Haiku.
    """
    if not conclusion_text or not conclusion_text.strip():
        return {
            "model": model_name, "kind": "abstain", "primary_option": None,
            "components": [], "ordering": [], "confidence": confidence_text or "MEDIUM",
            "qualifier": "", "extraction_method": "deterministic",
            "extraction_confidence": "high",
        }

    text_lower = conclusion_text.lower()

    # Build match targets from options list
    option_matches = {}  # option_id -> match score
    for opt in options_list:
        opt_id = opt.get("id", "")
        label = opt.get("label", "").lower()
        opt_text = opt.get("text", "").lower()
        # Score: check for option ID mention (O1, O2...) or label keyword overlap
        score = 0
        if opt_id.lower() in text_lower:
            score += 10
        label_words = set(re.findall(r'[a-z]{4,}', label))
        if label_words:
            hits = sum(1 for w in label_words if w in text_lower)
            score += hits
        # Also check short distinctive keywords from the option text
        text_words = set(re.findall(r'[a-z]{4,}', opt_text))
        distinctive = text_words - {
            "should", "would", "could", "with", "that", "this", "from",
            "have", "been", "will", "into", "their", "them", "more",
            "than", "also", "other", "between", "about",
        }
        if distinctive:
            hits = sum(1 for w in list(distinctive)[:8] if w in text_lower)
            score += hits
        option_matches[opt_id] = score

    if not option_matches or max(option_matches.values()) == 0:
        return {
            "model": model_name, "kind": "none", "primary_option": None,
            "components": [], "ordering": [], "confidence": confidence_text or "MEDIUM",
            "qualifier": conclusion_text[:120].strip(),
            "extraction_method": "deterministic",
            "extraction_confidence": "low",
        }

    # Detect sequencing language
    _seq_patterns = [
        r'first\s+\w+.*?then\s+\w+', r'\w+\s+followed\s+by\s+\w+',
        r'\w+\s+before\s+\w+', r'immediate(?:ly)?\s+\w+.*?then\s+\w+',
        r'start\s+with\s+\w+.*?then\s+\w+', r'phase\s*1.*?phase\s*2',
        r'step\s*1.*?step\s*2',
    ]
    has_sequence = any(re.search(p, text_lower) for p in _seq_patterns)

    # Sort options by match score descending
    ranked = sorted(option_matches.items(), key=lambda x: x[1], reverse=True)
    best_id, best_score = ranked[0]
    second_id, second_score = ranked[1] if len(ranked) > 1 else (None, 0)

    # Fix: When sequence language is detected AND multiple options score > 0,
    # ALWAYS escalate to Haiku. Deterministic keyword scoring is unreliable
    # for determining ordering in sequence/hybrid cases.
    if has_sequence and second_score > 0:
        return {
            "model": model_name, "kind": "sequence",
            "primary_option": best_id,
            "components": [best_id, second_id],
            "ordering": [],
            "confidence": confidence_text or "MEDIUM",
            "qualifier": "sequence_detected_escalating",
            "extraction_method": "deterministic",
            "extraction_confidence": "low",  # forces Haiku escalation
        }
    elif second_score > 0 and second_score >= best_score * 0.5 and not has_sequence:
        # Both options moderately present but no sequencing language
        # Still ambiguous enough to escalate — could be hybrid
        return {
            "model": model_name, "kind": "hybrid",
            "primary_option": best_id,
            "components": [best_id, second_id],
            "ordering": [],
            "confidence": confidence_text or "MEDIUM",
            "qualifier": "multi_option_escalating",
            "extraction_method": "deterministic",
            "extraction_confidence": "low",  # forces Haiku escalation
        }
    else:
        # Single option clearly dominates (second option absent or very weak)
        conf = "high" if best_score >= 4 else "medium" if best_score >= 2 else "low"
        return {
            "model": model_name, "kind": "single",
            "primary_option": best_id,
            "components": [best_id],
            "ordering": [],
            "confidence": confidence_text or "MEDIUM",
            "qualifier": "",
            "extraction_method": "deterministic",
            "extraction_confidence": conf,
        }


def _extract_position_haiku(model_name, conclusion_text, confidence_text,
                             options_list, log=None):
    """Haiku-based position extraction for ambiguous conclusions."""
    opts_json = json.dumps([{"id": o["id"], "label": o["label"]} for o in options_list])
    prompt = (
        "You are a structured-output extraction tool. Given a model's conclusion "
        "and a set of options, determine which option the model advocates.\n\n"
        f"Options: {opts_json}\n\n"
        f"Model conclusion:\n{conclusion_text[:1500]}\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"chosen_option": "O1"|"O2"|...|"NONE"|"HYBRID"|"SEQUENCE", '
        '"components": ["O1","O2"], "ordering": ["O2","O1"], '
        '"qualifier": "brief note if needed"}\n\n'
        "Rules:\n"
        "- SEQUENCE means the model advocates doing options in a specific order\n"
        "- HYBRID means the model combines options without clear ordering\n"
        "- NONE means no clear advocacy for any listed option\n"
        "- components and ordering only needed for HYBRID/SEQUENCE\n"
    )
    try:
        raw = call_haiku(prompt, max_tokens=400)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            if log:
                log.log(f"    [POSITION-EXTRACT] Haiku returned no JSON for {model_name}")
            return {
                "model": model_name, "kind": "none", "primary_option": None,
                "components": [], "ordering": [],
                "confidence": confidence_text or "MEDIUM", "qualifier": "",
                "extraction_method": "haiku", "extraction_confidence": "low",
            }
        parsed = json.loads(json_match.group())
        chosen = parsed.get("chosen_option", "NONE")
        components = parsed.get("components", [])
        ordering = parsed.get("ordering", [])
        qualifier = parsed.get("qualifier", "")

        if chosen == "SEQUENCE":
            kind = "sequence"
            primary = ordering[0] if ordering else (components[0] if components else None)
        elif chosen == "HYBRID":
            kind = "hybrid"
            primary = components[0] if components else None
        elif chosen == "NONE":
            kind = "none"
            primary = None
        else:
            kind = "single"
            primary = chosen
            components = [chosen]

        return {
            "model": model_name, "kind": kind, "primary_option": primary,
            "components": components, "ordering": ordering,
            "confidence": confidence_text or "MEDIUM", "qualifier": qualifier,
            "extraction_method": "haiku", "extraction_confidence": "medium",
        }
    except Exception as exc:
        if log:
            log.log(f"    [POSITION-EXTRACT] Haiku failed for {model_name}: {exc}")
        return {
            "model": model_name, "kind": "none", "primary_option": None,
            "components": [], "ordering": [],
            "confidence": confidence_text or "MEDIUM", "qualifier": "",
            "extraction_method": "haiku_failed", "extraction_confidence": "low",
        }


def _extract_positions_for_round(round_num, model_outputs, ledger, log):
    """Phase 3A: Extract structured positions from all models in a round.

    Deterministic-first: only escalates to Haiku if extraction_confidence is 'low'.
    Stores results in ledger.model_positions_by_round[round_num].
    """
    options = ledger.explicit_options or ledger.extracted_options
    if not options:
        log.log(f"  [POSITION-EXTRACT] R{round_num}: no options available — skipping")
        return

    positions = {}
    methods_used = set()

    for model_name, text in model_outputs.items():
        if not text:
            positions[model_name] = {
                "model": model_name, "kind": "abstain", "primary_option": None,
                "components": [], "ordering": [], "confidence": "LOW",
                "qualifier": "no output", "extraction_method": "deterministic",
                "extraction_confidence": "high",
            }
            continue

        # Extract [CONCLUSION] section
        concl_m = re.search(
            r'\[CONCLUSION\]\s*(.+?)(?=\[(?:CONFIDENCE|KEY ARGUMENTS)|$)',
            text, re.DOTALL | re.IGNORECASE,
        )
        conclusion = concl_m.group(1).strip()[:1500] if concl_m else text[:500]

        # Extract [CONFIDENCE] marker
        conf_m = re.search(r'\[CONFIDENCE[:\s]*(\w+)', text, re.IGNORECASE)
        confidence = conf_m.group(1).upper() if conf_m else "MEDIUM"

        # Step 1: deterministic extraction
        pos = _extract_position_deterministic(model_name, conclusion, confidence, options, log)

        # Step 2: escalate to Haiku if low confidence
        if pos["extraction_confidence"] == "low":
            if log:
                log.log(f"    [POSITION-EXTRACT] {model_name}: deterministic→low, escalating to Haiku")
            pos = _extract_position_haiku(model_name, conclusion, confidence, options, log)

        methods_used.add(pos["extraction_method"])
        positions[model_name] = pos

    ledger.model_positions_by_round[round_num] = positions

    # Log summary
    for m, p in positions.items():
        log.log(
            f"  [POSITION-EXTRACT] R{round_num} {m}: kind={p['kind']} "
            f"option={p['primary_option']} confidence={p['confidence']} "
            f"method={p['extraction_method']}({p['extraction_confidence']})"
        )

    return positions


def _extract_options_from_r1(model_outputs, ledger, log):
    """Phase 3A: For open-ended briefs, extract candidate options from R1 conclusions via Haiku."""
    combined = ""
    for model_name, text in model_outputs.items():
        if not text:
            continue
        concl_m = re.search(
            r'\[CONCLUSION\]\s*(.+?)(?=\[(?:CONFIDENCE|KEY ARGUMENTS)|$)',
            text, re.DOTALL | re.IGNORECASE,
        )
        conclusion = concl_m.group(1).strip()[:800] if concl_m else text[:400]
        combined += f"\n{model_name}: {conclusion}\n"

    prompt = (
        "You are a structured-output extraction tool. Multiple analysts have provided "
        "recommendations. Extract the distinct top-level strategic options they propose.\n\n"
        f"Analyst conclusions:\n{combined}\n\n"
        "Rules:\n"
        "- Only extract DISTINCT top-level alternatives (not sub-steps)\n"
        "- Merge options that are substantively the same across analysts\n"
        "- 2-6 options maximum\n\n"
        'Respond with ONLY JSON: {"options": [{"id": "O1", "label": "short label", '
        '"text": "one-sentence description"}]}'
    )
    try:
        raw = call_haiku(prompt, max_tokens=600)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            log.log("  [OPTION-EXTRACT-R1] No JSON in Haiku response")
            return
        parsed = json.loads(json_match.group())
        options = parsed.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            log.log("  [OPTION-EXTRACT-R1] Fewer than 2 options extracted")
            return
        clean = []
        for i, opt in enumerate(options[:6]):
            if not isinstance(opt, dict):
                continue
            text = str(opt.get("text", "")).strip()
            label = str(opt.get("label", "")).strip()
            if len(text) < 5:
                continue
            clean.append({"id": f"O{i+1}", "label": label[:60] or text[:60], "text": text})
        if len(clean) >= 2:
            ledger.extracted_options = clean
            labels = ", ".join(f"{o['id']}={o['label'][:40]}" for o in clean)
            log.log(f"  [OPTION-EXTRACT-R1] Frozen {len(clean)} options: {labels}")
        else:
            log.log("  [OPTION-EXTRACT-R1] After validation < 2 options")
    except Exception as exc:
        log.log(f"  [OPTION-EXTRACT-R1] Failed (non-fatal): {exc}")


# ── Phase 3A: Evidence citation tracking ─────────────────────────────────────

def _track_evidence_citations(round_num, model_outputs, ledger, log):
    """Scan model outputs for evidence ID references (E001, E002...).
    Stores citations on each evidence item and in ledger.evidence_citations_by_round."""
    if not ledger.items:
        return
    citations = {}  # evidence_id -> [model_names]
    evidence_ids = {item["evidence_id"] for item in ledger.items}

    for model_name, text in model_outputs.items():
        if not text:
            continue
        found_ids = set(re.findall(r'\bE\d{3}\b', text))
        for eid in found_ids:
            if eid in evidence_ids:
                citations.setdefault(eid, []).append(model_name)

    ledger.evidence_citations_by_round[round_num] = citations

    # Update cited_by_models on each evidence item
    for item in ledger.items:
        eid = item["evidence_id"]
        if eid in citations:
            for model_name in citations[eid]:
                entry = {"model": model_name, "round": round_num}
                if entry not in item["cited_by_models"]:
                    item["cited_by_models"].append(entry)

    if citations:
        total = sum(len(v) for v in citations.values())
        log.log(f"  [EVIDENCE-CITATIONS] R{round_num}: {total} citation(s) across {len(citations)} item(s)")
    else:
        log.log(f"  [EVIDENCE-CITATIONS] R{round_num}: none")


# ── Phase 3A: Position change tracking ───────────────────────────────────────

def _track_position_changes(round_num, ledger, log):
    """Compare positions between round N and N-1. Track changes with evidence-driven flag.

    evidence_driven requires ALL:
      a. position actually changed
      b. at least one evidence item has first_available_round == round_num
      c. the model cited at least one such new item in round_num
    """
    if round_num <= 1:
        return
    curr_positions = ledger.model_positions_by_round.get(round_num, {})
    prev_positions = ledger.model_positions_by_round.get(round_num - 1, {})
    if not curr_positions or not prev_positions:
        return

    # Evidence items new to this round
    new_evidence_ids = {
        item["evidence_id"] for item in ledger.items
        if item.get("first_available_round") == round_num
    }

    # Citations in this round
    round_citations = ledger.evidence_citations_by_round.get(round_num, {})

    for model in curr_positions:
        if model not in prev_positions:
            continue
        curr = curr_positions[model]
        prev = prev_positions[model]

        changed = (
            curr.get("primary_option") != prev.get("primary_option")
            or curr.get("kind") != prev.get("kind")
            or curr.get("ordering") != prev.get("ordering")
        )
        if not changed:
            continue

        # Check evidence-driven: model must have cited new-to-round evidence
        model_cited_new = False
        if new_evidence_ids:
            for eid, citing_models in round_citations.items():
                if eid in new_evidence_ids and model in citing_models:
                    model_cited_new = True
                    break

        evidence_driven = bool(new_evidence_ids) and model_cited_new

        change = {
            "model": model,
            "from_round": round_num - 1,
            "to_round": round_num,
            "from_position": prev.get("primary_option"),
            "to_position": curr.get("primary_option"),
            "from_kind": prev.get("kind"),
            "to_kind": curr.get("kind"),
            "evidence_driven": evidence_driven,
        }
        ledger.position_changes.append(change)
        log.log(
            f"  [POSITION-CHANGE] R{round_num} {model}: "
            f"{prev.get('primary_option')}({prev.get('kind')}) → "
            f"{curr.get('primary_option')}({curr.get('kind')}) "
            f"evidence_driven={evidence_driven}"
        )


# ── V4: Blocker Lifecycle Ledger ──────────────────────────────────────────
# Reduced disagreement lifecycle adapted from Chamber V10's objection state model.
# Provides durable IDs and typed state trajectories for contested dimensions
# and evidence gaps, without importing Chamber's sequential role pipeline.
#
# Blocker kinds:
#   CONTESTED_POSITION — models disagree on primary option/kind
#   EVIDENCE_GAP       — detected gap not yet resolved by retrieval
#   UNRESOLVED_DRIFT   — position changed without evidence support
#
# Blocker statuses:
#   OPEN     — first detected, not yet resolved
#   RESOLVED — disagreement collapsed or gap filled
#   DEFERRED — gap closed without resolution (e.g., training_only ceiling)
#   DROPPED  — no longer relevant (e.g., model dropped from roster)

def _next_blocker_id(ledger):
    """Generate next durable blocker ID: BLK001, BLK002, ..."""
    ledger.blocker_counter += 1
    return f"BLK{ledger.blocker_counter:03d}"


def _register_blocker(ledger, kind, source_dimension, detected_round,
                       models_involved=None, evidence_ids=None, detail="", log=None):
    """Register a new blocker or return existing if same source_dimension already tracked.

    Returns the blocker_id (new or existing).
    """
    # Dedup: if this exact dimension is already tracked and still OPEN, skip
    existing_id = ledger.blocker_id_map.get(source_dimension)
    if existing_id:
        for blk in ledger.blocker_ledger:
            if blk["blocker_id"] == existing_id and blk["status"] == "OPEN":
                # Update last_seen_round and models_involved
                blk["last_seen_round"] = detected_round
                if models_involved:
                    for m in models_involved:
                        if m not in blk["models_involved"]:
                            blk["models_involved"].append(m)
                return existing_id

    blocker_id = _next_blocker_id(ledger)
    blocker = {
        "blocker_id": blocker_id,
        "kind": kind,
        "source_dimension": source_dimension,
        "detected_round": detected_round,
        "last_seen_round": detected_round,
        "status": "OPEN",
        "status_history": [
            {"status": "OPEN", "round": detected_round, "trigger": "detected"},
        ],
        "models_involved": list(models_involved or []),
        "evidence_ids": list(evidence_ids or []),
        "detail": detail[:200],
        "resolution_note": "",
    }
    ledger.blocker_ledger.append(blocker)
    ledger.blocker_id_map[source_dimension] = blocker_id

    if log:
        log.log(
            f"  [BLOCKER-REGISTERED] {blocker_id} kind={kind} "
            f"dim={source_dimension[:60]} round={detected_round} "
            f"models={models_involved or []}"
        )
    return blocker_id


def _update_blocker_status(ledger, blocker_id, new_status, round_num, trigger="",
                            resolution_note="", log=None):
    """Transition a blocker to a new status. Records history."""
    for blk in ledger.blocker_ledger:
        if blk["blocker_id"] == blocker_id:
            old_status = blk["status"]
            if old_status == new_status:
                return  # no-op
            # Validate transitions
            _legal = {
                "OPEN": {"RESOLVED", "DEFERRED", "DROPPED"},
                "DEFERRED": {"RESOLVED", "OPEN"},  # can reopen if new evidence arrives
            }
            allowed = _legal.get(old_status, set())
            if new_status not in allowed:
                if log:
                    log.log(
                        f"  [BLOCKER-ILLEGAL] {blocker_id}: {old_status}→{new_status} "
                        f"not in legal set {allowed}"
                    )
                return

            blk["status"] = new_status
            blk["status_history"].append({
                "status": new_status,
                "round": round_num,
                "trigger": trigger[:100],
            })
            if resolution_note:
                blk["resolution_note"] = resolution_note[:200]
            if log:
                log.log(
                    f"  [BLOCKER-UPDATE] {blocker_id}: {old_status}→{new_status} "
                    f"round={round_num} trigger={trigger[:60]}"
                )
            return

    if log:
        log.log(f"  [BLOCKER-NOT-FOUND] {blocker_id} — cannot update")


def _detect_blockers_from_positions(round_num, ledger, log):
    """Detect CONTESTED_POSITION blockers from current-round position data.

    Called after _extract_positions_for_round and _track_position_changes.
    Registers new blockers for contested dimensions and resolves blockers
    where previously contested dimensions have converged.
    """
    positions = ledger.model_positions_by_round.get(round_num, {})
    if len(positions) < 2:
        return

    # Group by effective position
    groups = {}
    for model, pos in positions.items():
        key = _effective_position_key(pos)
        groups.setdefault(key, []).append(model)

    total = len(positions)

    # Identify contested dimensions (options not held by all models)
    contested_now = set()
    for opt, models in groups.items():
        if not opt.startswith("__") and len(models) < total:
            contested_now.add(opt)

    # Register new blockers for newly contested dimensions
    for dim in contested_now:
        models_in_dim = groups.get(dim, [])
        models_against = [m for m in positions if m not in models_in_dim]
        _register_blocker(
            ledger,
            kind="CONTESTED_POSITION",
            source_dimension=f"position:{dim}",
            detected_round=round_num,
            models_involved=models_in_dim + models_against,
            detail=f"Models split on {dim}: for={models_in_dim} against={models_against}",
            log=log,
        )

    # Resolve blockers for dimensions that are no longer contested
    for blk in ledger.blocker_ledger:
        if blk["kind"] != "CONTESTED_POSITION" or blk["status"] != "OPEN":
            continue
        dim_key = blk["source_dimension"].replace("position:", "", 1)
        if dim_key not in contested_now:
            # Check if this dimension converged (all models now agree)
            # or disappeared (option no longer present)
            if dim_key in groups and len(groups[dim_key]) == total:
                _update_blocker_status(
                    ledger, blk["blocker_id"], "RESOLVED", round_num,
                    trigger="convergence",
                    resolution_note=f"All {total} models now agree on {dim_key}",
                    log=log,
                )
            elif dim_key not in groups:
                _update_blocker_status(
                    ledger, blk["blocker_id"], "DROPPED", round_num,
                    trigger="option_disappeared",
                    resolution_note=f"Option {dim_key} no longer present in round {round_num}",
                    log=log,
                )


def _detect_blockers_from_gaps(ledger, round_num, log):
    """Register EVIDENCE_GAP blockers from newly detected gaps.

    Called after gap extraction in research gates. Converts gap lifecycle
    records into durable blocker objects with typed states.
    """
    # Find gaps detected in this phase that don't already have blockers
    for gap in ledger.gaps_detected:
        gap_id = gap.get("gap_id", "")
        gap_text = gap.get("text", "")[:120]
        dim_key = f"gap:{gap_id}"

        if dim_key in ledger.blocker_id_map:
            continue  # already tracked

        _register_blocker(
            ledger,
            kind="EVIDENCE_GAP",
            source_dimension=dim_key,
            detected_round=gap.get("round", round_num),
            detail=gap_text,
            log=log,
        )


def _detect_blockers_from_contradictions(ledger, round_num, log):
    """V6 Fix 1+5: Register EVIDENCE_CONTRADICTION blockers from contradiction ledger.
    
    These become governing blockers — they force disagreement floor downgrade
    if unresolved at classification time.
    """
    for ctr in ledger.contradiction_ledger:
        dim_key = f"contradiction:{ctr['contradiction_id']}"
        if dim_key in ledger.blocker_id_map:
            continue
        _register_blocker(
            ledger,
            kind="EVIDENCE_CONTRADICTION",
            source_dimension=dim_key,
            detected_round=ctr.get("detected_round", round_num),
            evidence_ids=ctr.get("evidence_ids", []),
            detail=ctr.get("detail", "")[:200],
            log=log,
        )


def _update_gap_blockers_from_research(ledger, round_num, log):
    """Update EVIDENCE_GAP blocker states after a research phase.

    Gaps that were queried and produced GAP-SPECIFIC evidence → RESOLVED.
    Gaps that were queried but no relevant evidence matched → DEFERRED.
    Gaps that were dropped → DEFERRED (ceiling or slot limit).

    Gap-specificity: evidence must share keyword overlap with the gap's
    query text to count as resolving that specific gap. This prevents
    one unrelated admitted result from marking multiple gaps as resolved.
    """
    queried_gap_ids = {g["gap_id"] for g in ledger.gaps_queried}
    dropped_gap_ids = {g["gap_id"] for g in ledger.gaps_dropped}

    # Build query-text lookup for keyword matching
    gap_query_texts = {}
    for g in ledger.gaps_queried:
        gap_query_texts[g["gap_id"]] = g.get("query_text", "")
    # Also pull gap text from detected gaps
    for g in ledger.gaps_detected:
        if g["gap_id"] not in gap_query_texts:
            gap_query_texts[g["gap_id"]] = g.get("text", "")

    def _gap_evidence_match(gap_id, gap_text):
        """Check if any evidence item admitted after this gap's detection
        shares meaningful keyword overlap with the gap's query/text."""
        if not gap_text:
            return False
        # Extract keywords from gap text (4+ char words, skip stopwords)
        _stop = {"the", "and", "for", "that", "this", "with", "from", "have",
                 "been", "will", "should", "could", "would", "about", "their",
                 "which", "more", "than", "also", "what", "where", "when"}
        gap_kw = {w.lower() for w in re.findall(r'[a-z]{4,}', gap_text.lower())} - _stop
        if not gap_kw:
            return False

        # Find the blocker's detected_round
        detected_round = 0
        for blk in ledger.blocker_ledger:
            if blk["source_dimension"] == f"gap:{gap_id}":
                detected_round = blk["detected_round"]
                break

        for item in ledger.items:
            if item.get("first_available_round", 0) < detected_round:
                continue
            ev_text = f"{item.get('topic', '')} {item.get('fact', '')}".lower()
            ev_kw = {w for w in re.findall(r'[a-z]{4,}', ev_text)} - _stop
            overlap = gap_kw & ev_kw
            if len(overlap) >= 2:
                return True
        return False

    for blk in ledger.blocker_ledger:
        if blk["kind"] != "EVIDENCE_GAP" or blk["status"] != "OPEN":
            continue
        gap_id = blk["source_dimension"].replace("gap:", "", 1)

        if gap_id in queried_gap_ids:
            gap_text = gap_query_texts.get(gap_id, "")
            if _gap_evidence_match(gap_id, gap_text):
                _update_blocker_status(
                    ledger, blk["blocker_id"], "RESOLVED", round_num,
                    trigger="gap_specific_evidence_matched",
                    resolution_note=f"Gap {gap_id} researched, gap-specific evidence found",
                    log=log,
                )
            else:
                _update_blocker_status(
                    ledger, blk["blocker_id"], "DEFERRED", round_num,
                    trigger="queried_no_matching_evidence",
                    resolution_note=f"Gap {gap_id} queried but no gap-specific evidence matched",
                    log=log,
                )
        elif gap_id in dropped_gap_ids:
            drop_reason = next(
                (g.get("reason", "") for g in ledger.gaps_dropped if g["gap_id"] == gap_id),
                "unknown"
            )
            _update_blocker_status(
                ledger, blk["blocker_id"], "DEFERRED", round_num,
                trigger=f"gap_dropped:{drop_reason}",
                resolution_note=f"Gap {gap_id} dropped: {drop_reason}",
                log=log,
            )


def _detect_drift_diagnostics(round_num, ledger, log):
    """Log UNRESOLVED_DRIFT as diagnostic annotations, NOT lifecycle blockers.

    Position changes without evidence support are important signals, but they
    do not have a natural resolution path in Brain's parallel topology (no
    Strategist to patch, no Auditor to adjudicate). Recording them as full
    lifecycle blockers creates objects that can only be deferred at run end,
    which is not a meaningful lifecycle. Instead, they are recorded as
    diagnostic entries on the blocker ledger with status=DIAGNOSTIC.
    """
    for change in ledger.position_changes:
        if change.get("to_round") != round_num:
            continue
        if change.get("evidence_driven"):
            continue  # evidence-driven changes are healthy

        model = change.get("model", "?")
        from_pos = change.get("from_position", "?")
        to_pos = change.get("to_position", "?")
        dim_key = f"drift:{model}:R{round_num}"

        if dim_key in ledger.blocker_id_map:
            continue  # already recorded

        blocker_id = _next_blocker_id(ledger)
        blocker = {
            "blocker_id": blocker_id,
            "kind": "UNRESOLVED_DRIFT",
            "source_dimension": dim_key,
            "detected_round": round_num,
            "last_seen_round": round_num,
            "status": "DIAGNOSTIC",
            "status_history": [
                {"status": "DIAGNOSTIC", "round": round_num,
                 "trigger": "non_evidence_driven_change"},
            ],
            "models_involved": [model],
            "evidence_ids": [],
            "detail": f"{model} changed {from_pos}→{to_pos} without citing new evidence"[:200],
            "resolution_note": "Diagnostic only — no lifecycle resolution path in parallel topology",
        }
        ledger.blocker_ledger.append(blocker)
        ledger.blocker_id_map[dim_key] = blocker_id

        if log:
            log.log(
                f"  [DRIFT-DIAGNOSTIC] {blocker_id} {model}: "
                f"{from_pos}→{to_pos} (no evidence support)"
            )


def _close_stale_blockers(ledger, final_round, log):
    """Close any OPEN blockers at end of run by deferring them.

    Called before outcome classification. Ensures no lifecycle blocker falls out
    without a terminal state. DIAGNOSTIC entries are already terminal and skipped.
    """
    for blk in ledger.blocker_ledger:
        if blk["status"] == "OPEN":
            _update_blocker_status(
                ledger, blk["blocker_id"], "DEFERRED", final_round,
                trigger="run_end_close",
                resolution_note="Blocker still open at run end — deferred",
                log=log,
            )


def _compute_blocker_summary(ledger):
    """Compute summary statistics for proof.json."""
    total = len(ledger.blocker_ledger)
    by_status = {}
    by_kind = {}
    for blk in ledger.blocker_ledger:
        by_status[blk["status"]] = by_status.get(blk["status"], 0) + 1
        by_kind[blk["kind"]] = by_kind.get(blk["kind"], 0) + 1

    # Lifecycle blockers exclude DIAGNOSTIC entries
    lifecycle_total = sum(1 for blk in ledger.blocker_ledger if blk["status"] != "DIAGNOSTIC")

    return {
        "total_blockers": total,
        "lifecycle_blockers": lifecycle_total,
        "diagnostic_entries": by_status.get("DIAGNOSTIC", 0),
        "by_status": by_status,
        "by_kind": by_kind,
        "open_at_end": by_status.get("OPEN", 0),
        "resolved": by_status.get("RESOLVED", 0),
        "deferred": by_status.get("DEFERRED", 0),
        "dropped": by_status.get("DROPPED", 0),
    }


# ── Phase 3A: Derived deliberation fields ────────────────────────────────────

def _effective_position_key(pos):
    """Compute a grouping key for a position record.

    Grouping rules (from locked architecture):
      - single: group by primary_option
      - sequence: same components + same ordering = agreement
      - hybrid: same components (any order) = agreement
      - abstain/none/other: each is its own group, never agrees with anything
    """
    kind = pos.get("kind", "none")
    if kind in ("abstain", "none", "other"):
        # Each abstain/none/other is unique — use model name to prevent grouping
        return f"__{kind}_{pos.get('model', 'x')}__"
    elif kind == "sequence":
        ordering = tuple(pos.get("ordering", []))
        return f"seq:{','.join(ordering)}" if ordering else f"seq:{pos.get('primary_option', '?')}"
    elif kind == "hybrid":
        components = tuple(sorted(pos.get("components", [])))
        return f"hyb:{','.join(components)}" if components else f"hyb:{pos.get('primary_option', '?')}"
    else:  # single
        return pos.get("primary_option") or "__none__"


def _compute_deliberation_derived(last_round, ledger, log):
    """Compute stable_agreements, stable_contested, evolved_positions,
    unresolved_residual, convergence_trend from position data."""

    final_positions = ledger.model_positions_by_round.get(last_round, {})
    if not final_positions:
        return {}, [], [], [], [], "unknown", 0.0

    # Group by effective position (full semantics, not just primary_option)
    groups = {}
    for model, pos in final_positions.items():
        key = _effective_position_key(pos)
        groups.setdefault(key, []).append(model)

    total = len(final_positions)
    # Denominator includes abstain/none (binding rule D7)
    largest_group = max(groups.values(), key=len) if groups else []
    largest_option = None
    for opt, models in groups.items():
        if models == largest_group:
            largest_option = opt
            break

    agreement_ratio = len(largest_group) / total if total > 0 else 0.0

    # Majority option (binding rule D10: no confidence tiebreaker)
    majority_option = None
    if agreement_ratio > 0.5:
        # Check for ties
        sizes = sorted([len(v) for v in groups.values()], reverse=True)
        if len(sizes) < 2 or sizes[0] > sizes[1]:
            majority_option = largest_option if largest_option.startswith("__") else largest_option

    # Stable agreements: options where ALL final-round models agree
    stable_agreements = []
    if agreement_ratio == 1.0 and largest_option and not largest_option.startswith("__"):
        stable_agreements.append(largest_option)

    # Even when effective keys differ, extract shared sub-conclusions:
    # options that appear in ALL final-round models' components
    if agreement_ratio < 1.0:
        all_components = []
        for model, pos in final_positions.items():
            comps = set(pos.get("components", []))
            if pos.get("primary_option"):
                comps.add(pos["primary_option"])
            all_components.append(comps)
        if all_components:
            shared_options = all_components[0]
            for comps in all_components[1:]:
                shared_options = shared_options & comps
            for opt in sorted(shared_options):
                if opt and not opt.startswith("__"):
                    stable_agreements.append(f"shared:{opt}")

    # Stable contested: options where final-round models disagree
    stable_contested = []
    if agreement_ratio < 1.0:
        for opt, models in groups.items():
            if not opt.startswith("__") and len(models) < total:
                stable_contested.append(opt)

    # Evolved positions
    evolved_positions = [
        c for c in ledger.position_changes
        if c["from_position"] != c["to_position"]
    ]

    # Unresolved residual: contested in last two rounds
    prev_positions = ledger.model_positions_by_round.get(last_round - 1, {})
    unresolved = []
    if prev_positions and stable_contested:
        prev_groups = {}
        for model, pos in prev_positions.items():
            key = _effective_position_key(pos)
            prev_groups.setdefault(key, []).append(model)
        prev_contested = {opt for opt, models in prev_groups.items()
                         if not opt.startswith("__") and len(models) < len(prev_positions)}
        unresolved = [opt for opt in stable_contested if opt in prev_contested]

    # Convergence trend
    # Compare agreement ratios across rounds
    round_agreements = []
    for rnd in sorted(ledger.model_positions_by_round.keys()):
        rnd_pos = ledger.model_positions_by_round[rnd]
        if len(rnd_pos) < 2:
            continue
        rnd_groups = {}
        for model, pos in rnd_pos.items():
            key = _effective_position_key(pos)
            rnd_groups.setdefault(key, []).append(model)
        rnd_largest = max(len(v) for v in rnd_groups.values())
        rnd_ratio = rnd_largest / len(rnd_pos)
        round_agreements.append(rnd_ratio)

    if len(round_agreements) >= 2:
        if round_agreements[-1] > round_agreements[0]:
            convergence_trend = "improving"
        elif round_agreements[-1] < round_agreements[0]:
            convergence_trend = "degrading"
        else:
            convergence_trend = "stable"
    else:
        convergence_trend = "stable"

    log.log(f"  [DELIBERATION-DERIVED] agreement_ratio={agreement_ratio:.2f} "
            f"majority={majority_option} convergence={convergence_trend}")
    if stable_agreements:
        log.log(f"  [DELIBERATION-DERIVED] stable_agreements={stable_agreements}")
    if stable_contested:
        log.log(f"  [DELIBERATION-DERIVED] stable_contested={stable_contested}")
    if evolved_positions:
        log.log(f"  [DELIBERATION-DERIVED] evolved_positions={len(evolved_positions)}")
    if unresolved:
        log.log(f"  [DELIBERATION-DERIVED] unresolved_residual={unresolved}")

    return (groups, stable_agreements, stable_contested, evolved_positions,
            unresolved, convergence_trend, agreement_ratio)


# ── Phase 3B: Controller outcome classification ──────────────────────────────

# ── V6 Fix 5: Governing blockers — selective gating ──────────────────────────
# Two classes of blockers:
#   diagnostic: recorded, informative, no automatic gating
#   governing: force downgrade, extra round, or explicit unresolved status
#
# Governing blocker criteria (exactly three types):
#   1. Unresolved contradiction on controlling claim (EVIDENCE_CONTRADICTION)
#   2. Ungrounded number still present in final controlling rationale
#   3. Evidence gap on a must-verify claim (EVIDENCE_GAP with HIGH severity)

def _get_governing_blockers(ledger):
    """Return list of blockers that should force status downgrade.
    
    Only returns blockers that are OPEN or DEFERRED (not RESOLVED/DROPPED)
    and match one of the three governing criteria.
    """
    governing = []
    for blk in ledger.blocker_ledger:
        if blk["status"] in ("RESOLVED", "DROPPED", "DIAGNOSTIC"):
            continue
        # Type 1: Evidence contradiction blocker
        if blk["kind"] == "EVIDENCE_CONTRADICTION":
            governing.append(blk)
            continue
        # Type 2: Evidence gap with controlling claim
        if blk["kind"] == "EVIDENCE_GAP" and blk["status"] in ("OPEN", "DEFERRED"):
            governing.append(blk)
            continue
        # Type 3: Contested position still unresolved at final round
        if blk["kind"] == "CONTESTED_POSITION" and blk["status"] == "OPEN":
            governing.append(blk)
            continue
    return governing


# ── V6 Fix 3: Minority argument carry-forward ────────────────────────────────

def _build_minority_archive(round_num, dropped_models, ledger, outdir, log):
    """Preserve minority arguments from models being dropped.
    
    Called at each model reduction step (R1→R2: kimi drops, R2→R3: glm5 drops).
    Extracts the minority model's position, primary argument, and evidence citations,
    then stores in ledger.minority_archive for injection into future round prompts.
    """
    positions = ledger.model_positions_by_round.get(round_num, {})
    if not positions:
        return

    # Determine majority position
    groups = {}
    for model, pos in positions.items():
        key = _effective_position_key(pos)
        groups.setdefault(key, []).append(model)
    majority_key = max(groups, key=lambda k: len(groups[k])) if groups else None

    for model in dropped_models:
        pos = positions.get(model)
        if not pos:
            continue
        model_key = _effective_position_key(pos)
        # Only archive if this model held a MINORITY position
        if model_key == majority_key:
            continue
        if model_key.startswith("__"):  # abstain/none
            continue

        # Extract argument summary from model output
        output_path = outdir / f"r{round_num}-{model}.txt"
        argument_summary = ""
        evidence_cited = []
        if output_path.exists():
            text = output_path.read_text(errors="replace")
            # Extract conclusion section
            concl_m = re.search(
                r'\[CONCLUSION\]\s*(.+?)(?=\[(?:CONFIDENCE|KEY ARGUMENTS)|$)',
                text, re.DOTALL | re.IGNORECASE,
            )
            if concl_m:
                argument_summary = concl_m.group(1).strip()[:400]
            else:
                argument_summary = text[:400]
            evidence_cited = re.findall(r'\bE\d{3}\b', text)

        archive_entry = {
            "round_dropped": round_num,
            "model": model,
            "position": pos.get("primary_option", "?"),
            "position_kind": pos.get("kind", "?"),
            "argument_summary": argument_summary,
            "evidence_cited": sorted(set(evidence_cited))[:10],
            "addressed_by": None,  # filled when a later-round model explicitly addresses it
        }
        ledger.minority_archive.append(archive_entry)
        log.log(
            f"  [MINORITY-ARCHIVED] {model} R{round_num}: position={pos.get('primary_option')} "
            f"kind={pos.get('kind')} argument={argument_summary[:80]}..."
        )


def _classify_outcome(last_round, ledger, log):
    """Controller outcome classification. Returns structured outcome dict.

    Classification rules (from locked architecture):
      CONSENSUS: agreement_ratio == 1.0
      PARTIAL_CONSENSUS: agreement_ratio >= 0.5 or 2-model split
      NO_CONSENSUS: no majority + empty stable_agreements + high-confidence incompatible
    """
    (groups, stable_agreements, stable_contested, evolved_positions,
     unresolved, convergence_trend, agreement_ratio) = _compute_deliberation_derived(
        last_round, ledger, log
    )

    final_positions = ledger.model_positions_by_round.get(last_round, {})
    if not final_positions:
        return {
            "outcome_class": "UNKNOWN",
            "agreement_ratio": 0.0,
            "majority_option": None,
            "consensus_strength": None,
            "shared_ground": [],
            "contested_dimension": None,
            "position_trajectory": "unknown",
            "evidence_driven_convergence": False,
            "residual_risk_flag": False,
            "method": "controller_v1",
            "extraction_methods_used": [],
        }

    total = len(final_positions)

    # Majority option (binding D10: no confidence tiebreaker)
    sizes = sorted([len(v) for v in groups.values()], reverse=True)
    majority_option = None
    if agreement_ratio > 0.5 and (len(sizes) < 2 or sizes[0] > sizes[1]):
        for opt, models in groups.items():
            if len(models) == sizes[0] and not opt.startswith("__"):
                majority_option = opt
                break

    # Position trajectory
    if convergence_trend == "improving":
        trajectory = "convergent"
    elif convergence_trend == "degrading":
        trajectory = "divergent"
    else:
        trajectory = "stable"

    # Evidence-driven convergence
    evidence_driven_changes = [c for c in ledger.position_changes if c["evidence_driven"]]
    evidence_driven_convergence = bool(evidence_driven_changes)

    # Extraction methods used
    methods = set()
    for rnd_positions in ledger.model_positions_by_round.values():
        for pos in rnd_positions.values():
            methods.add(pos.get("extraction_method", "unknown"))

    # Classify
    if agreement_ratio == 1.0:
        outcome_class = "CONSENSUS"
        if evidence_driven_convergence:
            consensus_strength = "evidence-driven"
        elif evolved_positions:
            consensus_strength = "strong"
        else:
            consensus_strength = "default"
        shared_ground = stable_agreements
        contested_dimension = None
        residual_risk_flag = bool(unresolved)

    elif agreement_ratio < 1.0:
        # Check: do all models share the same primary_option?
        # If yes, the split is subordinate staging (sequence length, hybrid components)
        # not a primary recommendation disagreement → upgrade to CONSENSUS
        primary_options = {
            pos.get("primary_option") for pos in final_positions.values()
            if pos.get("primary_option") and pos.get("kind") not in ("abstain", "none", "other")
        }
        # All models must have a primary option AND they must all be the same
        models_with_primary = sum(
            1 for pos in final_positions.values()
            if pos.get("primary_option") and pos.get("kind") not in ("abstain", "none", "other")
        )
        all_same_primary = (
            len(primary_options) == 1
            and models_with_primary == len(final_positions)
        )

        if all_same_primary:
            # All models recommend the same primary action — subordinate staging differs
            outcome_class = "CONSENSUS"
            if evidence_driven_convergence:
                consensus_strength = "evidence-driven"
            elif evolved_positions:
                consensus_strength = "strong"
            else:
                consensus_strength = "default"
            shared_ground = stable_agreements
            # Note the subordinate difference
            if len(groups) > 1:
                contested_dimension = "subordinate_staging"
            else:
                contested_dimension = None
            residual_risk_flag = bool(unresolved)

        else:
            # Genuine primary-option disagreement
            # Check for NO_CONSENSUS escape (binding D6):
            # 2-model split, both HIGH confidence, empty stable_agreements
            is_no_consensus = False
            if total == 2 and agreement_ratio < 1.0:
                all_high = all(
                    pos.get("confidence", "").upper() == "HIGH"
                    for pos in final_positions.values()
                )
                disjoint = len(groups) >= 2 and not any(k.startswith("__") for k in groups)
                if all_high and disjoint and not stable_agreements:
                    is_no_consensus = True

            if is_no_consensus:
                outcome_class = "NO_CONSENSUS"
                consensus_strength = None
                shared_ground = []
                contested_dimension = ", ".join(stable_contested) if stable_contested else "all dimensions"
                residual_risk_flag = False
            else:
                outcome_class = "PARTIAL_CONSENSUS"
                consensus_strength = None
                shared_ground = stable_agreements
                contested_dimension = ", ".join(stable_contested) if stable_contested else None
                residual_risk_flag = False
    else:
        outcome_class = "NO_CONSENSUS"
        consensus_strength = None
        shared_ground = []
        contested_dimension = ", ".join(stable_contested) if stable_contested else "all dimensions"
        residual_risk_flag = False

    result = {
        "outcome_class": outcome_class,
        "agreement_ratio": round(agreement_ratio, 2),
        "majority_option": majority_option,
        "consensus_strength": consensus_strength,
        "shared_ground": shared_ground,
        "contested_dimension": contested_dimension,
        "position_trajectory": trajectory,
        "evidence_driven_convergence": evidence_driven_convergence,
        "residual_risk_flag": residual_risk_flag,
        "method": "controller_v1",
        "extraction_methods_used": sorted(methods),
        "disagreement_floor_applied": False,
        "governing_blocker_downgrade": False,
    }

    # V6 Fix 2: Disagreement floor — prevent CONSENSUS when high-severity residue remains
    # Three types of residue that force downgrade:
    #   (a) unresolved evidence contradiction on any topic
    #   (b) active minority packet not addressed
    #   (c) unresolved governing blocker (see Fix 5)
    if outcome_class == "CONSENSUS":
        floor_reasons = []

        # (a) Unresolved evidence contradictions
        unresolved_ctrs = [c for c in ledger.contradiction_ledger if c["status"] == "UNRESOLVED"]
        high_ctrs = [c for c in unresolved_ctrs if c.get("severity") == "HIGH"]
        if high_ctrs:
            floor_reasons.append(f"{len(high_ctrs)} HIGH unresolved contradiction(s)")

        # (b) Unaddressed minority carry-forward packets
        unaddressed_minorities = [m for m in ledger.minority_archive if not m.get("addressed_by")]
        if unaddressed_minorities:
            floor_reasons.append(f"{len(unaddressed_minorities)} unaddressed minority argument(s)")

        # (c) Governing blockers still OPEN or DEFERRED on controlling dimensions
        governing_blockers = _get_governing_blockers(ledger)
        if governing_blockers:
            floor_reasons.append(f"{len(governing_blockers)} governing blocker(s)")

        if floor_reasons:
            result["outcome_class"] = "PARTIAL_CONSENSUS"
            result["consensus_strength"] = "downgraded"
            result["disagreement_floor_applied"] = True
            result["disagreement_floor_reasons"] = floor_reasons
            log.log(
                f"  [DISAGREEMENT-FLOOR] CONSENSUS → PARTIAL_CONSENSUS — "
                f"reasons: {'; '.join(floor_reasons)}"
            )

    # V6 Fix 5: Governing blocker downgrade — even PARTIAL_CONSENSUS gets flagged
    if outcome_class in ("CONSENSUS", "PARTIAL_CONSENSUS"):
        governing = _get_governing_blockers(ledger)
        if governing:
            result["governing_blocker_downgrade"] = True
            result["residual_risk_flag"] = True
            result["governing_blockers"] = [
                {"blocker_id": b["blocker_id"], "kind": b["kind"],
                 "dimension": b["source_dimension"][:60]}
                for b in governing
            ]
            log.log(
                f"  [GOVERNING-BLOCKERS] {len(governing)} governing blocker(s) remain: "
                f"{[b['blocker_id'] for b in governing]}"
            )

    log.log(f"  [CONTROLLER-OUTCOME] class={outcome_class} agreement={agreement_ratio:.2f} "
            f"majority={majority_option} strength={consensus_strength} trajectory={trajectory}")

    return result


def _shadow_compare_outcome(controller_outcome, proof, log):
    """Phase 3B: Compare controller outcome vs synthesis stage outcome.
    Stores structured shadow_outcome comparison in proof."""
    synthesis_outcome = proof.get("v3_outcome_class", "not applicable")
    controller_class = controller_outcome.get("outcome_class", "UNKNOWN")

    agreement = (controller_class == synthesis_outcome)
    log.log(
        f"  [OUTCOME-SHADOW] controller={controller_class} "
        f"synthesis={synthesis_outcome} agreement={agreement}"
    )
    if not agreement:
        log.log(f"  [OUTCOME-SHADOW] MISMATCH — controller inputs: "
                f"ratio={controller_outcome.get('agreement_ratio')} "
                f"trajectory={controller_outcome.get('position_trajectory')} "
                f"shared_ground={controller_outcome.get('shared_ground')} "
                f"methods={controller_outcome.get('extraction_methods_used')}")

    proof["shadow_outcome"] = {
        "controller": controller_class,
        "synthesis": synthesis_outcome,
        "agreement": agreement,
    }

    return agreement


# ── Phase 3A: Evidence citation density ──────────────────────────────────────

def _compute_citation_density(ledger):
    """Compute evidence_citation_density_by_round."""
    density = {}
    for rnd, citations in ledger.evidence_citations_by_round.items():
        available = [
            item for item in ledger.items
            if item.get("first_available_round", 0) <= rnd
        ]
        if available:
            cited_ids = set(citations.keys())
            available_ids = {item["evidence_id"] for item in available}
            density[rnd] = round(len(cited_ids & available_ids) / len(available_ids), 2)
        else:
            density[rnd] = 0.0
    return density


# ── Phase 1 Roadmap: Run invariant validator ─────────────────────────────────

def _validate_run_invariants(proof, ledger, log):
    """End-of-run invariant checks. Returns list of violation dicts.

    Severity levels:
      FATAL  — must fail the run / block artifact emission
      ERROR  — run completed but cannot be considered clean
      WARNING — logged for review only

    Each violation: {id, severity, detail}
    """
    violations = []

    def _v(inv_id, severity, detail):
        violations.append({"id": inv_id, "severity": severity, "detail": detail})
        log.log(f"  [INVARIANT-VIOLATION] {inv_id} ({severity}): {detail}")

    # ── Search / Retrieval invariants ──
    # S1: If retrieval attempted, at least one engine must be recorded
    if ledger.search_diag_live_retrieval_attempted:
        engines = [ph["method"] for ph in ledger.research_phases]
        if not engines:
            _v("S1", "ERROR", "live_retrieval_ever_attempted=True but no research phase recorded (even with 0 admits)")

    # S2: If mode changed, escalation metadata must exist
    if proof.get("final_search_mode") != proof.get("initial_search_mode"):
        has_escalation = any(d["decision_type"] == "search_escalation" for d in ledger.decisions)
        if not has_escalation and not ledger.search_mode_escalated:
            _v("S2", "ERROR", f"search mode changed {proof.get('initial_search_mode')}→{proof.get('final_search_mode')} but no escalation metadata")

    # S3: If evidence admitted, retrieval must have been attempted
    if len(ledger.items) > 0 and not ledger.search_diag_live_retrieval_attempted:
        _v("S3", "FATAL", f"evidence_items={len(ledger.items)} but live_retrieval_ever_attempted=False")

    # S4: Detected gaps not queried must appear in gaps_dropped
    detected_ids = {g["gap_id"] for g in ledger.gaps_detected}
    queried_ids = {g["gap_id"] for g in ledger.gaps_queried}
    dropped_ids = {g["gap_id"] for g in ledger.gaps_dropped}
    untracked = detected_ids - queried_ids - dropped_ids
    if untracked:
        _v("S4", "WARNING", f"gaps detected but neither queried nor dropped: {sorted(untracked)}")

    # ── Evidence invariants ──
    # E1: Every evidence item must have source, evidence_id, and a non-empty fact
    for item in ledger.items:
        missing_fields = []
        if not item.get("evidence_id"):
            missing_fields.append("evidence_id")
        if not item.get("topic"):
            missing_fields.append("topic")
        if not item.get("fact"):
            missing_fields.append("fact")
        if missing_fields:
            _v("E1", "ERROR", f"evidence item missing {missing_fields}: id={item.get('evidence_id', '?')}")

    # E3: No item both rejected and admitted (structural — checked by ledger.admit())

    # ── Confidence invariants ──
    # C1: Only one confidence adjustor in active path (structural — enforced by dead code removal)
    # C3: No stale-state penalties
    if proof.get("v3_confidence_adjustment", "not applicable") != "not applicable":
        adj_str = proof["v3_confidence_adjustment"]
        if "training_only_unresolved_gaps" in adj_str and ledger.search_diag_live_retrieval_attempted:
            _v("C3", "ERROR", "training_only_unresolved_gaps penalty applied despite successful retrieval")

    # ── Artifact invariants ──
    # A1: proof internal consistency — final_search_mode must match search_mode
    _proof_sm = proof.get("search_mode", "")
    _proof_fsm = proof.get("final_search_mode", "")
    if _proof_fsm and _proof_sm and _proof_fsm != _proof_sm:
        # search_mode is the initial value; final_search_mode is the post-escalation value
        # They can differ, but only if escalation is recorded
        if not proof.get("search_mode_escalated"):
            _v("A1", "ERROR", f"final_search_mode={_proof_fsm} != search_mode={_proof_sm} but search_mode_escalated=False")

    # A2: proof outcome vs report frontmatter
    if proof.get("synthesis_report_path") and proof.get("synthesis_status") == "COMPLETE":
        try:
            rpt = Path(proof["synthesis_report_path"]).read_text(encoding="utf-8")[:800]
            fm_m = re.search(r'^outcome:\s*(\S+)', rpt, re.MULTILINE)
            if fm_m:
                synthesis_fm_outcome = fm_m.group(1).strip()
                proof_outcome = proof.get("v3_outcome_class", "not applicable")
                if proof_outcome != "not applicable" and synthesis_fm_outcome != proof_outcome:
                    _v("A2", "ERROR", f"proof v3_outcome_class={proof_outcome} vs synthesis outcome={synthesis_fm_outcome}")
        except Exception:
            pass

    # A3: evidence count consistency
    admitted_in_log = len(ledger.items)
    admitted_in_proof = proof.get("evidence_items", 0)
    if admitted_in_log != admitted_in_proof:
        _v("A3", "ERROR", f"ledger has {admitted_in_log} items but proof says {admitted_in_proof}")

    # ── Execution invariants ──
    # X1: fallbacks must be recorded in execution_events
    mp = proof.get("model_provenance", {})
    if mp:
        for slot, actual in mp.items():
            found = any(
                e.get("type") == "fallback" and slot in e.get("detail", "")
                for e in ledger.execution_events
            )
            if not found:
                _v("X1", "ERROR", f"fallback {slot}→{actual} in model_provenance but not in execution_events")

    # X2: skipped steps must have reasons
    for evt in ledger.execution_events:
        if evt.get("type") in ("timeout", "failure") and not evt.get("detail"):
            _v("X2", "ERROR", f"execution event type={evt['type']} stage={evt.get('stage')} has no detail")

    # X3: degraded mode flag
    has_degradation = any(
        e.get("type") in ("timeout", "failure", "degraded_success", "fallback")
        for e in ledger.execution_events
    )
    if has_degradation and not any(e.get("type") == "degraded_success" for e in ledger.execution_events):
        # Failures/timeouts without degraded_success means models failed completely
        # This is informational — the round failure handlers already deal with it
        pass

    # ── Synthesis invariants (Phase 3C) ──
    # Y1: Synthesis stage frontmatter outcome must not contradict controller
    _ctrl_outcome = proof.get("controller_outcome", {}).get("outcome_class")
    _synth_fm = proof.get("shadow_outcome", {}).get("synthesis")
    if _ctrl_outcome and _synth_fm and _ctrl_outcome != _synth_fm:
        if proof.get("synthesis_override_present"):
            _v("Y1", "WARNING",
               f"controller={_ctrl_outcome} vs synthesis={_synth_fm} "
               f"(override section present — narrated dissent)")
        else:
            _v("Y1", "WARNING",
               f"controller={_ctrl_outcome} vs synthesis={_synth_fm} "
               f"(no override section)")

    # ── Transition invariants (Phase 4) ──
    # T1: Every state transition must be in the legal transition table
    _legal_transitions = {
        ("INIT", "CLASSIFYING"), ("CLASSIFYING", "ROUND_RUNNING"),
        ("ROUND_RUNNING", "ROUND_COMPLETE"), ("ROUND_RUNNING", "FAILED"),
        ("ROUND_COMPLETE", "RESEARCH_GATE"), ("ROUND_COMPLETE", "PRE_SYNTHESIS"),
        ("RESEARCH_GATE", "RESEARCHING"), ("RESEARCH_GATE", "ROUND_RUNNING"),
        ("RESEARCHING", "COOLDOWN"), ("COOLDOWN", "ROUND_RUNNING"),
        ("PRE_SYNTHESIS", "SYNTHESIZING"), ("SYNTHESIZING", "POST_SYNTHESIS"),
        ("SYNTHESIZING", "FAILED"), ("POST_SYNTHESIS", "VALIDATING"),
        ("VALIDATING", "COMPLETE"), ("VALIDATING", "FAILED"),
    }
    for t in ledger.state_transitions:
        pair = (t.get("from_state"), t.get("to_state"))
        if pair not in _legal_transitions:
            _v("T1", "ERROR", f"illegal transition: {pair[0]}→{pair[1]} trigger={t.get('trigger')}")

    # ── Blocker lifecycle invariants (V4) ──
    # BLK1: No lifecycle blocker should remain OPEN at run end
    # (_close_stale_blockers should have deferred them — if any survive, lifecycle logic failed)
    open_blockers = [b for b in ledger.blocker_ledger
                     if b["status"] == "OPEN" and b["kind"] != "UNRESOLVED_DRIFT"]
    if open_blockers:
        _v("BLK1", "ERROR",
           f"{len(open_blockers)} lifecycle blocker(s) still OPEN at run end "
           f"(close_stale_blockers should have deferred these): "
           f"{[b['blocker_id'] for b in open_blockers]}")

    # BLK2: Every blocker must have at least one status_history entry
    for blk in ledger.blocker_ledger:
        if not blk.get("status_history"):
            _v("BLK2", "ERROR",
               f"blocker {blk['blocker_id']} has empty status_history")

    # BLK3: Blocker summary must be consistent with blocker ledger
    _blk_summary = proof.get("blocker_summary", {})
    if _blk_summary:
        expected_total = len(ledger.blocker_ledger)
        reported_total = _blk_summary.get("total_blockers", -1)
        if reported_total != expected_total:
            _v("BLK3", "ERROR",
               f"blocker_summary.total_blockers={reported_total} but "
               f"blocker_ledger has {expected_total} entries")
        # Verify status counts match
        actual_by_status = {}
        for blk in ledger.blocker_ledger:
            actual_by_status[blk["status"]] = actual_by_status.get(blk["status"], 0) + 1
        reported_by_status = _blk_summary.get("by_status", {})
        if actual_by_status != reported_by_status:
            _v("BLK3", "ERROR",
               f"blocker_summary.by_status={reported_by_status} does not match "
               f"actual={actual_by_status}")

    # Summary
    if violations:
        fatal_count = sum(1 for v in violations if v["severity"] == "FATAL")
        error_count = sum(1 for v in violations if v["severity"] == "ERROR")
        warn_count = sum(1 for v in violations if v["severity"] == "WARNING")
        log.log(f"  [INVARIANT-SUMMARY] {len(violations)} violation(s): {fatal_count} FATAL, {error_count} ERROR, {warn_count} WARNING")
    else:
        log.log(f"  [INVARIANT-SUMMARY] 0 violations — run is clean")

    return violations


# ── V3 Fix 5: Post-synthesis confidence adjustment (canonical) ───────────────

def _adjust_synthesis_confidence(report_path, ledger, last_round, log,
                                  outcome_override=None):
    """Canonical confidence adjustor. All penalty rules live here.

    Returns a dict with adjustment details for proof.json, or None if skipped.
    
    Phase 3C: outcome_override allows controller to provide the canonical outcome
    class instead of reading from synthesis frontmatter.
    
    Penalty rules (applied in order):
      1. Ungrounded statistics across all rounds
      2. training_only with unresolved evidence gaps
      3. Options dropped in final round
      4. Major drift in final round (with evidence-aware suppression)
      5. Noisy research (cross-domain rejections)
      6. Split outcome (PARTIAL_CONSENSUS / NO_CONSENSUS)
    """
    try:
        text = report_path.read_text(encoding="utf-8")
    except Exception:
        return None
    fm_match = re.search(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not fm_match:
        log.log("  [CONFIDENCE-ADJ] No YAML frontmatter — skipping")
        return None
    frontmatter = fm_match.group(1)
    conf_match = re.search(r'^confidence:\s*(\S+)', frontmatter, re.MULTILINE)
    if not conf_match:
        log.log("  [CONFIDENCE-ADJ] No confidence field — skipping")
        return None
    raw_str = conf_match.group(1).strip()
    conf_map = {"high": 0.85, "medium": 0.65, "low": 0.40}
    raw_conf = conf_map.get(raw_str)
    if raw_conf is None:
        try:
            raw_conf = float(raw_str)
        except ValueError:
            log.log(f"  [CONFIDENCE-ADJ] Unrecognized: {raw_str}")
            return None

    # Phase 3C: Use controller outcome if provided, otherwise fall back to frontmatter
    if outcome_override:
        _outcome = outcome_override
        _is_split = _outcome in ("PARTIAL_CONSENSUS", "NO_CONSENSUS")
    else:
        _outcome_m = re.search(r'^outcome:\s*(\S+)', frontmatter, re.MULTILINE)
        _consensus_m = re.search(r'^consensus_level:\s*(\S+)', frontmatter, re.MULTILINE)
        _outcome = _outcome_m.group(1).strip() if _outcome_m else ""
        _consensus = _consensus_m.group(1).strip() if _consensus_m else ""
        _is_split = _outcome in ("PARTIAL_CONSENSUS", "NO_CONSENSUS") or _consensus in ("split", "none")

    penalties = []
    penalty_sum = 0.0

    # Penalty 1: ungrounded stats
    total_ug = sum(len(v) for v in ledger.ungrounded_stats_by_round.values())
    if total_ug > 0:
        p = min(total_ug * 0.02, 0.10)
        penalty_sum += p
        penalties.append(f"ungrounded={total_ug}x0.02={p:.2f}")

    # Penalty 2: training_only with unresolved gaps (only if never retrieved)
    _ended_to = ledger.search_mode == "training_only"
    _had_gaps = ledger.search_diag_live_evidence_candidates > 0
    _never_ret = not ledger.search_diag_live_retrieval_attempted
    if _ended_to and _had_gaps and _never_ret:
        penalty_sum += 0.03
        penalties.append("training_only_unresolved_gaps=0.03")

    # Penalty 3: options dropped in final round
    final_drops = ledger.option_drops_by_round.get(last_round, [])
    if final_drops:
        p = len(final_drops) * 0.05
        penalty_sum += p
        penalties.append(f"opts_dropped={len(final_drops)}x0.05={p:.2f}")

    # Penalty 4: major drift in final round (evidence-aware suppression)
    # Suppression requires ALL of:
    #   a. Evidence was injected immediately before the drifting round
    #   b. Final outcome is convergent (not split)
    #   c. Final round has zero ungrounded stats
    # If any condition fails, full 0.05 penalty applies.
    final_fps = ledger.position_fingerprints.get(last_round, {})
    prev_fps = ledger.position_fingerprints.get(last_round - 1, {})
    if final_fps and prev_fps:
        sims = []
        for m, curr in final_fps.items():
            prev = prev_fps.get(m)
            if prev:
                u = len(curr | prev)
                sims.append(len(curr & prev) / u if u else 0)
        if sims and (sum(sims) / len(sims)) < 0.4:
            _drift_suppressed = False
            if ledger.research_phases and not _is_split:
                _evidence_fed_last = any(
                    ph.get("items_admitted", 0) > 0
                    and ph["phase"].endswith(f"R{last_round}")
                    for ph in ledger.research_phases
                )
                _final_clean = len(ledger.ungrounded_stats_by_round.get(last_round, [])) == 0
                if _evidence_fed_last and _final_clean:
                    _drift_suppressed = True
                    penalties.append("major_drift=0.00(evidence-driven)")
            if not _drift_suppressed:
                penalty_sum += 0.05
                penalties.append("major_drift=0.05")

    # Penalty 5: noisy research
    if ledger.cross_domain_rejections >= 3:
        penalty_sum += 0.03
        penalties.append(f"crossdomain={ledger.cross_domain_rejections}->0.03")

    # Penalty 6: split outcome
    if _is_split:
        p = 0.10 if _outcome == "NO_CONSENSUS" else 0.07
        penalty_sum += p
        penalties.append(f"split_outcome={_outcome or _consensus}->{p:.2f}")

    if penalty_sum == 0:
        log.log(f"  [CONFIDENCE-ADJ] No penalties — unchanged at {raw_str}")
        return {"raw": raw_str, "raw_val": raw_conf, "adjusted": raw_conf,
                "adjusted_label": raw_str, "penalties": []}

    adjusted = max(raw_conf - penalty_sum, 0.20)
    adj_label = "high" if adjusted >= 0.75 else "medium" if adjusted >= 0.50 else "low"
    log.log(f"  [CONFIDENCE-ADJ] {raw_str}({raw_conf:.2f}) -> {adj_label}({adjusted:.2f}) [{', '.join(penalties)}]")
    new_fm = re.sub(
        r'^(confidence:\s*)\S+',
        f'confidence_raw: {raw_str}\n\\1{adj_label}',
        frontmatter, count=1, flags=re.MULTILINE,
    )
    new_text = text[:fm_match.start(1)] + new_fm + text[fm_match.end(1):]
    try:
        report_path.write_text(new_text, encoding="utf-8")
        log.log(f"  [CONFIDENCE-ADJ] Frontmatter updated")
    except Exception as exc:
        log.log(f"  [CONFIDENCE-ADJ] Write failed (non-fatal): {exc}")

    return {"raw": raw_str, "raw_val": raw_conf, "adjusted": round(adjusted, 2),
            "adjusted_label": adj_label, "penalties": penalties}



# ── V3 Fix 2: Ungrounded-statistic detector (log + interventional) ────────────
# V5: No longer log-only. Flagged figures are injected into the next round's
# evidence block as [UNGROUNDED FIGURE WARNINGS], giving models a chance to
# self-correct. Also feeds the downstream confidence penalty.

_UNGROUNDED_PATTERNS = [
    re.compile(r'\b(\d+(?:\.\d+)?)\s*%'),
    re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:probability|chance|likelihood|rate)\b', re.IGNORECASE),
    re.compile(r'\b1\s+in\s+(\d+)\b', re.IGNORECASE),
    re.compile(r'\$(\d[\d,]*(?:\.\d+)?)[KMBkmb]?\b'),
]

def _scan_ungrounded_stats(round_num, model_outputs, ledger, log):
    """V3 Fix 2: Scan model outputs for figures not in evidence.
    Flagged figures are injected into the next round's evidence block as warnings
    and feed the downstream confidence penalty."""
    ev_text = " ".join(item["fact"].lower() for item in ledger.items)
    flagged = []
    seen_figs = set()
    for mname, text in model_outputs.items():
        if not text:
            continue
        for pat in _UNGROUNDED_PATTERNS:
            for match in pat.finditer(text):
                fig = match.group(1) if match.lastindex else match.group(0)
                if fig and fig not in ev_text and fig not in seen_figs:
                    seen_figs.add(fig)
                    ctx = text[max(0, match.start()-30):match.end()+30].replace("\n", " ")[:80]
                    flagged.append({"round": round_num, "model": mname, "figure": fig, "context": ctx})
    if flagged:
        log.log(f"  [UNGROUNDED-STATS] Round {round_num}: {len(flagged)} ungrounded figure(s)")
        for f in flagged[:5]:
            log.log(f'    [{f["model"]}] figure="{f["figure"]}" ctx="{f["context"]}"')
    else:
        log.log(f"  [UNGROUNDED-STATS] Round {round_num}: none detected")
    ledger.ungrounded_stats_by_round[round_num] = flagged
    return flagged


# ── V3 Fix 3: Position-drift detector (log-only) ────────────────────────────

_DRIFT_STOPWORDS = frozenset({
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "but", "is", "are", "was", "be", "by", "from", "that", "this", "it",
    "as", "if", "with", "not", "which", "their", "they", "have", "has",
    "been", "will", "can", "may", "should", "could", "would", "its",
    "also", "there", "here", "then", "however", "therefore", "thus",
    "view", "analysis", "report", "round", "model", "analyst",
    "above", "below", "following", "previous", "original", "prompt",
})

def _extract_position_kw(text, top_n=30):
    from collections import Counter
    words = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    filtered = [w for w in words if len(w) >= 4 and w not in _DRIFT_STOPWORDS]
    return set(w for w, _ in Counter(filtered).most_common(top_n))

def _detect_position_drift(round_num, model_outputs, ledger, log):
    """V3 Fix 3: Compare position fingerprints between rounds. Log-only."""
    curr_fps = {}
    for mname, text in model_outputs.items():
        if text:
            curr_fps[mname] = _extract_position_kw(text)
    ledger.position_fingerprints[round_num] = curr_fps
    if round_num <= 1:
        log.log(f"  [POSITION-DRIFT] Round {round_num}: baseline ({len(curr_fps)} models)")
        return {}
    prev_fps = ledger.position_fingerprints.get(round_num - 1, {})
    if not prev_fps:
        return {}
    drift = {}
    for mname, curr in curr_fps.items():
        prev = prev_fps.get(mname)
        if not prev or not curr:
            continue
        union = len(curr | prev)
        sim = round(len(curr & prev) / union, 2) if union else 0.0
        label = "STABLE" if sim >= 0.7 else "SHIFTED" if sim >= 0.4 else "MAJOR_SHIFT"
        new_kw = sorted(list(curr - prev))[:3]
        dropped = sorted(list(prev - curr))[:3]
        drift[mname] = {"similarity": sim}
        log.log(f"  [POSITION-DRIFT] R{round_num} {mname}: sim={sim} ({label}) new={new_kw} dropped={dropped}")
    if drift:
        avg = round(sum(d["similarity"] for d in drift.values()) / len(drift), 2)
        log.log(f"  [POSITION-DRIFT] R{round_num} avg_similarity={avg}")
    return drift


# ── V3 Fix 4: Explicit option preservation ───────────────────────────────────

def _v3_extract_explicit_options(brief, log):
    """V3 Fix 4: Haiku call at startup to detect finite option set in brief."""
    prompt = (
        "You are a structured-output extraction tool. Determine whether this decision brief "
        "presents a finite set of top-level alternatives to choose between.\n\n"
        f"Brief:\n---\n{brief[:2000]}\n---\n\n"
        "Rules:\n"
        "- Only count TOP-LEVEL alternatives (not sub-steps)\n"
        "- Must be SIBLING CHOICES, not sequential steps\n"
        "- Extract verbatim text per option, short label per option\n\n"
        'If YES: {"explicit_option_mode": true, "options": [{"id": "O1", "label": "short", "text": "verbatim"}]}\n'
        'If NO: {"explicit_option_mode": false, "options": []}'
    )
    try:
        raw = call_haiku(prompt, max_tokens=800)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            log.log("  [EXPLICIT-OPTIONS] No JSON in Haiku response")
            return []
        parsed = json.loads(json_match.group())
        if not parsed.get("explicit_option_mode", False):
            log.log("  [EXPLICIT-OPTIONS] No explicit alternatives detected")
            return []
        options = parsed.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            log.log("  [EXPLICIT-OPTIONS] Fewer than 2 options")
            return []
        clean = []
        for i, opt in enumerate(options[:6]):
            if not isinstance(opt, dict):
                continue
            text = str(opt.get("text", "")).strip()
            label = str(opt.get("label", "")).strip()
            if len(text) < 10:
                continue
            clean.append({"id": f"O{i+1}", "label": label[:60] or text[:60], "text": text})
        if len(clean) >= 2:
            labels = ", ".join(f"{o['id']}={o['label'][:40]}" for o in clean)
            log.log(f"  [EXPLICIT-OPTIONS] {len(clean)} options: {labels}")
            return clean
        log.log("  [EXPLICIT-OPTIONS] After validation < 2 options")
        return []
    except Exception as exc:
        log.log(f"  [EXPLICIT-OPTIONS] Failed (non-fatal): {exc}")
        return []

def _check_option_preservation(round_num, model_outputs, ledger, log):
    """V3 Fix 4: Check if brief-stated options still mentioned. Log-only."""
    if not ledger.explicit_options:
        return []
    combined = " ".join((t or "").lower() for t in model_outputs.values())
    missing = []
    for opt in ledger.explicit_options:
        kws = set(re.findall(r'[a-z]{4,}', opt["text"].lower()))
        if len(kws) < 2:
            continue
        hits = sum(1 for kw in kws if kw in combined)
        threshold = max(2, len(kws) * 0.25)
        if hits < threshold:
            missing.append(opt["id"])
            log.log(f"  [OPTION-DROPPED] R{round_num}: {opt['id']} ({opt['label'][:40]}) {hits}/{len(kws)} kw")
    if not missing:
        log.log(f"  [OPTION-PRESERVED] R{round_num}: all {len(ledger.explicit_options)} present")
    ledger.option_drops_by_round[round_num] = missing
    return missing


# ── Phase 4: State transition recorder ────────────────────────────────────────

def _record_transition(ledger, from_state, to_state, trigger):
    """Record a state transition on the ledger for Phase 4 formalization."""
    ledger.state_transitions.append({
        "from_state": from_state,
        "to_state": to_state,
        "trigger": trigger,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _close_unqueried_gaps(ledger, reason, log):
    """Drop any gaps that were detected but neither queried nor already dropped.
    Prevents S4 invariant warnings from gaps that fell through research phases."""
    detected_ids = {g["gap_id"] for g in ledger.gaps_detected}
    queried_ids = {g["gap_id"] for g in ledger.gaps_queried}
    dropped_ids = {g["gap_id"] for g in ledger.gaps_dropped}
    untracked = detected_ids - queried_ids - dropped_ids
    for gap_id in sorted(untracked):
        ledger.gaps_dropped.append({"gap_id": gap_id, "reason": reason})
        log.log(f"  [GAP-DROPPED] gap_id={gap_id} reason={reason}")


# ── Phase 1 Roadmap: execution event recorder ────────────────────────────────

def _record_round_execution_events(round_key, results, ledger):
    """Scan round results for timeouts, failures, and fallbacks. Append to ledger."""
    for model, r in results.items():
        if not r.get("ok"):
            err = r.get("error", "unknown")
            event_type = "timeout" if "timeout" in str(err).lower() else "failure"
            ledger.execution_events.append({
                "type": event_type, "stage": f"{round_key}/{model}",
                "detail": str(err)[:200],
            })
        actual = r.get("actual_model", "")
        expected = PRIMARY_MODELS.get(model, model)
        if actual and actual != expected:
            ledger.execution_events.append({
                "type": "fallback", "stage": f"{round_key}/{model}",
                "detail": f"fallback:{round_key}/{model} expected={expected} actual={actual}",
            })
        if r.get("warning"):
            ledger.execution_events.append({
                "type": "degraded_success", "stage": f"{round_key}/{model}",
                "detail": r["warning"],
            })


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global INVOKE, PRIMARY_MODELS, ROUND1_MODELS, ROUND2_MODELS, ROUND234_MODELS
    global TIMEOUTS, COOLDOWN_PER_TRANSITION, WALL_CLOCK_BUDGET_S

    parser = argparse.ArgumentParser(description="Brain V3 Orchestrator — demand-driven research pipeline")
    parser.add_argument("--brief",  required=True, help="Path to brief file (free-form, any format)")
    parser.add_argument("--outdir", help="Output directory (auto-created under /tmp if omitted)")
    parser.add_argument("--rounds", type=int, default=4, choices=[1, 2, 3, 4],
                        help="Number of deliberation rounds (default 4). Use 1 for fast single-round.")
    parser.add_argument("--wall-clock-budget", type=int, default=WALL_CLOCK_BUDGET_S,
                        help="Maximum wall-clock seconds for deliberation rounds.")
    args = parser.parse_args()

    brief_path = Path(args.brief)
    if not brief_path.exists():
        print(f"[BRAIN ERROR] Brief file missing: {brief_path}", file=sys.stderr)
        sys.exit(1)

    brief = brief_path.read_text().strip()
    if not brief:
        print("[BRAIN ERROR] Brief is empty.", file=sys.stderr)
        sys.exit(1)

    outdir = Path(args.outdir) if args.outdir else Path(f"/tmp/brain-v3-{int(time.time())}")
    outdir.mkdir(parents=True, exist_ok=True)

    log = Logger(outdir / "orchestrator.log")
    log.log("Brain V3 Orchestrator started — demand-driven research enabled")
    log.log(f"Outdir: {outdir}")

    brief_copy = outdir / "brief.md"
    brief_copy.write_text(brief)
    log.log(f"Brief: {brief_copy} ({len(brief)} chars)")

    # ── Phase 0: Search Mode Classification ───────────────────────────────────
    log.log("\n── Phase 0: Search mode classification ──")
    # Phase 4: state transitions begin here — ledger not yet created, defer first transition
    search_mode, _router_confidence, _mode_origin = _resolve_search_mode(brief, log)
    log.log(f"  [SEARCH-MODE-LOCK] selected_mode={search_mode} routing_confidence={_router_confidence} origin={_mode_origin}")
    log.log(f"  search_mode = {search_mode}")

    # ── Evidence Ledger init ───────────────────────────────────────────────────
    ledger = EvidenceLedger(brief)
    ledger.search_mode = search_mode
    ledger.search_diag_router_confidence = _router_confidence
    ledger.search_diag_upfront_mode = search_mode
    ledger.search_mode_origin = _mode_origin
    ledger.run_id = outdir.name  # use outdir basename as canonical run_id
    ledger.decisions.append({
        "decision_type": "search_mode_classification",
        "trigger": "phase_0",
        "inputs": {"routing_confidence": _router_confidence, "origin": _mode_origin},
        "reason": f"selected_mode={search_mode}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # V3 Fix 4: Detect explicit options in brief
    log.log("\n── Phase 0b: Explicit option extraction ──")
    ledger.explicit_options = _v3_extract_explicit_options(brief, log)

    proof = {
        "proof_schema_version": "2.0",
        "run_id":            ledger.run_id,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "protocol_version":  "v3",
        "brain_config":      "archimedes-v3",
        "brief_path":        str(brief_copy),
        "outdir":            str(outdir),
        "rounds_requested":  args.rounds,
        "search_mode":       search_mode,
        "initial_search_mode": search_mode,
        "final_search_mode":   search_mode,
        "search_mode_escalated": False,
        "wall_clock_budget_s": args.wall_clock_budget,
        "round1_models":     ROUND1_MODELS,
        "round234_models":   ROUND234_MODELS,
        "round2_models":     ROUND2_MODELS,
        "rounds":            {},
        "final_status":      None,
        "evidence_items":    0,
        "research_phases":   [],
        "synthesis_prompt_path": None,
        "synthesis_status":  None,
        "synthesis_report_path": None,
        "v3_explicit_options": "not applicable",
        "v3_cross_domain_rejections": 0,
        "v3_ungrounded_stats_total": 0,
        "v3_option_drops": "not applicable",
        "v3_position_drift_summary": "not applicable",
        "v3_confidence_adjustment": "not applicable",
        "v3_outcome_class": "not applicable",
        "gaps_detected": [],
        "gaps_queried": [],
        "gaps_dropped": [],
        "decisions": [],
        "execution_events": [],
        "invariant_violations": [],
        "controller_outcome": {},
        "model_positions_by_round": {},
        "position_changes": [],
        "stable_agreements": [],
        "stable_contested": [],
        "evolved_positions": [],
        "unresolved_residual": [],
        "evidence_citation_density": {},
        "convergence_trend": "not applicable",
        "state_transitions": [],
        "shadow_outcome": {},
        "outcome_source": "controller",
        "synthesis_override_present": False,
        # V4: Blocker lifecycle
        "blocker_ledger": [],
        "blocker_summary": {},
        # V6: Contradiction, minority, governing blocker tracking
        "contradiction_ledger": [],
        "contradiction_count": 0,
        "unresolved_contradictions": 0,
        "minority_archive": [],
        "minority_count": 0,
        "unaddressed_minorities": 0,
        "governing_blockers": [],
        "governing_blocker_count": 0,
        "disagreement_floor_applied": False,
    }
    write_proof(outdir, proof)

    # Phase 4: record initial transitions
    _record_transition(ledger, "INIT", "CLASSIFYING", "orchestrator_start")
    _record_transition(ledger, "CLASSIFYING", "ROUND_RUNNING", "classification_complete")

    # ── Wall-clock budget tracking ─────────────────────────────────────────────
    _orch_start_t = time.time()
    _wall_budget = args.wall_clock_budget
    _socrates_times = []
    log.log(f"  Wall-clock budget: {_wall_budget}s ({_wall_budget/60:.0f} min)")

    def _budget_remaining():
        return _wall_budget - (time.time() - _orch_start_t)

    def _should_skip_round(rnd, cooldown_s=45):
        """Budget warning — never skips a round.
        
        Logs a warning if remaining budget is likely insufficient for the next round.
        Records the warning in decisions for proof.json. Always returns False —
        no LLM turn is ever suppressed mid-run.
        """
        remaining = _budget_remaining()
        if _socrates_times:
            estimated_model_s = max(_socrates_times) * 1.3
        else:
            estimated_model_s = max(TIMEOUTS.values())
        estimated_need = estimated_model_s + cooldown_s + 60
        if remaining < estimated_need:
            log.log(
                f"  [BUDGET-WARNING] Round {rnd} may exceed budget — "
                f"remaining={remaining:.0f}s estimated_need={estimated_need:.0f}s "
                f"(proceeding anyway — rounds are never skipped)"
            )
            ledger.decisions.append({
                "decision_type": "budget_warning",
                "trigger": "wall_clock_budget",
                "inputs": {"round": rnd, "remaining": round(remaining),
                           "estimated_need": round(estimated_need)},
                "reason": f"Round {rnd} may exceed budget: {remaining:.0f}s < {estimated_need:.0f}s (proceeding)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return False  # Never skip — all requested rounds always run

    # ── Round 1 ───────────────────────────────────────────────────────────────
    log.log(f"\n── Round 1: {', '.join(ROUND1_MODELS)} (parallel) ──")
    (outdir / "r1-prompt.txt").write_text(brief)

    r1_results = run_parallel(ROUND1_MODELS, brief, outdir, "r1", log)
    r1_ok   = {m: r for m, r in r1_results.items() if r["ok"]}
    r1_fail = {m: r for m, r in r1_results.items() if not r["ok"]}

    log.log(f"  Round 1: {len(r1_ok)}/{len(ROUND1_MODELS)} succeeded")
    proof["rounds"]["r1"] = {
        "responded": list(r1_ok.keys()),
        "failed":    list(r1_fail.keys()),
        "results":   r1_results,
    }
    _record_round_execution_events("r1", r1_results, ledger)

    if len(r1_ok) < 2:
        log.log(f"  ✗ FAIL — need ≥2 Round 1 responses, got {len(r1_ok)}")
        proof["final_status"] = "FAILED_R1_INSUFFICIENT"
        write_proof(outdir, proof)
        log.close()
        print(f"[BRAIN ERROR] Round 1 insufficient responses: need >=2, got {len(r1_ok)}.", file=sys.stderr)
        sys.exit(4)

    r1_d = read_file(outdir / "r1-r1.txt",       "[LLM 1 response not available]")
    r1_s = read_file(outdir / "r1-reasoner.txt",  "[LLM 2 response not available]")
    r1_a = read_file(outdir / "r1-glm5.txt",      "[LLM 3 response not available]")
    r1_k = read_file(outdir / "r1-kimi.txt",      "[LLM 4 response not available]")

    last_round = 1

    if "reasoner" in r1_results and r1_results["reasoner"].get("ok"):
        _socrates_times.append(r1_results["reasoner"]["elapsed"])

    # V3: Post-round analysis (Round 1)
    _r1_outputs_v3 = {"r1": r1_d, "reasoner": r1_s, "glm5": r1_a, "kimi": r1_k}
    _scan_ungrounded_stats(1, _r1_outputs_v3, ledger, log)
    _detect_position_drift(1, _r1_outputs_v3, ledger, log)
    _check_option_preservation(1, _r1_outputs_v3, ledger, log)
    # Phase 3A: extract options from R1 if open-ended brief
    if not ledger.explicit_options:
        _extract_options_from_r1(_r1_outputs_v3, ledger, log)
    # Phase 3A: position extraction + citation tracking
    _extract_positions_for_round(1, _r1_outputs_v3, ledger, log)
    _track_evidence_citations(1, _r1_outputs_v3, ledger, log)
    # V4: Blocker lifecycle — detect contested positions after R1
    _detect_blockers_from_positions(1, ledger, log)
    # V6 Fix 3: Archive minority arguments from kimi (drops after R1)
    _build_minority_archive(1, ["kimi"], ledger, outdir, log)
    _record_transition(ledger, "ROUND_RUNNING", "ROUND_COMPLETE", "round_1_complete")


    if args.rounds >= 2 and _should_skip_round(2, COOLDOWN_PER_TRANSITION.get("r1_to_r2", 15)):
        args.rounds = 1

    # ── R1→R2 Research Gate + Cooldown ────────────────────────────────────────
    if args.rounds >= 2:
        _record_transition(ledger, "ROUND_COMPLETE", "RESEARCH_GATE", "round_1_not_final")
        r1_outputs = {
            "Analyst_1": r1_d,
            "Analyst_2": r1_s,
            "Analyst_3": r1_a,
            "Analyst_4": r1_k,
        }
        r1_to_r2_research_and_cooldown(
            model_outputs=r1_outputs,
            ledger=ledger,
            search_mode=search_mode,
            outdir=outdir,
            log=log,
            cooldown_s=COOLDOWN_PER_TRANSITION.get("r1_to_r2", 15),
        )
        _record_transition(ledger, "RESEARCH_GATE", "ROUND_RUNNING", "r1_r2_research_complete")
        _close_unqueried_gaps(ledger, "r1_r2_research_phase_ended", log)
        # V4: Blocker lifecycle — detect gap blockers and update from research
        _detect_blockers_from_gaps(ledger, 1, log)
        _update_gap_blockers_from_research(ledger, 1, log)
        # V6: Detect contradiction blockers from newly admitted evidence
        _detect_blockers_from_contradictions(ledger, 1, log)

        # Save evidence block for audit
        ev_block = build_evidence_block(ledger)
        if ev_block:
            (outdir / "evidence-r1-to-r2.txt").write_text(ev_block)
            log.log(f"  Evidence block: {len(ledger.items)} item(s) built for R2 prompt")

        # ── Round 2 ──────────────────────────────────────────────────────────
        log.log(f"\n── Round 2: {', '.join(ROUND2_MODELS)} (parallel, refs {len(ROUND1_MODELS)} R1 views) ──")

        r2_prompt = ROUND2_PROMPT.format(
            brief=brief,
            r1_view1=r1_d,
            r1_view2=r1_s,
            r1_view3=r1_a,
            r1_view4=r1_k,
        )
        if ev_block:
            r2_prompt = r2_prompt + "\n\n" + ev_block
        (outdir / "r2-prompt.txt").write_text(r2_prompt)

        r2_results = run_parallel(ROUND2_MODELS, r2_prompt, outdir, "r2", log)
        r2_ok   = {m: r for m, r in r2_results.items() if r["ok"]}
        r2_fail = {m: r for m, r in r2_results.items() if not r["ok"]}

        log.log(f"  Round 2: {len(r2_ok)}/{len(ROUND2_MODELS)} succeeded")
        proof["rounds"]["r2"] = {
            "responded": list(r2_ok.keys()),
            "failed":    list(r2_fail.keys()),
            "results":   r2_results,
        }
        _record_round_execution_events("r2", r2_results, ledger)

        if len(r2_ok) < len(ROUND2_MODELS):
            log.log(f"  ✗ FAIL — Round 2 missing responses from: {list(r2_fail.keys())}")
            proof["final_status"] = "FAILED_R2_INSUFFICIENT"
            proof["evidence_items"] = len(ledger.items)
            proof["research_phases"] = ledger.research_phases
            write_proof(outdir, proof)
            log.close()
            failed_model, failed_result = next(iter(r2_fail.items()))
            emit_model_failure(2, failed_model, failed_result.get("error", "unknown error"), outdir)
            sys.exit(5)

        last_round = 2

        # V3: Post-round analysis (Round 2)
        _r2v3 = {"r1": read_file(outdir / "r2-r1.txt", ""), "reasoner": read_file(outdir / "r2-reasoner.txt", ""), "glm5": read_file(outdir / "r2-glm5.txt", "")}
        _scan_ungrounded_stats(2, _r2v3, ledger, log)
        _detect_position_drift(2, _r2v3, ledger, log)
        _check_option_preservation(2, _r2v3, ledger, log)
        # Phase 3A: position extraction, citation tracking, position changes
        _extract_positions_for_round(2, _r2v3, ledger, log)
        _track_evidence_citations(2, _r2v3, ledger, log)
        _track_position_changes(2, ledger, log)
        # V4: Blocker lifecycle — detect contested positions and drift blockers after R2
        _detect_blockers_from_positions(2, ledger, log)
        _detect_drift_diagnostics(2, ledger, log)
        # V6 Fix 3: Archive minority arguments from glm5 (drops after R2)
        _build_minority_archive(2, ["glm5"], ledger, outdir, log)
        _record_transition(ledger, "ROUND_RUNNING", "ROUND_COMPLETE", "round_2_complete")

    if args.rounds >= 2 and "r2" in proof["rounds"]:
        _r2r = proof["rounds"]["r2"].get("results", {})
        if "reasoner" in _r2r and _r2r["reasoner"].get("ok"):
            _socrates_times.append(_r2r["reasoner"]["elapsed"])

    if args.rounds >= 3 and _should_skip_round(3, COOLDOWN_PER_TRANSITION.get("r2_to_r3", 35)):
        args.rounds = 2

    # ── R2→R3 Research Gate + Cooldown ────────────────────────────────────────
    if args.rounds >= 3:
        _record_transition(ledger, "ROUND_COMPLETE", "RESEARCH_GATE", "round_2_not_final")
        r2_d = read_file(outdir / "r2-r1.txt",       None)
        r2_s = read_file(outdir / "r2-reasoner.txt",  None)
        r2_a = read_file(outdir / "r2-glm5.txt",      None)

        if not (r2_d and r2_s and r2_a):
            missing_views = [
                x for x, v in [("r2-r1", r2_d), ("r2-reasoner", r2_s), ("r2-glm5", r2_a)] if not v
            ]
            proof["final_status"] = "FAILED_R2_INSUFFICIENT"
            proof["evidence_items"] = len(ledger.items)
            proof["research_phases"] = ledger.research_phases
            write_proof(outdir, proof)
            log.close()
            print("[BRAIN ERROR] Round 2 insufficient for Round 3.", file=sys.stderr)
            print(f"[BRAIN ERROR] Missing: {missing_views}", file=sys.stderr)
            sys.exit(5)

        r2_outputs = {"Analyst_1": r2_d, "Analyst_2": r2_s, "Analyst_3": r2_a}

        r2_to_r3_research_and_cooldown(
            model_outputs=r2_outputs,
            ledger=ledger,
            search_mode=ledger.search_mode,
            outdir=outdir,
            log=log,
            cooldown_s=COOLDOWN_PER_TRANSITION.get("r2_to_r3", 35),
        )
        _record_transition(ledger, "RESEARCH_GATE", "ROUND_RUNNING", "r2_r3_research_complete")
        _close_unqueried_gaps(ledger, "r2_r3_research_phase_ended", log)
        # V4: Blocker lifecycle — detect gap blockers and update from research
        _detect_blockers_from_gaps(ledger, 2, log)
        _update_gap_blockers_from_research(ledger, 2, log)
        # V6: Detect contradiction blockers
        _detect_blockers_from_contradictions(ledger, 2, log)

        # Save cumulative evidence block
        ev_block = build_evidence_block(ledger)
        if ev_block:
            (outdir / "evidence-r2-to-r3.txt").write_text(ev_block)
            log.log(f"  Cumulative evidence block: {len(ledger.items)} item(s) built for R3 prompt")

        # ── Round 3 ──────────────────────────────────────────────────────────
        r2_view_count = sum(1 for v in [r2_d, r2_s, r2_a] if v)
        view_label = f"{r2_view_count} R2 view{'s' if r2_view_count != 1 else ''}"
        log.log(f"\n── Round 3: {', '.join(ROUND234_MODELS)} (parallel, refs {view_label}) ──")

        r3_prompt = ROUND3_PROMPT.format(brief=brief, r2_view1=r2_d, r2_view2=r2_s, r2_view3=r2_a)
        if ev_block:
            r3_prompt = r3_prompt + "\n\n" + ev_block
        (outdir / "r3-prompt.txt").write_text(r3_prompt)

        r3_results = run_parallel(ROUND234_MODELS, r3_prompt, outdir, "r3", log)
        r3_ok   = {m: r for m, r in r3_results.items() if r["ok"]}
        r3_fail = {m: r for m, r in r3_results.items() if not r["ok"]}

        log.log(f"  Round 3: {len(r3_ok)}/{len(ROUND234_MODELS)} succeeded")
        proof["rounds"]["r3"] = {
            "responded": list(r3_ok.keys()),
            "failed":    list(r3_fail.keys()),
            "results":   r3_results,
        }
        _record_round_execution_events("r3", r3_results, ledger)

        if len(r3_ok) < len(ROUND234_MODELS):
            log.log(f"  ✗ FAIL — Round 3 missing responses from: {list(r3_fail.keys())}")
            proof["final_status"] = "FAILED_R3_INSUFFICIENT"
            proof["evidence_items"] = len(ledger.items)
            proof["research_phases"] = ledger.research_phases
            write_proof(outdir, proof)
            log.close()
            failed_model, failed_result = next(iter(r3_fail.items()))
            emit_model_failure(3, failed_model, failed_result.get("error", "unknown error"), outdir)
            sys.exit(6)

        last_round = 3

        # V3: Post-round analysis (Round 3)
        _r3v3 = {"r1": read_file(outdir / "r3-r1.txt", ""), "reasoner": read_file(outdir / "r3-reasoner.txt", "")}
        _scan_ungrounded_stats(3, _r3v3, ledger, log)
        _detect_position_drift(3, _r3v3, ledger, log)
        _check_option_preservation(3, _r3v3, ledger, log)
        # Phase 3A: position extraction, citation tracking, position changes
        _extract_positions_for_round(3, _r3v3, ledger, log)
        _track_evidence_citations(3, _r3v3, ledger, log)
        _track_position_changes(3, ledger, log)
        # V4: Blocker lifecycle — detect contested positions and drift blockers after R3
        _detect_blockers_from_positions(3, ledger, log)
        _detect_drift_diagnostics(3, ledger, log)
        _record_transition(ledger, "ROUND_RUNNING", "ROUND_COMPLETE", "round_3_complete")

    if args.rounds >= 3 and "r3" in proof["rounds"]:
        _r3r = proof["rounds"]["r3"].get("results", {})
        if "reasoner" in _r3r and _r3r["reasoner"].get("ok"):
            _socrates_times.append(_r3r["reasoner"]["elapsed"])

    if args.rounds >= 4 and _should_skip_round(4, COOLDOWN_PER_TRANSITION.get("r3_to_r4", 10)):
        args.rounds = 3

    # ── Round 4 ───────────────────────────────────────────────────────────────
    if args.rounds >= 4:
        _record_transition(ledger, "ROUND_COMPLETE", "RESEARCH_GATE", "round_3_not_final")
        r3_d = read_file(outdir / "r3-r1.txt",       None)
        r3_s = read_file(outdir / "r3-reasoner.txt",  None)

        if not (r3_d and r3_s):
            missing_views = [x for x, v in [("r3-r1", r3_d), ("r3-reasoner", r3_s)] if not v]
            proof["final_status"] = "FAILED_R3_INSUFFICIENT"
            proof["evidence_items"] = len(ledger.items)
            proof["research_phases"] = ledger.research_phases
            write_proof(outdir, proof)
            log.close()
            print("[BRAIN ERROR] Round 3 insufficient for Round 4.", file=sys.stderr)
            print(f"[BRAIN ERROR] Missing: {missing_views}", file=sys.stderr)
            sys.exit(6)

        # ── R3→R4 Research Gate + Cooldown (new in V2.1) ─────────────────
        r3_outputs = {"Analyst_1": r3_d, "Analyst_2": r3_s}
        r3_to_r4_research_and_cooldown(
            model_outputs=r3_outputs,
            ledger=ledger,
            outdir=outdir,
            log=log,
            cooldown_s=COOLDOWN_PER_TRANSITION.get("r3_to_r4", 10),
        )
        _record_transition(ledger, "RESEARCH_GATE", "ROUND_RUNNING", "r3_r4_research_complete")
        _close_unqueried_gaps(ledger, "r3_r4_research_phase_ended", log)
        # V4: Blocker lifecycle — detect gap blockers and update from research
        _detect_blockers_from_gaps(ledger, 3, log)
        _update_gap_blockers_from_research(ledger, 3, log)
        # V6: Detect contradiction blockers
        _detect_blockers_from_contradictions(ledger, 3, log)

        # Save cumulative evidence block (may now include R3→R4 research)
        ev_block = build_evidence_block(ledger)
        if ev_block:
            (outdir / "evidence-r3-to-r4.txt").write_text(ev_block)
            log.log(f"  Cumulative evidence block: {len(ledger.items)} item(s) built for R4 prompt")

        r3_view_count = sum(1 for v in [r3_d, r3_s] if v)
        view_label = f"{r3_view_count} R3 view{'s' if r3_view_count != 1 else ''}"
        log.log(f"\n── Round 4: {', '.join(ROUND234_MODELS)} (parallel, refs {view_label}) ──")

        # Use cumulative evidence block (now includes any R3→R4 research)
        ev_block = build_evidence_block(ledger)
        r4_prompt = ROUND4_PROMPT.format(brief=brief, r3_view1=r3_d, r3_view2=r3_s)
        if ev_block:
            r4_prompt = r4_prompt + "\n\n" + ev_block
        (outdir / "r4-prompt.txt").write_text(r4_prompt)

        r4_results = run_parallel(ROUND234_MODELS, r4_prompt, outdir, "r4", log)
        r4_ok   = {m: r for m, r in r4_results.items() if r["ok"]}
        r4_fail = {m: r for m, r in r4_results.items() if not r["ok"]}

        log.log(f"  Round 4: {len(r4_ok)}/{len(ROUND234_MODELS)} succeeded")
        proof["rounds"]["r4"] = {
            "responded": list(r4_ok.keys()),
            "failed":    list(r4_fail.keys()),
            "results":   r4_results,
        }
        _record_round_execution_events("r4", r4_results, ledger)

        if len(r4_ok) < len(ROUND234_MODELS):
            log.log(f"  ✗ FAIL — Round 4 missing responses from: {list(r4_fail.keys())}")
            proof["final_status"] = "FAILED_R4_INSUFFICIENT"
            proof["evidence_items"] = len(ledger.items)
            proof["research_phases"] = ledger.research_phases
            write_proof(outdir, proof)
            log.close()
            failed_model, failed_result = next(iter(r4_fail.items()))
            emit_model_failure(4, failed_model, failed_result.get("error", "unknown error"), outdir)
            sys.exit(7)

        last_round = 4

        # V3: Post-round analysis (Round 4)
        _r4v3 = {"r1": read_file(outdir / "r4-r1.txt", ""), "reasoner": read_file(outdir / "r4-reasoner.txt", "")}
        _scan_ungrounded_stats(4, _r4v3, ledger, log)
        _detect_position_drift(4, _r4v3, ledger, log)
        _check_option_preservation(4, _r4v3, ledger, log)
        # Phase 3A: position extraction, citation tracking, position changes
        _extract_positions_for_round(4, _r4v3, ledger, log)
        _track_evidence_citations(4, _r4v3, ledger, log)
        _track_position_changes(4, ledger, log)
        # V4: Blocker lifecycle — detect contested positions and drift blockers after R4
        _detect_blockers_from_positions(4, ledger, log)
        _detect_drift_diagnostics(4, ledger, log)
        _record_transition(ledger, "ROUND_RUNNING", "ROUND_COMPLETE", "round_4_complete")

    # ── Final status ──────────────────────────────────────────────────────────
    proof["final_status"]    = "COMPLETE"
    proof["final_round"]     = last_round
    proof["evidence_items"]  = len(ledger.items)
    proof["research_phases"] = ledger.research_phases
    _record_transition(ledger, "ROUND_COMPLETE", "PRE_SYNTHESIS", f"round_{last_round}_is_final")

    # ── Phase 3C: Controller outcome classification (BEFORE synthesis) ────────
    # V4: Close stale blockers before classification — ensures no OPEN blockers remain
    _close_stale_blockers(ledger, last_round, log)
    log.log("\n── Controller Outcome Classification ──")
    controller_outcome = _classify_outcome(last_round, ledger, log)
    proof["controller_outcome"] = controller_outcome
    # Controller is now the canonical outcome authority
    proof["v3_outcome_class"] = controller_outcome["outcome_class"]
    proof["outcome_source"] = "controller"

    # Phase 3A: emit canonical deliberation fields at proof level
    _delib = _compute_deliberation_derived(last_round, ledger, log)
    (_d_groups, _d_stable_ag, _d_stable_con, _d_evolved, _d_unresolved,
     _d_conv_trend, _d_agree_ratio) = _delib
    proof["stable_agreements"] = _d_stable_ag
    proof["stable_contested"] = _d_stable_con
    proof["evolved_positions"] = [
        {"model": c["model"], "from_round": c["from_round"], "to_round": c["to_round"],
         "from_position": c["from_position"], "to_position": c["to_position"],
         "evidence_driven": c["evidence_driven"]}
        for c in _d_evolved
    ]
    proof["unresolved_residual"] = _d_unresolved

    # ── Write synthesis prompt with controller outcome constraint ─────────────
    synthesis_prompt = build_synthesis_prompt(brief, outdir, last_round)

    # Phase 3C: Inject controller outcome constraint into synthesis prompt
    _ctrl_class = controller_outcome["outcome_class"]
    _ctrl_shared = controller_outcome.get("shared_ground", [])
    _ctrl_contested = controller_outcome.get("contested_dimension")
    _outcome_constraint = (
        "\n\n---\n\n## OUTCOME CONSTRAINT\n"
        f"The controller has classified this deliberation as: **{_ctrl_class}**\n"
    )
    if _ctrl_shared:
        _outcome_constraint += f"Shared ground: {', '.join(str(s) for s in _ctrl_shared)}\n"
    if _ctrl_contested:
        _outcome_constraint += f"Contested dimension: {_ctrl_contested}\n"
    _outcome_constraint += (
        "\nNarrate within this classification. If you believe it is incorrect, "
        "include a [SYNTHESIS-OVERRIDE] section at the end of your report "
        "explaining why, but do NOT change the outcome field in the frontmatter.\n"
        f"Use `outcome: {_ctrl_class}` in your YAML frontmatter.\n"
    )

    # V6 Fix 7: Synthesis transparency — inject unresolved residue
    # The narrative cannot omit active high-severity residue
    _residue_lines = []

    # Unresolved contradictions
    _unresolved_ctrs = [c for c in ledger.contradiction_ledger if c["status"] == "UNRESOLVED"]
    if _unresolved_ctrs:
        _residue_lines.append(f"\n**Unresolved evidence contradictions ({len(_unresolved_ctrs)}):**")
        for ctr in _unresolved_ctrs[:5]:
            _residue_lines.append(f"- {ctr['contradiction_id']}: {ctr['detail'][:120]}")

    # Unaddressed minority arguments
    _unaddressed = [m for m in ledger.minority_archive if not m.get("addressed_by")]
    if _unaddressed:
        _residue_lines.append(f"\n**Unaddressed minority arguments ({len(_unaddressed)}):**")
        for mv in _unaddressed:
            _residue_lines.append(
                f"- [{mv['model']} R{mv['round_dropped']}] {mv['position']}: "
                f"{mv['argument_summary'][:100]}"
            )

    # Governing blockers
    _gov_blockers = _get_governing_blockers(ledger)
    if _gov_blockers:
        _residue_lines.append(f"\n**Active governing blockers ({len(_gov_blockers)}):**")
        for blk in _gov_blockers[:5]:
            _residue_lines.append(
                f"- {blk['blocker_id']} [{blk['kind']}]: {blk['source_dimension'][:60]}"
            )

    if _residue_lines:
        _outcome_constraint += (
            "\n\n## UNRESOLVED RESIDUE (must appear in report)\n"
            "The following items remain unresolved. Your report MUST include a section\n"
            "that explicitly acknowledges each one. Do not present a clean narrative\n"
            "that omits these active conflicts.\n"
            + "\n".join(_residue_lines) + "\n"
        )

    synthesis_prompt_path = outdir / "synthesis-prompt.txt"

    provenance_lines = ["\n\n---\n\n## Model Provenance\n"]
    for rnd_key, rnd_data in proof["rounds"].items():
        for m, r in rnd_data.get("results", {}).items():
            if r.get("ok"):
                actual = r.get("actual_model", PRIMARY_MODELS.get(m, m))
                expected = PRIMARY_MODELS.get(m, m)
                label = f"**{actual}**" + (" *(fallback)*" if actual != expected else "")
                provenance_lines.append(f"- {rnd_key} / {m}: {label}")

    synthesis_prompt_path.write_text(synthesis_prompt + _outcome_constraint + "\n".join(provenance_lines))
    proof["synthesis_prompt_path"] = str(synthesis_prompt_path)
    log.log(f"\n  ✓ Synthesis prompt saved: {synthesis_prompt_path} ({synthesis_prompt_path.stat().st_size}b)")
    log.log(f"  Evidence NOT injected into synthesis stage (design intent)")
    log.log(f"  [OUTCOME-CONSTRAINT] Injected: {_ctrl_class}")

    # ── Synthesis stage ──────────────────────────────────────────────────────
    if proof["final_status"] in SYNTHESIS_FINAL_STATUSES:
        _record_transition(ledger, "PRE_SYNTHESIS", "SYNTHESIZING", "synthesis_prompt_ready")
        log.log(f"\n── Synthesis stage ──")
        log.log(f"  Starting synthesis stage with prompt: {synthesis_prompt_path}")
        synthesis_result = invoke_hermes_synthesis(outdir, synthesis_prompt_path, log)
        proof["synthesis_status"]      = synthesis_result["status"]
        proof["synthesis_report_path"] = synthesis_result.get("report_path")
        proof["synthesis_session_id"]  = synthesis_result.get("session_id")
        proof["synthesis_elapsed_s"]   = synthesis_result.get("elapsed_s")
        if synthesis_result.get("status_path"):
            proof["synthesis_status_path"] = synthesis_result["status_path"]
        if synthesis_result.get("response_status"):
            proof["synthesis_response_status"] = synthesis_result["response_status"]
        if synthesis_result.get("error"):
            proof["synthesis_error"] = synthesis_result["error"]
        write_proof(outdir, proof)

        log.log(f"  Synthesis status: {proof['synthesis_status']}")
        if proof["synthesis_report_path"]:
            rp = Path(proof["synthesis_report_path"])
            log.log(f"  Synthesis report: {rp} ({rp.stat().st_size}b)")
        if synthesis_result.get("error"):
            log.log(f"  Synthesis error: {synthesis_result['error']}")

        # ── SLP: Standalone Leverage Assessment (post-synthesis appendix) ──
        if proof["synthesis_report_path"] and proof["synthesis_status"] == "COMPLETE":
            try:
                rp = Path(proof["synthesis_report_path"])
                slp_outputs = {}
                for model_key in ROUND234_MODELS:
                    txt = read_file(outdir / f"r{last_round}-{model_key}.txt", None)
                    if txt:
                        slp_outputs[model_key] = txt

                if slp_outputs:
                    log.log(f"\n── SLP: Standalone Leverage Assessment ──")
                    slp_section = _build_slp_section(
                        report_path=rp,
                        r4_outputs=slp_outputs,
                        evidence_count=len(ledger.items),
                        log=log,
                        controller_outcome_class=controller_outcome["outcome_class"],
                    )
                    if slp_section:
                        with rp.open("a", encoding="utf-8") as fh:
                            fh.write(slp_section)
                        log.log(f"  [SLP] Appended {len(slp_section)} chars to synthesis report")
                    else:
                        log.log(f"  [SLP] No positions extracted — SLP section not appended")
                else:
                    log.log(f"  [SLP] No final-round outputs available — SLP skipped")
            except Exception as exc:
                log.log(f"  [SLP-ERROR] SLP generation failed (non-fatal): {exc}")

        # Phase 3C: Extract synthesis frontmatter outcome for Y1 invariant check
        _synthesis_fm_outcome = None
        if proof["synthesis_report_path"] and proof["synthesis_status"] == "COMPLETE":
            try:
                _rpt_head = Path(proof["synthesis_report_path"]).read_text(encoding="utf-8")[:800]
                _oc_m = re.search(r'^outcome:\s*(\S+)', _rpt_head, re.MULTILINE)
                if _oc_m:
                    _synthesis_fm_outcome = _oc_m.group(1).strip()
            except Exception:
                pass

        # Shadow comparison (now post-switchover: controller is canonical, synthesis is checked)
        if _synthesis_fm_outcome:
            proof["shadow_outcome"] = {
                "controller": controller_outcome["outcome_class"],
                "synthesis": _synthesis_fm_outcome,
                "agreement": controller_outcome["outcome_class"] == _synthesis_fm_outcome,
            }
            log.log(f"  [OUTCOME-SHADOW] controller={controller_outcome['outcome_class']} "
                     f"synthesis={_synthesis_fm_outcome} "
                     f"agreement={controller_outcome['outcome_class'] == _synthesis_fm_outcome}")
            # Check for [SYNTHESIS-OVERRIDE] section
            try:
                _full_rpt = Path(proof["synthesis_report_path"]).read_text(encoding="utf-8")
                if "[SYNTHESIS-OVERRIDE]" in _full_rpt:
                    log.log(f"  [SYNTHESIS-OVERRIDE] Detected — narrated dissent present")
                    proof["synthesis_override_present"] = True
                else:
                    proof["synthesis_override_present"] = False
            except Exception:
                proof["synthesis_override_present"] = False

        # Phase 3C: Confidence adjustment reads from CONTROLLER outcome
        if proof["synthesis_report_path"] and proof["synthesis_status"] == "COMPLETE":
            log.log("\n── V3: Post-synthesis confidence adjustment ──")
            adj_result = _adjust_synthesis_confidence(Path(proof["synthesis_report_path"]), ledger, last_round, log,
                                                      outcome_override=controller_outcome["outcome_class"])
            if adj_result:
                proof["v3_confidence_adjustment"] = (
                    f"{adj_result['raw']}({adj_result['raw_val']:.2f})"
                    f"->{adj_result['adjusted_label']}({adj_result['adjusted']:.2f})"
                    f" [{', '.join(adj_result['penalties'])}]"
                    if adj_result['penalties']
                    else f"{adj_result['raw']}({adj_result['raw_val']:.2f}) unchanged"
                )

        _record_transition(ledger, "SYNTHESIZING", "POST_SYNTHESIS", "synthesis_complete")

    # ── Model provenance & total time ─────────────────────────────────────────
    total_model_time = sum(
        r.get("elapsed", 0)
        for rnd in proof["rounds"].values()
        for r in rnd["results"].values()
        if r.get("ok")
    )
    proof["total_model_time_s"] = round(total_model_time, 1)

    model_provenance = {}
    for rnd_key, rnd_data in proof["rounds"].items():
        for m, r in rnd_data.get("results", {}).items():
            expected = PRIMARY_MODELS.get(m, m)
            actual = r.get("actual_model", expected)
            if actual != expected:
                model_provenance[f"{rnd_key}/{m}"] = actual
    proof["model_provenance"] = model_provenance
    write_proof(outdir, proof)

    # Telemetry: canonicalize search mode in proof
    proof["final_search_mode"] = ledger.search_mode
    proof["search_mode_escalated"] = ledger.search_mode_escalated

    # V3: Populate proof fields
    proof["v3_cross_domain_rejections"] = ledger.cross_domain_rejections
    proof["v3_ungrounded_stats_total"] = sum(len(v) for v in ledger.ungrounded_stats_by_round.values())
    # V5: Evidence cap discards — serialized into proof for machine-readability
    _cap_discards = getattr(ledger, "_cap_discards", 0)
    proof["v3_evidence_cap_discards"] = _cap_discards
    if _cap_discards > 0:
        log.log(f"  [EVIDENCE-CAP-SUMMARY] {_cap_discards} item(s) discarded at cap={MAX_EVIDENCE_ITEMS}")
    if ledger.explicit_options:
        proof["v3_explicit_options"] = [o["label"] for o in ledger.explicit_options]
        fd = ledger.option_drops_by_round.get(last_round, [])
        proof["v3_option_drops"] = fd if fd else "none"
    drift_s = {}
    for rnd, fps in ledger.position_fingerprints.items():
        if rnd <= 1:
            continue
        prev = ledger.position_fingerprints.get(rnd - 1, {})
        if prev:
            sims = []
            for m, curr in fps.items():
                p = prev.get(m)
                if p:
                    u = len(curr | p)
                    sims.append(round(len(curr & p) / u, 2) if u else 0)
            if sims:
                drift_s[f"R{rnd}"] = round(sum(sims) / len(sims), 2)
    proof["v3_position_drift_summary"] = drift_s if drift_s else "not applicable"

    # Phase 1 roadmap: populate gap tracking, decisions, execution events
    proof["gaps_detected"] = ledger.gaps_detected
    proof["gaps_queried"] = ledger.gaps_queried
    proof["gaps_dropped"] = ledger.gaps_dropped
    proof["decisions"] = ledger.decisions
    proof["execution_events"] = ledger.execution_events

    # Phase 3A: populate position tracking, citation density, convergence
    proof["model_positions_by_round"] = {
        str(rnd): {
            m: {k: v for k, v in pos.items()}
            for m, pos in positions.items()
        }
        for rnd, positions in ledger.model_positions_by_round.items()
    }
    proof["position_changes"] = ledger.position_changes
    proof["evidence_citation_density"] = _compute_citation_density(ledger)
    # Convergence trend (from controller outcome if available)
    co = proof.get("controller_outcome", {})
    proof["convergence_trend"] = co.get("position_trajectory", "not applicable")
    proof["state_transitions"] = ledger.state_transitions

    # V4: Blocker lifecycle — populate proof fields
    proof["blocker_ledger"] = ledger.blocker_ledger
    proof["blocker_summary"] = _compute_blocker_summary(ledger)

    # V6: Populate new proof fields
    proof["contradiction_ledger"] = ledger.contradiction_ledger
    proof["contradiction_count"] = len(ledger.contradiction_ledger)
    proof["unresolved_contradictions"] = len([c for c in ledger.contradiction_ledger if c["status"] == "UNRESOLVED"])
    proof["minority_archive"] = ledger.minority_archive
    proof["minority_count"] = len(ledger.minority_archive)
    proof["unaddressed_minorities"] = len([m for m in ledger.minority_archive if not m.get("addressed_by")])
    _gov = _get_governing_blockers(ledger)
    proof["governing_blockers"] = [
        {"blocker_id": b["blocker_id"], "kind": b["kind"], "dimension": b["source_dimension"][:60]}
        for b in _gov
    ]
    proof["governing_blocker_count"] = len(_gov)
    proof["disagreement_floor_applied"] = controller_outcome.get("disagreement_floor_applied", False)
    if controller_outcome.get("disagreement_floor_reasons"):
        proof["disagreement_floor_reasons"] = controller_outcome["disagreement_floor_reasons"]

    # Phase 1 roadmap: run invariant validator
    _record_transition(ledger, "POST_SYNTHESIS", "VALIDATING", "artifacts_ready")
    log.log(f"\n── Invariant Validation ──")
    inv_violations = _validate_run_invariants(proof, ledger, log)
    proof["invariant_violations"] = inv_violations

    # Check for FATAL violations
    _fatal_count = sum(1 for v in inv_violations if v.get("severity") == "FATAL")
    if _fatal_count > 0:
        _record_transition(ledger, "VALIDATING", "FAILED", f"fatal_violations={_fatal_count}")
    else:
        _record_transition(ledger, "VALIDATING", "COMPLETE", "zero_fatal_violations")

    # Update state_transitions in proof after validation transitions
    proof["state_transitions"] = ledger.state_transitions
    write_proof(outdir, proof)

    # ── Summary ───────────────────────────────────────────────────────────────
    log.log(f"\n── Orchestration complete ──")
    log.log(f"  Status:           {proof['final_status']}")
    log.log(f"  search_mode:      {ledger.search_diag_upfront_mode}" +
            (f" → {ledger.search_mode} (escalated)" if ledger.search_mode_escalated else ""))
    log.log(f"  Rounds requested: {args.rounds}  |  Final round: {last_round}")
    log.log(f"  Evidence items:   {len(ledger.items)}")
    log.log(f"  Research phases:  {len(ledger.research_phases)}")
    log.log(f"  Total model time: {proof['total_model_time_s']}s")
    if ledger.research_phases:
        for phase in ledger.research_phases:
            log.log(f"  Phase {phase['phase']}: method={phase['method']} queries={phase['queries_attempted']} admitted={phase['items_admitted']}")
    if model_provenance:
        log.log(f"\n── Model fallbacks used ──")
        for slot, actual in model_provenance.items():
            log.log(f"  {slot}: {actual} (fallback)")
    else:
        log.log(f"  All models ran as primary (no fallbacks)")

    log.log(f"\n── V3 Controller Diagnostics ──")
    log.log(f"  Cross-domain rejections: {ledger.cross_domain_rejections}")
    log.log(f"  Ungrounded stats total:  {proof['v3_ungrounded_stats_total']}")
    log.log(f"  Explicit options:        {len(ledger.explicit_options)} detected")
    for rnd, drops in sorted(ledger.option_drops_by_round.items()):
        if drops:
            log.log(f"  Option drops R{rnd}:       {drops}")
    log.log(f"  Position drift:          {proof['v3_position_drift_summary']}")

    # V4: Blocker lifecycle diagnostics
    _blk_summary = proof.get("blocker_summary", {})
    log.log(f"\n── V4 Blocker Lifecycle ──")
    log.log(f"  Total blockers:   {_blk_summary.get('total_blockers', 0)}")
    log.log(f"  By status:        {_blk_summary.get('by_status', {})}")
    log.log(f"  By kind:          {_blk_summary.get('by_kind', {})}")
    log.log(f"  Resolved:         {_blk_summary.get('resolved', 0)}")
    log.log(f"  Deferred:         {_blk_summary.get('deferred', 0)}")
    log.log(f"  Dropped:          {_blk_summary.get('dropped', 0)}")
    for blk in ledger.blocker_ledger:
        transitions = " → ".join(h["status"] for h in blk["status_history"])
        log.log(f"  {blk['blocker_id']} [{blk['kind']}] {blk['source_dimension'][:50]}: {transitions}")

    # V6 diagnostics
    log.log(f"\n── V6 Controller Enhancements ──")
    log.log(f"  Contradictions:   {len(ledger.contradiction_ledger)} total, "
            f"{len([c for c in ledger.contradiction_ledger if c['status'] == 'UNRESOLVED'])} unresolved")
    log.log(f"  Minority archive: {len(ledger.minority_archive)} entries, "
            f"{len([m for m in ledger.minority_archive if not m.get('addressed_by')])} unaddressed")
    _gov = _get_governing_blockers(ledger)
    log.log(f"  Governing blockers: {len(_gov)}")
    if controller_outcome.get("disagreement_floor_applied"):
        log.log(f"  Disagreement floor: APPLIED — {controller_outcome.get('disagreement_floor_reasons', [])}")
    else:
        log.log(f"  Disagreement floor: not triggered")
    log.log(f"  Evidence cap discards: {ledger._cap_discards}")

    # V3 controller diagnostics

    log.log(f"\nSynthesis prompt: {synthesis_prompt_path}")
    log.log(f"Outdir: {outdir}")
    _emit_search_diagnostics(ledger, log)

    # ── Proof integrity check ─────────────────────────────────────────────────
    _proof_complete = (
        proof.get("final_status") == "COMPLETE"
        and proof.get("controller_outcome", {}).get("outcome_class")
        and proof.get("model_positions_by_round")
        and proof.get("proof_schema_version") == "2.0"
        and proof.get("synthesis_status") == "COMPLETE"
        # V4: blocker fields must be populated
        and isinstance(proof.get("blocker_ledger"), list)
        and isinstance(proof.get("blocker_summary"), dict)
        and proof.get("blocker_summary", {}).get("total_blockers", -1) >= 0
    )
    if _proof_complete:
        log.log(f"\n  [PROOF-INTEGRITY] VALID — all canonical fields populated (including blocker lifecycle)")
    else:
        _missing = []
        if proof.get("final_status") != "COMPLETE":
            _missing.append(f"final_status={proof.get('final_status')}")
        if not proof.get("controller_outcome", {}).get("outcome_class"):
            _missing.append("controller_outcome empty")
        if not proof.get("model_positions_by_round"):
            _missing.append("model_positions_by_round empty")
        if proof.get("synthesis_status") != "COMPLETE":
            _missing.append(f"synthesis_status={proof.get('synthesis_status')}")
        if not isinstance(proof.get("blocker_ledger"), list):
            _missing.append("blocker_ledger missing or wrong type")
        if not isinstance(proof.get("blocker_summary"), dict):
            _missing.append("blocker_summary missing or wrong type")
        log.log(f"\n  [PROOF-INTEGRITY] INCOMPLETE — {', '.join(_missing)}")

    log.close()

    print(f"OUTDIR={outdir}")
    print(f"STATUS={proof['final_status']}")
    print(f"SEARCH_MODE={ledger.search_mode}")
    print(f"EVIDENCE_ITEMS={len(ledger.items)}")
    print(f"ROUNDS_REQUESTED={args.rounds}")
    print(f"FINAL_ROUND={last_round}")
    print(f"SYNTHESIS_PROMPT={synthesis_prompt_path}")
    print(f"SYNTHESIS_STATUS={proof['synthesis_status']}")
    print(f"SYNTHESIS_REPORT={proof['synthesis_report_path']}")
    print(f"PROOF_VALID={'true' if _proof_complete else 'false'}")

    if proof["final_status"].startswith("FAILED"):
        sys.exit(6)


if __name__ == "__main__":
    main()
