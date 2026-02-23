import type {
  Scan,
  PaginatedResponse,
  ScanFilters,
  ManualScanRequest,
} from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockScans from "../mock/scans.json";

/**
 * List scans with optional filters and pagination.
 */
export async function fetchScans(
  filters?: ScanFilters,
): Promise<PaginatedResponse<Scan>> {
  try {
    return await apiFetch<PaginatedResponse<Scan>>("/api/scans/manual", {
      params: filters as Record<string, string | number | boolean | undefined>,
    });
  } catch (err) {
    if (err instanceof MockModeActive)
      return mockScans as unknown as PaginatedResponse<Scan>;
    throw err;
  }
}

/**
 * Get a single scan by ID.
 */
export async function fetchScan(id: string): Promise<Scan> {
  try {
    return await apiFetch<Scan>(
      `/api/scans/manual/${encodeURIComponent(id)}`,
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      const scan = (mockScans as unknown as PaginatedResponse<Scan>).items.find(
        (s) => s.id === id,
      );
      if (!scan) throw new Error(`Mock scan not found: ${id}`);
      return scan;
    }
    throw err;
  }
}

/**
 * Trigger a new manual scan.
 */
export async function triggerManualScan(
  req: ManualScanRequest,
): Promise<Scan> {
  try {
    return await apiFetch<Scan>("/api/scans/manual", {
      method: "POST",
      body: req,
    });
  } catch (err) {
    if (err instanceof MockModeActive) {
      // Return a synthetic queued scan for mock mode
      const now = new Date().toISOString();
      return {
        id: crypto.randomUUID(),
        repo_id: req.repo_id,
        branch: req.branch,
        commit_sha: req.commit_sha ?? null,
        trigger_type: "manual",
        status: "queued",
        pr_id: null,
        external_build_id: null,
        external_app_id: null,
        started_at: null,
        finished_at: null,
        error_message: null,
        created_at: now,
        updated_at: now,
      };
    }
    throw err;
  }
}

/**
 * Re-run an existing scan.
 */
export async function rerunScan(id: string): Promise<Scan> {
  try {
    return await apiFetch<Scan>(
      `/api/scans/manual/${encodeURIComponent(id)}/rerun`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      const original = (
        mockScans as unknown as PaginatedResponse<Scan>
      ).items.find((s) => s.id === id);
      if (!original) throw new Error(`Mock scan not found: ${id}`);
      const now = new Date().toISOString();
      return { ...original, id: crypto.randomUUID(), status: "queued", created_at: now, updated_at: now };
    }
    throw err;
  }
}

/**
 * Trigger a repository sync (re-imports repos/branches from the SCM).
 */
export async function triggerSync(): Promise<void> {
  try {
    await apiFetch<void>("/api/repos/sync", { method: "POST" });
  } catch (err) {
    if (err instanceof MockModeActive) return; // no-op in mock
    throw err;
  }
}
