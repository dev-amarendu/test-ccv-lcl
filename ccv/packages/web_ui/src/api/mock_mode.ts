const MOCK_MODE_KEY = "ccv_mock_mode";

/**
 * Returns true when mock mode is enabled via localStorage.
 */
export function isMockMode(): boolean {
  try {
    return localStorage.getItem(MOCK_MODE_KEY) === "true";
  } catch {
    return false;
  }
}

/**
 * Enable or disable mock mode by writing to localStorage.
 */
export function setMockMode(on: boolean): void {
  try {
    if (on) {
      localStorage.setItem(MOCK_MODE_KEY, "true");
    } else {
      localStorage.removeItem(MOCK_MODE_KEY);
    }
  } catch {
    // localStorage may be unavailable (SSR, sandboxed iframe, etc.)
  }
}

export type Env = "LOCAL" | "DEV" | "PROD";

/**
 * Read the deploy environment from the Vite env variable.
 * Defaults to "LOCAL" when unset.
 */
export function getEnv(): Env {
  const raw = (import.meta.env.VITE_ENV ?? "LOCAL") as string;
  const upper = raw.toUpperCase() as Env;
  if (upper === "DEV" || upper === "PROD") return upper;
  return "LOCAL";
}

/**
 * Mock mode should only be toggleable in local development.
 */
export function isMockAllowed(): boolean {
  return getEnv() === "LOCAL";
}
