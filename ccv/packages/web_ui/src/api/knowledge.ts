import type {
  KBFixCard,
  CreateKBCardRequest,
  UpdateKBCardRequest,
  PaginatedResponse,
} from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockKB from "../mock/kb.json";

/**
 * Fetch all Knowledge Base fix cards.
 */
export async function fetchKBCards(): Promise<KBFixCard[]> {
  try {
    const res = await apiFetch<PaginatedResponse<KBFixCard>>("/api/findings", {
      params: { kind: "kb" },
    });
    return res.items;
  } catch (err) {
    if (err instanceof MockModeActive) return mockKB as unknown as KBFixCard[];
    throw err;
  }
}

/**
 * Fetch a single KB fix card by ID.
 */
export async function fetchKBCard(id: string): Promise<KBFixCard> {
  try {
    return await apiFetch<KBFixCard>(
      `/api/findings/kb/${encodeURIComponent(id)}`,
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      const card = (mockKB as unknown as KBFixCard[]).find((c) => c.id === id);
      if (!card) throw new Error(`Mock KB card not found: ${id}`);
      return card;
    }
    throw err;
  }
}

/**
 * Create a new KB fix card.
 */
export async function createKBCard(
  req: CreateKBCardRequest,
): Promise<KBFixCard> {
  try {
    return await apiFetch<KBFixCard>("/api/findings/kb", {
      method: "POST",
      body: req,
    });
  } catch (err) {
    if (err instanceof MockModeActive) {
      const now = new Date().toISOString();
      return {
        id: crypto.randomUUID(),
        cwe_id: req.cwe_id,
        title: req.title,
        tags: req.tags,
        summary: req.summary ?? null,
        fix_steps_json: req.fix_steps_json ?? null,
        content: req.content,
        source: req.source,
        approved: false,
        original_finding_id: null,
        usage_count: 0,
        content_hash: `mock-${req.cwe_id}`,
        created_at: now,
        updated_at: now,
      };
    }
    throw err;
  }
}

/**
 * Update an existing KB fix card.
 */
export async function updateKBCard(
  id: string,
  req: UpdateKBCardRequest,
): Promise<KBFixCard> {
  try {
    return await apiFetch<KBFixCard>(
      `/api/findings/kb/${encodeURIComponent(id)}`,
      { method: "PATCH", body: req },
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      const existing = (mockKB as unknown as KBFixCard[]).find((c) => c.id === id);
      if (!existing) throw new Error(`Mock KB card not found: ${id}`);
      const now = new Date().toISOString();
      return { ...existing, ...req, updated_at: now } as KBFixCard;
    }
    throw err;
  }
}
