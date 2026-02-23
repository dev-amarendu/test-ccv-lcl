"""Test finding normalization — raw Veracode JSON -> internal Finding shape."""

from __future__ import annotations

import uuid

import pytest

from scan_runner.normalize import normalize_findings
from shared.utils import stable_fingerprint


SAMPLE_VERACODE_V2_RESPONSE = {
    "_embedded": {
        "findings": [
            {
                "finding_details": {
                    "cwe": {"id": 79, "name": "Improper Neutralization of Input During Web Page Generation"},
                    "severity": 4,
                    "finding_category": {"name": "Cross-Site Scripting (XSS)"},
                    "file_path": "com/example/web/UserController.java",
                    "file_line_number": 42,
                },
            },
            {
                "finding_details": {
                    "cwe": {"id": 89, "name": "SQL Injection"},
                    "severity": 5,
                    "finding_category": {"name": "SQL Injection"},
                    "file_path": "com/example/dao/UserDAO.java",
                    "file_line_number": 105,
                },
            },
        ]
    }
}

SAMPLE_FLAT_FORMAT = {
    "findings": [
        {
            "cwe_id": 79,
            "severity": "High",
            "title": "XSS Vulnerability",
            "file_path": "src/main/java/App.java",
            "line": 10,
        }
    ]
}


@pytest.fixture
def scan_id() -> str:
    return str(uuid.uuid4())


class TestNormalizeFindings:
    def test_v2_format_produces_correct_count(self, scan_id: str):
        findings = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        assert len(findings) == 2

    def test_v2_finding_has_required_fields(self, scan_id: str):
        findings = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        f = findings[0]
        assert f.scan_id == scan_id
        assert f.cwe_id == 79
        assert f.severity == "High"
        assert f.title == "Cross-Site Scripting (XSS)"
        assert f.file_path == "com/example/web/UserController.java"
        assert f.line == 42
        assert f.fingerprint
        assert f.id

    def test_fingerprint_is_stable(self, scan_id: str):
        f1 = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        f2 = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        assert f1[0].fingerprint == f2[0].fingerprint

    def test_fingerprint_matches_manual_computation(self, scan_id: str):
        findings = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        expected = stable_fingerprint("79", "com/example/web/UserController.java", "42", "Cross-Site Scripting (XSS)")
        assert findings[0].fingerprint == expected

    def test_flat_format_works(self, scan_id: str):
        findings = normalize_findings(scan_id, SAMPLE_FLAT_FORMAT)
        assert len(findings) == 1
        assert findings[0].cwe_id == 79

    def test_empty_results(self, scan_id: str):
        findings = normalize_findings(scan_id, {})
        assert findings == []

    def test_severity_mapping(self, scan_id: str):
        findings = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        assert findings[0].severity == "High"      # severity 4
        assert findings[1].severity == "Very High"  # severity 5

    def test_raw_source_json_preserved(self, scan_id: str):
        findings = normalize_findings(scan_id, SAMPLE_VERACODE_V2_RESPONSE)
        assert findings[0].raw_source_json is not None
