import type {
  Schedule,
  CreateScheduleRequest,
  UpdateScheduleRequest,
} from "./types";
import { apiFetch, MockModeActive } from "./client";

import mockSchedules from "../mock/schedules.json";

/**
 * List all scan schedules.
 */
export async function fetchSchedules(): Promise<Schedule[]> {
  try {
    return await apiFetch<Schedule[]>("/api/schedules");
  } catch (err) {
    if (err instanceof MockModeActive) return mockSchedules as Schedule[];
    throw err;
  }
}

/**
 * Create a new scan schedule.
 */
export async function createSchedule(
  req: CreateScheduleRequest,
): Promise<Schedule> {
  try {
    return await apiFetch<Schedule>("/api/schedules", {
      method: "POST",
      body: req,
    });
  } catch (err) {
    if (err instanceof MockModeActive) {
      const now = new Date().toISOString();
      return {
        id: crypto.randomUUID(),
        repo_id: req.repo_id,
        branch: req.branch,
        // artifact_uri removed from frontend model — keep metadata minimal
        interval_minutes: req.interval_minutes,
        enabled: req.enabled ?? true,
        next_run_at: null,
        created_at: now,
        updated_at: now,
      };
    }
    throw err;
  }
}

/**
 * Update an existing scan schedule.
 */
export async function updateSchedule(
  id: string,
  req: UpdateScheduleRequest,
): Promise<Schedule> {
  try {
    return await apiFetch<Schedule>(
      `/api/schedules/${encodeURIComponent(id)}`,
      { method: "PATCH", body: req },
    );
  } catch (err) {
    if (err instanceof MockModeActive) {
      const existing = (mockSchedules as Schedule[]).find((s) => s.id === id);
      if (!existing) throw new Error(`Mock schedule not found: ${id}`);
      const now = new Date().toISOString();
      return { ...existing, ...req, updated_at: now };
    }
    throw err;
  }
}

/**
 * Immediately execute a scheduled scan.
 */
export async function runScheduleNow(id: string): Promise<void> {
  try {
    await apiFetch<void>(
      `/api/schedules/${encodeURIComponent(id)}/run`,
      { method: "POST" },
    );
  } catch (err) {
    if (err instanceof MockModeActive) return; // no-op in mock
    throw err;
  }
}

/**
 * Delete a scan schedule.
 */
export async function deleteSchedule(id: string): Promise<void> {
  try {
    await apiFetch<void>(
      `/api/schedules/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    );
  } catch (err) {
    if (err instanceof MockModeActive) return; // no-op in mock
    throw err;
  }
}