import { isMockMode } from "./mock_mode";

// ─── Custom error class ──────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly body?: unknown,
  ) {
    super(`API ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

// Sentinel error thrown when mock mode is active so each module can handle it.
export class MockModeActive extends Error {
  constructor() {
    super("Mock mode is active – use local fixtures");
    this.name = "MockModeActive";
  }
}

// ─── Base fetch wrapper ──────────────────────────────────────────────────────

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
}

/**
 * Low-level fetch wrapper used by every API module.
 *
 * - When mock mode is ON the function throws `MockModeActive` so the caller
 *   can short-circuit to its mock-data path.
 * - Automatically serialises a JSON body and sets appropriate headers.
 * - Appends query-string parameters from `options.params`.
 */
export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  // Short-circuit when mock mode is enabled
  if (isMockMode()) {
    throw new MockModeActive();
  }

  const { body, params, headers: extraHeaders, ...rest } = options;

  // Build URL with query params
  let url = path;
  if (params) {
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) qs.set(key, String(value));
    }
    const search = qs.toString();
    if (search) url += `?${search}`;
  }

  const headers: HeadersInit = {
    Accept: "application/json",
    ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(extraHeaders as Record<string, string> | undefined),
  };

  const response = await fetch(url, {
    ...rest,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let parsed: unknown;
    try {
      parsed = await response.json();
    } catch {
      // body may not be JSON
    }
    throw new ApiError(response.status, response.statusText, parsed);
  }

  // 204 No Content – return undefined cast as T (for void returns)
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return (await response.json()) as T;
}
