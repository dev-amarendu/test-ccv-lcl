// ─── Enums (string unions) ───────────────────────────────────────────────────

export type TriggerType = "push" | "pr" | "manual" | "schedule";

export type ScanStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type ArtifactMode = "latest" | "pinned" | "none";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

// ─── Core domain models ─────────────────────────────────────────────────────

export interface Repo {
  id: string;
  org_id: string;
  name: string;
  default_branch: string;
  connected: boolean;
}

export interface Branch {
  name: string;
  is_default: boolean;
}

export interface Artifact {
  id: string;
  scan_id: string;
  artifact_sha256: string;
  build_tool: string;
  created_at: string;
}

export interface Scan {
  id: string;
  repo_id: string;
  pr_id?: number | null;
  branch: string;
  commit_sha?: string | null;
  trigger_type: TriggerType;
  status: ScanStatus;
  external_build_id?: string | null;
  external_app_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  scan_id: string;
  cwe_id: number;
  severity: Severity;
  title: string;
  file_path: string;
  line?: number | null;
  fingerprint: string;
  enrichment_summary?: string | null;
  enrichment_confidence?: number | null;
  raw_source_json?: Record<string, unknown> | null;
  code_snippet_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface FindingAnalysis {
  id: string;
  finding_id: string;
  model_name: string;
  model_version: string;
  root_cause: string;
  risk: string;
  fix_guidance: string;
  code_snippet?: string;
  references_json?: Record<string, unknown> | null;
  provenance_json?: Record<string, unknown> | null;
  confidence?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Schedule {
  id: string;
  repo_id: string;
  branch: string;
  artifact_mode: ArtifactMode;
  interval_minutes: number;
  enabled: boolean;
  next_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface KBFixCard {
  id: string;
  cwe_id: number;
  title: string;
  tags: string[];
  summary?: string | null;
  fix_steps_json?: Record<string, unknown> | null;
  content: string;
  source: string;
  approved: boolean;
  original_finding_id?: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

// ─── Generic paginated response ──────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Request / filter helpers ────────────────────────────────────────────────

export interface ScanFilters {
  repo_id?: string;
  branch?: string;
  status?: ScanStatus;
  trigger_type?: TriggerType;
  page?: number;
  page_size?: number;
}

export interface FindingFilters {
  scan_id?: string;
  severity?: Severity;
  cwe_id?: number;
  kind?: "finding" | "kb";
  page?: number;
  page_size?: number;
}

export interface ManualScanRequest {
  repo_id: string;
  branch: string;
  commit_sha?: string;
}

export interface CreateScheduleRequest {
  repo_id: string;
  branch: string;
  artifact_mode: ArtifactMode;
  interval_minutes: number;
  enabled?: boolean;
}

export interface UpdateScheduleRequest {
  branch?: string;
  artifact_mode?: ArtifactMode;
  interval_minutes?: number;
  enabled?: boolean;
}

export interface CreateKBCardRequest {
  cwe_id: number;
  title: string;
  tags: string[];
  summary?: string;
  fix_steps_json?: Record<string, unknown>;
  content: string;
  source: string;
}

export interface UpdateKBCardRequest {
  title?: string;
  tags?: string[];
  summary?: string | null;
  fix_steps_json?: Record<string, unknown> | null;
  content?: string;
  source?: string;
  approved?: boolean;
}
