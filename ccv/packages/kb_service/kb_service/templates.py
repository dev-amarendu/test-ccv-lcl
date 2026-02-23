"""Fix Card template generator helpers.

Generates deterministic Fix Card content from CWE data.
"""

from __future__ import annotations


def generate_fix_card_content(
    cwe_id: int,
    cwe_name: str,
    description: str = "",
    extended_description: str = "",
    potential_mitigations: str = "",
    languages: str = "Java",
) -> str:
    """Generate a structured Fix Card content string from CWE data.

    The output is a deterministic plain-text document suitable for
    embedding and retrieval.
    """
    sections = [
        f"# CWE-{cwe_id}: {cwe_name}",
        "",
        "## Overview",
        description or f"This weakness relates to CWE-{cwe_id} ({cwe_name}).",
        "",
    ]

    if extended_description:
        sections.extend([
            "## Extended Description",
            extended_description,
            "",
        ])

    sections.extend([
        "## Applicable Languages",
        languages,
        "",
    ])

    if potential_mitigations:
        sections.extend([
            "## Recommended Mitigations",
            potential_mitigations,
            "",
        ])

    sections.extend([
        "## Fix Guidance (Java)",
        f"When addressing CWE-{cwe_id} in Java applications:",
        "",
        "1. **Input Validation**: Validate and sanitize all external inputs before processing.",
        "2. **Secure Coding Practices**: Follow OWASP secure coding guidelines relevant to this weakness.",
        "3. **Framework Support**: Leverage built-in security features of your framework (Spring Security, etc.).",
        "4. **Testing**: Add unit tests that specifically cover the vulnerable code path.",
        "5. **Code Review**: Ensure peer review focuses on the specific weakness pattern.",
        "",
        "## References",
        f"- https://cwe.mitre.org/data/definitions/{cwe_id}.html",
        f"- OWASP guidance related to CWE-{cwe_id}",
    ])

    return "\n".join(sections)
