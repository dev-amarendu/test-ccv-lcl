import type { Artifact } from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockArtifacts from "../mock/artifacts.json";

/**
 * Fetch artifacts for a given repo + branch combination.
 */
export async function fetchArtifacts(
  repoId: string,
  branch: string,
): Promise<Artifact[]> {
  try {
    return await apiFetch<Artifact[]>("/api/artifacts", {
      params: { repoId, branch },
    });
  } catch (err) {
    if (err instanceof MockModeActive) return mockArtifacts as Artifact[];
    throw err;
  }
}
