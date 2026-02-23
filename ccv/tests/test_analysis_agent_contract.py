"""Test Analysis Agent contract — ADK agent instruction, tools, response parsing."""

from __future__ import annotations

import json

import pytest

from analysis_agent.prompts import (
    AGENT_INSTRUCTION,
    AnalysisOutput,
    parse_analysis_response,
)
from analysis_agent.agent import _build_finding_message
from analysis_agent.tools import lookup_kb_fix_card


VALID_LLM_RESPONSE = json.dumps({
    "root_cause": "User input is concatenated directly into the SQL query string without parameterization.",
    "risk": "An attacker can inject arbitrary SQL to read, modify, or delete data.",
    "fix_guidance": "1. Use parameterized queries. 2. Apply input validation. 3. Use ORM query builders.",
    "cwe_references": ["CWE-89: SQL Injection"],
})


class TestAgentInstruction:
    """Verify the ADK agent instruction contains required elements."""

    def test_instruction_references_kb_tool(self):
        assert "lookup_kb_fix_card" in AGENT_INSTRUCTION

    def test_instruction_specifies_json_schema(self):
        assert "root_cause" in AGENT_INSTRUCTION
        assert "risk" in AGENT_INSTRUCTION
        assert "fix_guidance" in AGENT_INSTRUCTION
        assert "cwe_references" in AGENT_INSTRUCTION

    def test_instruction_contains_workflow(self):
        assert "WORKFLOW" in AGENT_INSTRUCTION

    def test_instruction_forbids_code_patches(self):
        assert "Do NOT generate code patches" in AGENT_INSTRUCTION


class TestBuildFindingMessage:
    """Verify the user message builder for the ADK agent."""

    def _make_mock_finding(self, **overrides):
        """Create a minimal mock finding object."""

        class MockFinding:
            id = "00000000-0000-0000-0000-000000000001"
            cwe_id = 89
            severity = "High"
            title = "SQL Injection"
            file_path = "com/example/dao/UserDAO.java"
            line = 105
            code_snippet_json = None

        f = MockFinding()
        for k, v in overrides.items():
            setattr(f, k, v)
        return f

    def test_message_contains_cwe(self):
        finding = self._make_mock_finding()
        msg = _build_finding_message(finding)
        assert "CWE-89" in msg
        assert "SQL Injection" in msg

    def test_message_contains_file_path(self):
        finding = self._make_mock_finding()
        msg = _build_finding_message(finding)
        assert "UserDAO.java" in msg

    def test_message_includes_line(self):
        finding = self._make_mock_finding(line=42)
        msg = _build_finding_message(finding)
        assert "Line: 42" in msg

    def test_message_includes_code_snippet(self):
        snippet_json = {"snippet": 'String q = "SELECT * FROM users WHERE id=" + input;'}
        finding = self._make_mock_finding(code_snippet_json=snippet_json)
        msg = _build_finding_message(finding)
        assert "SELECT * FROM users" in msg

    def test_message_omits_line_when_none(self):
        finding = self._make_mock_finding(line=None)
        msg = _build_finding_message(finding)
        assert "Line:" not in msg


class TestParseResponse:
    """Verify response parsing and validation."""

    def test_valid_json_parsed(self):
        output = parse_analysis_response(VALID_LLM_RESPONSE)
        assert isinstance(output, AnalysisOutput)
        assert "SQL" in output.root_cause

    def test_markdown_wrapped_json(self):
        wrapped = f"```json\n{VALID_LLM_RESPONSE}\n```"
        output = parse_analysis_response(wrapped)
        assert isinstance(output, AnalysisOutput)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_analysis_response("This is not JSON")

    def test_missing_fields_raises(self):
        partial = json.dumps({"root_cause": "something"})
        with pytest.raises(ValueError, match="does not match schema"):
            parse_analysis_response(partial)


class TestLookupKBTool:
    """Verify the KB lookup tool contract (return format)."""

    def test_tool_returns_not_found_for_unknown_cwe(self):
        """With no DB or KB service, tool should return not_found."""
        result = lookup_kb_fix_card(cwe_id=999999)
        assert result["status"] == "not_found"
        assert result["cwe_id"] == 999999

    def test_tool_has_proper_docstring(self):
        """ADK uses the docstring to generate the tool schema."""
        assert lookup_kb_fix_card.__doc__ is not None
        assert "CWE" in lookup_kb_fix_card.__doc__

    def test_tool_has_type_hints(self):
        """ADK uses type hints to generate the parameter schema."""
        annotations = lookup_kb_fix_card.__annotations__
        assert "cwe_id" in annotations
        assert annotations["cwe_id"] is int
        assert annotations["return"] is dict


class TestAnalysisAgentContract:
    """End-to-end contract: build message → mock LLM response → parse."""

    @pytest.mark.asyncio
    async def test_agent_pipeline_contract(self):
        finding = TestBuildFindingMessage()._make_mock_finding(
            cwe_id=89,
            severity="High",
            title="SQL Injection",
            file_path="UserDAO.java",
            line=105,
            code_snippet_json={"snippet": "stmt.execute(userInput)"},
        )
        msg = _build_finding_message(finding)
        assert "CWE-89" in msg

        # Simulate LLM response and parse
        output = parse_analysis_response(VALID_LLM_RESPONSE)
        assert output.root_cause
        assert output.risk
        assert output.fix_guidance
        data = output.model_dump()
        assert all(
            k in data
            for k in ("root_cause", "risk", "fix_guidance", "cwe_references")
        )
