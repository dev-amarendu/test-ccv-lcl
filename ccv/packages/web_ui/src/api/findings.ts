import type {
  Finding,
  FindingAnalysis,
  PaginatedResponse,
  FindingFilters,
} from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockFindings from "../mock/findings.json";

/**
 * List findings with optional filters and pagination.
 */
export async function fetchFindings(
  filters?: FindingFilters,
): Promise<PaginatedResponse<Finding>> {
  try {
    return await apiFetch<PaginatedResponse<Finding>>("/api/findings", {
      params: filters as Record<string, string | number | boolean | undefined>,
    });
  } catch (err) {
    if (err instanceof MockModeActive)
      return mockFindings as unknown as PaginatedResponse<Finding>;
    throw err;
  }
}

/**
 * Fetch a single finding by ID.
 */
export async function fetchFinding(id: string): Promise<Finding> {
  try {
    return await apiFetch<Finding>(
      `/api/findings/${encodeURIComponent(id)}`,
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      const finding = (
        mockFindings as unknown as PaginatedResponse<Finding>
      ).items.find((f) => f.id === id);
      if (!finding) throw new Error(`Mock finding not found: ${id}`);
      return finding;
    }
    throw err;
  }
}

/**
 * Fetch the AI-generated analysis for a finding.
 */
export async function fetchFindingAnalysis(
  id: string,
): Promise<FindingAnalysis> {
  try {
    return await apiFetch<FindingAnalysis>(
      `/api/findings/${encodeURIComponent(id)}/analysis`,
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      // Return a synthetic analysis for mock mode
      const now = new Date().toISOString();
      return {
        id: crypto.randomUUID(),
        finding_id: id,
        model_name: "gpt-4o",
        model_version: "2025-11-20",
        root_cause:
          "User-controlled input is concatenated directly into the SQL query string without parameterisation or sanitisation.",
        risk: "An attacker could exfiltrate or modify database contents, escalate privileges, or execute administrative operations on the database server.",
        fix_guidance:
          "Replace string concatenation with parameterised queries using the framework's built-in prepared-statement API. Validate and sanitise all user inputs at the boundary.",
        references_json: {
          owasp: "https://owasp.org/Top10/A03_2021-Injection/",
          cwe: "https://cwe.mitre.org/data/definitions/89.html",
        },
        provenance_json: null,
        confidence: 0.92,
        created_at: now,
        updated_at: now,
      };
    }
    throw err;
  }
}

/**
 * Request a new AI analysis for a finding.
 */
export async function requestAnalysis(findingId: string): Promise<void> {
  try {
    await apiFetch<void>(
      `/api/findings/${encodeURIComponent(findingId)}/analysis`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof MockModeActive) return; // no-op in mock
    throw err;
  }
}
