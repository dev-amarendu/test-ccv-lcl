"""Download and extract a repository branch for scanning.

Uses the Bitbucket Server REST API archive endpoint with Bearer/Token auth
(same pattern as repos.py / branches.py).
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


# ── Bitbucket auth (same pattern as repos.py / branches.py) ──────────────────


def _auth_headers(token: str, scheme: str) -> dict:
    return {"Authorization": f"{scheme} {token}"}


def _get_stream_with_token(
    url: str, token: str, params: dict, verify_ssl: bool = True
) -> requests.Response:
    """Try Bearer first, then Token. Returns the best response."""
    last_resp = None
    for scheme in ("Bearer", "Token"):
        resp = requests.get(
            url,
            headers=_auth_headers(token, scheme),
            params=params,
            stream=True,
            allow_redirects=True,
            timeout=300,
            verify=verify_ssl,
        )
        last_resp = resp
        if resp.status_code in (401, 403):
            continue
        return resp
    return last_resp  # type: ignore[return-value]


def _safe_filename(name: str) -> str:
    """Keep the filename filesystem-safe."""
    name = name.strip().replace("\n", " ")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "archive.zip"


def _filename_from_cd(content_disposition: str | None) -> str | None:
    """Extract filename from Content-Disposition header."""
    if not content_disposition:
        return None
    m = re.search(
        r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?',
        content_disposition,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


# ── Download ZIP from Bitbucket ──────────────────────────────────────────────


def _download_repo_zip(
    repo_id: str,
    branch: str,
    out_dir: str,
    base_url: str,
    project: str,
    token: str,
    insecure: bool = False,
) -> Path:
    """Download a repository archive as a ZIP file from Bitbucket Server.

    Returns the path to the downloaded ZIP file.
    """
    base_url = base_url.rstrip("/")
    archive_url = f"{base_url}/rest/api/1.0/projects/{project}/repos/{repo_id}/archive"

    params = {"format": "zip"}
    if branch:
        params["at"] = branch

    logger.info("repo_download_start", repo=repo_id, branch=branch, url=archive_url)

    resp = _get_stream_with_token(
        archive_url, token, params=params, verify_ssl=(not insecure)
    )

    if resp.status_code in (401, 403):
        raise RuntimeError("Bitbucket authentication failed. Check BITBUCKET_TOKEN and REPO_READ permission.")
    if resp.status_code == 404:
        raise RuntimeError(f"Repository or branch not found: {project}/{repo_id} at={branch}")
    resp.raise_for_status()

    # Decide output filename
    cd_name = _filename_from_cd(resp.headers.get("Content-Disposition"))
    out_name = cd_name or f"{repo_id}-{branch or 'default'}.zip"
    out_name = _safe_filename(out_name)

    out_path = pathlib.Path(out_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    file_path = out_path / out_name

    # Stream to disk
    bytes_written = 0
    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                bytes_written += len(chunk)

    logger.info("repo_download_done", repo=repo_id, path=str(file_path), bytes=bytes_written)
    return file_path


def _unzip_file(zip_path: Path) -> Path:
    """Extract a ZIP file into an 'unzipped_output' subdirectory.

    Returns the path to the extracted directory.
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    extract_to = zip_path.parent / "unzipped_output"
    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    logger.info("repo_unzip_done", path=str(extract_to))
    return extract_to.resolve()


# ── Public API ───────────────────────────────────────────────────────────────


def clone_repo(repo_name: str, branch: str, target_dir: str | None = None) -> Path:
    """Download and extract a repo branch into a temporary directory.

    Uses the Bitbucket Server archive API with the same Bearer/Token auth
    as repos.py and branches.py.

    Returns the path to the extracted source directory.
    """
    settings = get_settings()

    base_url = settings.bitbucket_base_url
    project = settings.bitbucket_project
    token = settings.bitbucket_token

    if not base_url:
        raise RuntimeError("BITBUCKET_BASE_URL is not configured")
    if not project:
        raise RuntimeError("BITBUCKET_PROJECT is not configured")
    if not token:
        raise RuntimeError("BITBUCKET_TOKEN is not configured")

    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix="ccv-repo-")

    # Step 1: Download ZIP
    zip_path = _download_repo_zip(
        repo_id=repo_name,
        branch=branch,
        out_dir=target_dir,
        base_url=base_url,
        project=project,
        token=token,
    )

    # Step 2: Unzip
    extracted_path = _unzip_file(zip_path)

    # Step 3: Clean up ZIP file
    zip_path.unlink(missing_ok=True)

    return extracted_path


def cleanup_repo(path: Path) -> None:
    """Remove a downloaded repo directory."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        logger.info("repo_cleanup", path=str(path))
