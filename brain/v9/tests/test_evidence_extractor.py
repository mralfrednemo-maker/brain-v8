"""Tests for LLM-based evidence extraction."""
import pytest

from brain.evidence_extractor import parse_extracted_facts, EXTRACTION_PROMPT


class TestParseExtractedFacts:

    def test_parses_structured_facts(self):
        text = """FACT-1: The vulnerability was disclosed on 2026-01-15
FACT-2: CVSS score is 9.8 (critical)
FACT-3: Affects versions 2.0 through 2.5"""
        facts = parse_extracted_facts(text)
        assert len(facts) == 3
        assert "2026-01-15" in facts[0]["fact"]
        assert "9.8" in facts[1]["fact"]

    def test_parses_numbered_format(self):
        text = """1. The regulation requires 72-hour notification
2. Fines up to 4% of global revenue
3. Applies to all EU data processors"""
        facts = parse_extracted_facts(text)
        assert len(facts) == 3

    def test_empty_input(self):
        facts = parse_extracted_facts("")
        assert facts == []

    def test_none_response(self):
        facts = parse_extracted_facts("NONE")
        assert facts == []

    def test_none_case_insensitive(self):
        facts = parse_extracted_facts("none")
        assert facts == []

    def test_strips_markdown(self):
        text = """**FACT-1:** The breach affected 500,000 users
- FACT-2: Reported to authorities within 48 hours"""
        facts = parse_extracted_facts(text)
        assert len(facts) >= 1
        assert "500,000" in facts[0]["fact"]

    def test_bullet_format(self):
        text = """- The server had 99.9% uptime in 2025
- Revenue exceeded $50 million"""
        facts = parse_extracted_facts(text)
        assert len(facts) == 2

    def test_short_bullets_skipped(self):
        text = """- yes
- The company reported $2.5B in quarterly revenue"""
        facts = parse_extracted_facts(text)
        assert len(facts) == 1

    def test_returns_dict_structure(self):
        text = "FACT-1: Something specific happened"
        facts = parse_extracted_facts(text)
        assert len(facts) == 1
        assert "fact" in facts[0]
        assert isinstance(facts[0]["fact"], str)


class TestExtractionPrompt:

    def test_prompt_contains_instructions(self):
        assert "Extract" in EXTRACTION_PROMPT
        assert "FACT" in EXTRACTION_PROMPT
        assert "{url}" in EXTRACTION_PROMPT
        assert "{content}" in EXTRACTION_PROMPT

    def test_prompt_formats_correctly(self):
        formatted = EXTRACTION_PROMPT.format(url="https://example.com", content="page text")
        assert "https://example.com" in formatted
        assert "page text" in formatted
