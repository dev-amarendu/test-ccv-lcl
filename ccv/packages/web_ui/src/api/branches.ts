import type { Branch } from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockBranches from "../mock/branches.json";

/**
 * Fetch branches for a given repository.
 */
export async function fetchBranches(repoId: string): Promise<Branch[]> {
  try {
    return await apiFetch<Branch[]>("/api/branches", {
      params: { repoId },
    });
  } catch (err) {
    if (err instanceof MockModeActive) return mockBranches as Branch[];
    throw err;
  }
}
