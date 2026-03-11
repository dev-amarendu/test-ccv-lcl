import type { Repo } from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockRepos from "../mock/repos.json";

/**
 * Fetch all repositories visible to the current org.
 */
export async function fetchRepos(): Promise<Repo[]> {
  try {
    return await apiFetch<Repo[]>("/api/repos");
  } catch (err) {
    if (err instanceof MockModeActive) return mockRepos as Repo[];
    throw err;
  }
}

/**
 * Fetch a single repository by ID.
 */
export async function fetchRepo(id: string): Promise<Repo> {
  try {
    return await apiFetch<Repo>(`/api/repos/${encodeURIComponent(id)}`);
  } catch (err) {
    if (err instanceof MockModeActive) {
      const repo = (mockRepos as Repo[]).find((r) => r.id === id);
      if (!repo) throw new Error(`Mock repo not found: ${id}`);
      return repo;
    }
    throw err;
  }
}
