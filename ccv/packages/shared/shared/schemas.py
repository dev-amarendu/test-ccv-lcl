"""Pydantic schemas for API request / response bodies."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class TriggerTypeEnum(str, Enum):
    VERACODE_SYNC = "VERACODE_SYNC"
    WEBHOOK = "WEBHOOK"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class ScanStatusEnum(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── Repo ──────────────────────────────────────────────────────────────────────


class RepoResponse(BaseModel):
    id: str
    org_id: str
    name: str
    default_branch: str
    connected: bool
    model_config = {"from_attributes": True}


# ── Branch / Artifact ─────────────────────────────────────────────────────────


class BranchResponse(BaseModel):
    name: str
    is_default: bool = False


class ArtifactResponse(BaseModel):
    id: str
    scan_id: str
    artifact_uri: str
    artifact_sha256: str | None = None
    build_tool: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Scan ──────────────────────────────────────────────────────────────────────


class ManualScanRequest(BaseModel):
    repo_id: str
    branch: str
    commit_sha: str | None = None
    artifact_uri: str | None = None
    scan_type: str = "full"


class ScanResponse(BaseModel):
    id: str
    repo_id: str
    pr_id: str | None = None
    branch: str
    commit_sha: str | None = None
    trigger_type: TriggerTypeEnum
    status: ScanStatusEnum
    external_build_id: str | None = None
    external_app_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    total: int
    page: int
    page_size: int


# ── Finding ───────────────────────────────────────────────────────────────────


class FindingResponse(BaseModel):
    id: str
    scan_id: str
    cwe_id: int
    severity: str
    title: str
    file_path: str
    line: int | None = None
    fingerprint: str
    enrichment_summary: str | None = None
    enrichment_confidence: float | None = None
    raw_source_json: dict | None = None
    code_snippet_json: dict | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class FindingListResponse(BaseModel):
    items: list[FindingResponse]
    total: int
    page: int
    page_size: int


# ── Finding Analysis ──────────────────────────────────────────────────────────


class FindingAnalysisResponse(BaseModel):
    id: str
    finding_id: str
    model_name: str
    model_version: str
    root_cause: str
    risk: str
    fix_guidance: str
    code_snippet: str | None = None
    references_json: dict | None = None
    provenance_json: dict | None = None
    confidence: float | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AnalysisSummaryResponse(BaseModel):
    scan_id: str
    total_findings: int
    analyzed: int
    pending: int


# ── Schedule ──────────────────────────────────────────────────────────────────


class ScheduleCreateRequest(BaseModel):
    repo_id: str
    branch: str
    artifact_uri: str | None = None
    interval_minutes: int | None = 60
    cron_expression: str | None = None  # e.g. "0 9 * * 1" for 9am Monday


class ScheduleUpdateRequest(BaseModel):
    branch: str | None = None
    artifact_uri: str | None = None
    interval_minutes: int | None = None
    cron_expression: str | None = None
    enabled: bool | None = None


class ScheduleResponse(BaseModel):
    id: str
    repo_id: str
    branch: str
    artifact_uri: str | None = None
    interval_minutes: int | None = None
    cron_expression: str | None = None
    enabled: bool
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── KB Fix Card (exposed under /api/findings?kind=kb) ─────────────────────────


class KBFixCardResponse(BaseModel):
    id: str
    cwe_id: int
    title: str
    tags: list[str]
    summary: str | None = None
    fix_steps_json: dict | None = None
    content: str
    source: str
    approved: bool
    original_finding_id: str | None = None
    usage_count: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class KBFixCardListResponse(BaseModel):
    items: list[KBFixCardResponse]
    total: int
    page: int
    page_size: int


class KBFixCardCreateRequest(BaseModel):
    cwe_id: int
    title: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    fix_steps_json: dict | None = None
    content: str
    source: str = "CWE-660"
    original_finding_id: str | None = None


class KBFixCardUpdateRequest(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    summary: str | None = None
    fix_steps_json: dict | None = None
    content: str | None = None
    approved: bool | None = None


class KBSearchResult(BaseModel):
    cwe_id: int
    title: str
    content: str
    score: float


class KBSearchResponse(BaseModel):
    results: list[KBSearchResult]


# ── MCP ───────────────────────────────────────────────────────────────────────


class MCPCallRequest(BaseModel):
    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    caller: str | None = None
    timeout_ms: int = 30000


class MCPCallResponse(BaseModel):
    request_id: str
    tool_name: str
    ok: bool
    result: Any | None = None
    error: str | None = None
    latency_ms: float
    retriable: bool = False


# ── Webhook ───────────────────────────────────────────────────────────────────


class BitbucketPRWebhookPayload(BaseModel):
    pullrequest: dict = Field(default_factory=dict)
    repository: dict = Field(default_factory=dict)
    actor: dict = Field(default_factory=dict)


# ── Audit ─────────────────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    id: str
    request_id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    status: str
    details_json: dict | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ── Health / Version ──────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = ""
    version: str = "0.1.0"
