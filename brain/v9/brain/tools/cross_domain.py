"""Cross-domain evidence filter.

Prevents medical evidence from polluting security briefs, finance from
infrastructure briefs, etc. Domain detection via keyword families.
"""
from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "security": {"cve", "vulnerability", "exploit", "rce", "xss", "sql injection",
                 "buffer overflow", "privilege escalation", "malware", "breach",
                 "authentication", "authorization", "firewall", "encryption"},
    "medical": {"dosage", "patient", "clinical", "diagnosis", "treatment",
                "medication", "symptom", "therapy", "pharmaceutical", "surgery"},
    "finance": {"stock", "equity", "portfolio", "etf", "dividend", "trading",
                "market cap", "earnings", "revenue", "valuation", "bond"},
    "infrastructure": {"server", "database", "kubernetes", "docker", "deployment",
                       "latency", "throughput", "scaling", "load balancer", "cdn"},
    "compliance": {"gdpr", "hipaa", "sox", "pci", "dora", "regulation", "audit",
                   "compliance", "certification", "framework"},
}

# Which domains are compatible with each other
COMPATIBLE_DOMAINS: dict[str, set[str]] = {
    "security": {"security", "infrastructure", "compliance"},
    "medical": {"medical"},
    "finance": {"finance"},
    "infrastructure": {"infrastructure", "security", "compliance"},
    "compliance": {"compliance", "security", "infrastructure"},
}


def detect_domain(text: str) -> str | None:
    """Detect the primary domain of a text based on keyword density."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    if not scores:
        return None
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else None


def is_cross_domain(evidence_text: str, brief_domain: str) -> bool:
    """Check if evidence is from an incompatible domain."""
    ev_domain = detect_domain(evidence_text)
    if ev_domain is None:
        return False  # Can't determine domain — allow it
    compatible = COMPATIBLE_DOMAINS.get(brief_domain, {brief_domain})
    return ev_domain not in compatible
