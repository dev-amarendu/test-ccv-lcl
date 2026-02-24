"""Centralised settings loaded from environment / .env file."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Firestore ─────────────────────────────
    firestore_project_id: str = ""
    firestore_database: str = "(default)"

    # ── Cloud Pub/Sub ─────────────────────────
    pubsub_project_id: str = ""
    pubsub_topic_analyze_finding: str = "ccv-analyze-finding"
    pubsub_topic_run_scan: str = "ccv-run-scan"
    pubsub_topic_sync_veracode: str = "ccv-sync-veracode"
    pubsub_topic_embed_kb: str = "ccv-embed-kb"

    # ── Vertex AI Vector Search ───────────────
    vector_search_index_endpoint: str = ""
    vector_search_index_id: str = ""
    vector_search_deployed_index_id: str = ""

    # ── API ───────────────────────────────────
    api_host: str = "0.0.0.0"
    # Change default API port to avoid local port conflicts (see README)
    api_port: int = 8008
    api_log_level: str = "info"
    api_base_url: str = "http://localhost:8008"

    # ── MCP ───────────────────────────────────
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    mcp_internal_token: str = "changeme"
    mcp_base_url: str = "http://localhost:8001"

    # ── Veracode ──────────────────────────────
    veracode_analysis_base: str = "https://analysiscenter.veracode.com"
    veracode_rest_base: str = "https://api.veracode.com"
    veracode_api_key_id: str = ""
    veracode_api_key_secret: str = ""
    veracode_app_id: str = ""

    # ── Veracode Periodic Sync ────────────────
    veracode_sync_interval_seconds: int = 300

    # ── Bitbucket (optional) ──────────────────
    bitbucket_enabled: bool = False
    bitbucket_base_url: str = ""
    bitbucket_token: str = ""

    # ── Git / Repo Fetcher ────────────────────
    repo_clone_url_template: str = ""
    git_username: str = ""
    git_password_or_token: str = ""

    # ── Google Cloud / Vertex AI ──────────────
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True

    # ── LLM / Embeddings ─────────────────────
    llm_model: str = "gemini-2.0-flash"
    embedding_model: str = "gemini-embedding-001"
    embed_dim: int = 3072

    # ── KB ────────────────────────────────────
    cwe_660_csv_path: str = ""

    # ── Feature flags ─────────────────────────
    backend_mock_mode: bool = False

    # ── Scan Runner ───────────────────────────
    scan_poll_interval_seconds: int = 30
    scan_poll_max_attempts: int = 120

    # ── Analysis Agent ────────────────────────
    analysis_poll_interval_seconds: int = 5
    # GCS bucket used to store large raw Veracode payloads (SCA artifacts)
    gcs_raw_reports_bucket: str = ""
    # Threshold (bytes) above which SCA payloads are uploaded to GCS instead of embedded in Firestore
    sca_inline_size_limit: int = 800000


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached singleton settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
