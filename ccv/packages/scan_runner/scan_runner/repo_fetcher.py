"""Clone or archive a repository branch for scanning."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


def clone_repo(repo_name: str, branch: str, target_dir: str | None = None) -> Path:
    """Clone a repo branch into a temporary directory.

    Uses REPO_CLONE_URL_TEMPLATE with {repo} placeholder, authenticated
    via GIT_USERNAME / GIT_PASSWORD_OR_TOKEN.

    Returns the path to the cloned directory.
    """
    settings = get_settings()

    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix="ccv-repo-")
    target = Path(target_dir)

    url_template = settings.repo_clone_url_template
    if not url_template:
        raise RuntimeError("REPO_CLONE_URL_TEMPLATE is not configured")

    clone_url = (
        url_template
        .replace("{base_url}", settings.bitbucket_base_url.rstrip("/"))
        .replace("{project}", settings.bitbucket_project)
        .replace("{repo}", repo_name)
    )

    # Inject credentials into URL if provided
    token = settings.bitbucket_token or settings.git_password_or_token
    username = settings.git_username or "x-token-auth"
    if token and "://" in clone_url:
        proto, rest = clone_url.split("://", 1)
        clone_url = f"{proto}://{username}:{token}@{rest}"

    logger.info("repo_clone_start", repo=repo_name, branch=branch)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, clone_url, str(target)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("repo_clone_failed", repo=repo_name, stderr=exc.stderr[:500])
        raise RuntimeError(f"Git clone failed: {exc.stderr[:500]}") from exc

    logger.info("repo_clone_done", repo=repo_name, path=str(target))
    return target


def cleanup_repo(path: Path) -> None:
    """Remove a cloned repo directory."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        logger.info("repo_cleanup", path=str(path))
