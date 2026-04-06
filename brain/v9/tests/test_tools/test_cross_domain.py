"""Tests for cross-domain evidence filter."""
from brain.tools.cross_domain import detect_domain, is_cross_domain


class TestDetectDomain:

    def test_security_domain(self):
        assert detect_domain("CVE-2026-1234 buffer overflow exploit RCE") == "security"

    def test_medical_domain(self):
        assert detect_domain("patient clinical diagnosis treatment medication") == "medical"

    def test_finance_domain(self):
        assert detect_domain("stock market equity trading portfolio ETF") == "finance"

    def test_infrastructure_domain(self):
        assert detect_domain("kubernetes docker deployment server database") == "infrastructure"

    def test_compliance_domain(self):
        assert detect_domain("GDPR regulation audit compliance framework") == "compliance"

    def test_unknown_domain(self):
        assert detect_domain("hello world") is None

    def test_needs_two_keywords(self):
        assert detect_domain("one exploit") is None


class TestIsCrossDomain:

    def test_medical_cross_security(self):
        assert is_cross_domain("patient clinical diagnosis treatment", "security") is True

    def test_security_ok_for_security(self):
        assert is_cross_domain("CVE vulnerability exploit authentication", "security") is False

    def test_infra_ok_for_security(self):
        assert is_cross_domain("server deployment kubernetes docker", "security") is False

    def test_compliance_ok_for_security(self):
        assert is_cross_domain("GDPR compliance audit regulation", "security") is False

    def test_unknown_domain_allowed(self):
        assert is_cross_domain("hello world", "security") is False

    def test_finance_cross_medical(self):
        assert is_cross_domain("stock market trading portfolio equity", "medical") is True
