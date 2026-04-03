"""Configuration for the Thinker V8 Brain engine."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for a single LLM."""
    name: str
    model_id: str
    provider: str  # "openrouter", "anthropic", "deepseek", or "zai"
    max_tokens: int
    timeout_s: int
    is_thinking: bool = False


# --- Model roster (V8 spec Section 4) ---

R1_MODEL = ModelConfig("r1", "deepseek/deepseek-r1-0528", "openrouter", 30_000, 720, is_thinking=True)
REASONER_MODEL = ModelConfig("reasoner", "deepseek-reasoner", "deepseek", 30_000, 720, is_thinking=True)
GLM5_MODEL = ModelConfig("glm5", "glm-5-turbo", "zai", 16_000, 480)
KIMI_MODEL = ModelConfig("kimi", "moonshotai/kimi-k2", "openrouter", 16_000, 480)
SONNET_MODEL = ModelConfig("sonnet", "claude-sonnet-4-6", "anthropic", 16_000, 300)

# --- Round topology (V8 spec: 4 -> 3 -> 2 -> 2) ---

ROUND_TOPOLOGY: dict[int, list[str]] = {
    1: ["r1", "reasoner", "glm5", "kimi"],
    2: ["r1", "reasoner", "glm5"],
    3: ["r1", "reasoner"],
    4: ["r1", "reasoner"],
}

MODEL_REGISTRY: dict[str, ModelConfig] = {
    "r1": R1_MODEL,
    "reasoner": REASONER_MODEL,
    "glm5": GLM5_MODEL,
    "kimi": KIMI_MODEL,
    "sonnet": SONNET_MODEL,
}


@dataclass
class BrainConfig:
    """Runtime configuration for a Brain run."""
    rounds: int = 4
    max_evidence_items: int = 10
    max_search_queries_per_phase: int = 5
    search_after_rounds: int = 2  # Search runs after rounds 1..N (default: after R1 and R2)
    openrouter_api_key: str = ""
    anthropic_oauth_token: str = ""
    deepseek_api_key: str = ""
    zai_api_key: str = ""
    brave_api_key: str = ""
    outdir: str = "./output"
    analysis_debug_runs_remaining: int = 10  # DOD §18.4: debug sunset counter
