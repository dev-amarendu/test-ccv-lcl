"""Pydantic models representing Firestore document shapes for CCV.

These replace the SQLAlchemy ORM models.  Each model can serialize
to/from a plain dict suitable for ``DocumentReference.set()`` / snapshot.to_dict().
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────


class TriggerType(str, enum.Enum):
    VERACODE_SYNC = "VERACODE_SYNC"
    WEBHOOK = "WEBHOOK"
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class ScanStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobType(str, enum.Enum):
    RUN_SCAN = "RUN_SCAN"
    ANALYZE_FINDING = "ANALYZE_FINDING"
    EMBED_KB = "EMBED_KB"
    SYNC_VERACODE = "SYNC_VERACODE"


class ArtifactMode(str, enum.Enum):
    AUTO = "AUTO"
    EXPLICIT_URI = "EXPLICIT_URI"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Document Models ──────────────────────────────────────────────────────────


class OrganizationDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> OrganizationDoc:
        return cls(**doc_dict)


class RepoDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    org_id: str
    name: str
    default_branch: str = "main"
    connected: bool = False
    created_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> RepoDoc:
        return cls(**doc_dict)


class ScanDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    repo_id: str
    pr_id: str | None = None
    branch: str
    commit_sha: str | None = None
    trigger_type: TriggerType
    status: ScanStatus = ScanStatus.QUEUED
    external_build_id: str | None = None
    external_app_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> ScanDoc:
        return cls(**doc_dict)


class ScanArtifactDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    scan_id: str
    artifact_uri: str
    artifact_sha256: str | None = None
    build_tool: str = "maven"
    created_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> ScanArtifactDoc:
        return cls(**doc_dict)


class FindingDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    scan_id: str
    cwe_id: int
    severity: str
    title: str
    file_path: str
    line: int | None = None
    fingerprint: str
    gcs_ref: dict | None = None  # Optional pointer to raw SCA in GCS: { "uri": "gs://...", "index_in_blob": 12 }
    enrichment_summary: str | None = None
    enrichment_confidence: float | None = None
    raw_source_json: dict | None = None
    code_snippet_json: dict | None = None
    created_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> FindingDoc:
        return cls(**doc_dict)


class FindingAnalysisDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
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
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> FindingAnalysisDoc:
        return cls(**doc_dict)


class ScheduleDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    repo_id: str
    branch: str
    artifact_uri: str | None = None
    interval_minutes: int | None = 60
    cron_expression: str | None = None
    enabled: bool = True
    next_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> ScheduleDoc:
        return cls(**doc_dict)


class AuditLogDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    request_id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    status: str
    details_json: dict | None = None
    created_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> AuditLogDoc:
        return cls(**doc_dict)


class VeracodeSyncStateDoc(BaseModel):
    last_synced_at: datetime | None = None
    last_seen_build_id: str | None = None

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> VeracodeSyncStateDoc:
        return cls(**doc_dict)


class KBFixCardDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    cwe_id: int
    title: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    fix_steps_json: dict | None = None
    content: str
    source: str = "CWE-660"
    content_hash: str
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_dim: int | None = None
    approved: bool = True
    original_finding_id: str | None = None
    usage_count: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        d = self.model_dump()
        # Don't store embedding in Firestore — it goes to Vertex AI Vector Search
        d.pop("embedding", None)
        return d

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> KBFixCardDoc:
        return cls(**doc_dict)


class UserDoc(BaseModel):
    id: str = Field(default_factory=_new_id)
    email: str
    roles: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)

    def to_firestore_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_firestore_doc(cls, doc_dict: dict[str, Any]) -> UserDoc:
        return cls(**doc_dict)
