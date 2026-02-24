import type { Repo } from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockRepos from "../mock/repos.json";

/**
 * Response shape from GET /api/repos
 */
interface ReposApiResponse {
  repositories: string[];
}

/**
 * Fetch all repositories from Bitbucket (via backend).
 * The API returns { repositories: ["slug1", "slug2", ...] }.
 * We convert each slug into a Repo object for the UI.
 */
export async function fetchRepos(): Promise<Repo[]> {
  try {
    const data = await apiFetch<ReposApiResponse>("/api/repos");
    return (data.repositories || []).map((slug) => ({
      id: slug,
      org_id: "",
      name: slug,
      default_branch: "main",
      connected: true,
      created_at: "",
    }));
  } catch (err) {
    if (err instanceof MockModeActive) return mockRepos as Repo[];
    throw err;
  }
}

/**
 * Fetch a single repository by slug.
 * Since the API only returns a list, we fetch all and filter.
 */
export async function fetchRepo(id: string): Promise<Repo> {
  try {
    const repos = await fetchRepos();
    const repo = repos.find((r) => r.id === id);
    if (!repo) throw new Error(`Repo not found: ${id}`);
    return repo;
  } catch (err) {
    if (err instanceof MockModeActive) {
      const repo = (mockRepos as Repo[]).find((r) => r.id === id);
      if (!repo) throw new Error(`Mock repo not found: ${id}`);
      return repo;
    }
    throw err;
  }
}
