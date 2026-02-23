"""Build a Maven project and locate the output artifact (jar/war)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.logging import get_logger

logger = get_logger(__name__)


def build_maven_project(repo_path: Path) -> Path:
    """Run `mvn package -DskipTests` and return the path to the built artifact.

    Raises RuntimeError if the build fails or no artifact is found.
    """
    logger.info("maven_build_start", path=str(repo_path))

    pom = repo_path / "pom.xml"
    if not pom.exists():
        raise RuntimeError(f"No pom.xml found in {repo_path}")

    try:
        subprocess.run(
            ["mvn", "package", "-DskipTests", "-q", "-f", str(pom)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(repo_path),
        )
    except FileNotFoundError:
        raise RuntimeError("Maven (mvn) is not installed or not on PATH")
    except subprocess.CalledProcessError as exc:
        logger.error("maven_build_failed", stderr=exc.stderr[:1000])
        raise RuntimeError(f"Maven build failed: {exc.stderr[:500]}") from exc

    # Look for artifact in target/
    target_dir = repo_path / "target"
    if not target_dir.exists():
        raise RuntimeError(f"target/ directory not found after build in {repo_path}")

    # Prefer .war, then .jar
    for pattern in ("*.war", "*.jar"):
        artifacts = sorted(target_dir.glob(pattern))
        # Filter out sources/javadoc jars
        artifacts = [a for a in artifacts if "-sources" not in a.name and "-javadoc" not in a.name]
        if artifacts:
            artifact = artifacts[-1]
            logger.info("maven_build_done", artifact=str(artifact))
            return artifact

    raise RuntimeError(f"No jar/war artifact found in {target_dir}")
