"""Direct Veracode XML API client using HMAC authentication.

This runs natively inside the scan_runner to avoid long-polling HTTP timeouts
that would occur if these calls were brokered over the MCP server proxy.
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Tuple

import requests
from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


def _get_auth() -> RequestsAuthPluginVeracodeHMAC:
    """Create a Veracode HMAC auth object from settings."""
    settings = get_settings()
    if not settings.veracode_api_key_id or not settings.veracode_api_key_secret:
        raise RuntimeError("VERACODE_API_KEY_ID and VERACODE_API_KEY_SECRET must be configured")
    return RequestsAuthPluginVeracodeHMAC(
        api_key_id=settings.veracode_api_key_id,
        api_key_secret=settings.veracode_api_key_secret,
    )


def create_new_build(app_id: str, version: str, sandbox_id: str | None = None, api_base: str = "https://analysiscenter.veracode.com") -> str:
    auth = _get_auth()
    url = f"{api_base}/api/5.0/createbuild.do"
    data = {"app_id": str(app_id), "version": version}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)

    logger.info("veracode_create_build", app_id=app_id, version=version)
    resp = requests.post(url, data=data, auth=auth, timeout=120)
    resp.raise_for_status()

    try:
        root = ET.fromstring(resp.text)
        return root.attrib.get("build_id", "")
    except ET.ParseError:
        raise RuntimeError("Failed to parse createbuild.do XML response")


def _find_largest_jar(target_dir: str) -> Tuple[Path, int]:
    target_path = Path(target_dir).resolve()
    jars = list(target_path.rglob("*.jar"))
    if not jars:
        raise FileNotFoundError(f"No .jar files found under: {target_path}")
    largest = max(jars, key=lambda p: p.stat().st_size)
    return largest, largest.stat().st_size


def upload_artifact(app_id: str, target_dir: str, sandbox_id: str | None = None, api_base: str = "https://analysiscenter.veracode.com") -> str:
    auth = _get_auth()
    file_path, file_size = _find_largest_jar(target_dir)

    url = f"{api_base}/api/5.0/uploadfile.do"
    data: dict[str, str] = {"app_id": str(app_id)}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)

    filename = os.path.basename(file_path)
    logger.info("veracode_upload_start", file=filename, size_bytes=file_size)

    with open(file_path, "rb") as f:
        resp = requests.post(url, data=data, files={"file": (filename, f)}, auth=auth, timeout=900)
    resp.raise_for_status()
    return str(file_path)


def begin_prescan(app_id: str, sandbox_id: str | None = None, api_base: str = "https://analysiscenter.veracode.com") -> None:
    auth = _get_auth()
    url = f"{api_base}/api/5.0/beginprescan.do"
    data: dict[str, str] = {"app_id": str(app_id), "auto_scan": "false"}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)

    resp = requests.post(url, data=data, auth=auth, timeout=120)
    resp.raise_for_status()


def poll_prescan_until_complete(app_id: str, sandbox_id: str | None = None, build_id: str | None = None, poll_interval: int = 15, timeout: int = 900, api_base: str = "https://analysiscenter.veracode.com") -> dict:
    auth = _get_auth()
    url = f"{api_base}/api/5.0/getprescanresults.do"
    data: dict[str, str] = {"app_id": str(app_id)}
    if sandbox_id: data["sandbox_id"] = str(sandbox_id)
    if build_id: data["build_id"] = str(build_id)

    start = time.time()
    attempt = 0
    while True:
        attempt += 1
        resp = requests.post(url, data=data, auth=auth, timeout=60)
        if resp.status_code in (429, 502, 503, 504):
            logger.warning("veracode_prescan_poll_retry", code=resp.status_code, attempt=attempt)
            time.sleep(min(5 * attempt, 30))
            continue
        resp.raise_for_status()
        
        root = ET.fromstring(resp.text)
        module_statuses = {m.attrib.get("status", "").strip() for m in root.findall(".//{*}module")}

        if not module_statuses:
            if time.time() - start > timeout:
                raise RuntimeError("Prescan timed out — no modules found")
            logger.info("veracode_prescan_poll_waiting", reason="no_modules_yet", attempt=attempt)
            time.sleep(poll_interval)
            continue

        if any(s in {"Queued", "Pre-Scan Submitted", "Pre-Scan Running"} for s in module_statuses):
            if time.time() - start > timeout:
                raise RuntimeError(f"Prescan timed out. Statuses: {module_statuses}")
            logger.info("veracode_prescan_poll_waiting", statuses=list(module_statuses), attempt=attempt)
            time.sleep(poll_interval)
            continue

        logger.info("veracode_prescan_poll_complete", statuses=list(module_statuses), attempts=attempt)
        return {"statuses": list(module_statuses), "polls": attempt}


def begin_final_scan(app_id: str, sandbox_id: str | None = None, api_base: str = "https://analysiscenter.veracode.com") -> None:
    auth = _get_auth()
    url = f"{api_base}/api/5.0/beginscan.do"
    data: dict[str, str] = {"app_id": str(app_id), "scan_all_top_level_modules": "true"}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)

    resp = requests.post(url, data=data, auth=auth, timeout=180)
    resp.raise_for_status()
    logger.info("veracode_final_scan_started", app_id=app_id)


def poll_final_scan_until_complete(app_id: str, sandbox_id: str | None = None, build_id: str | None = None, poll_interval: int = 20, timeout: int = 3600, api_base: str = "https://analysiscenter.veracode.com") -> dict:
    auth = _get_auth()
    url = f"{api_base}/api/5.0/getbuildinfo.do"
    data: dict[str, str] = {"app_id": str(app_id)}
    if sandbox_id: data["sandbox_id"] = str(sandbox_id)
    if build_id: data["build_id"] = str(build_id)

    start = time.time()
    attempt = 0
    while True:
        attempt += 1
        resp = requests.post(url, data=data, auth=auth, timeout=60)
        if resp.status_code in (429, 502, 503, 504):
            logger.warning("veracode_final_scan_poll_retry", code=resp.status_code, attempt=attempt)
            time.sleep(min(5 * attempt, 30))
            continue
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        build_elem = root.find(".//{*}build")
        if build_elem is None:
            if time.time() - start > timeout:
                raise RuntimeError("Final scan timed out — no build info found")
            logger.info("veracode_final_scan_poll_waiting", reason="no_build_info_yet", attempt=attempt)
            time.sleep(poll_interval)
            continue

        if build_elem.attrib.get("results_ready", "").lower() == "true":
            logger.info("veracode_final_scan_poll_complete", attempts=attempt)
            return {"attempts": attempt, "results_ready": True}

        if time.time() - start > timeout:
            raise RuntimeError(f"Final scan timed out after {attempt} polls")
        
        logger.info("veracode_final_scan_poll_waiting", status=build_elem.attrib.get("analysis_unit_status", "in_progress"), attempt=attempt)
        time.sleep(poll_interval)


def get_detailed_report(build_id: str, api_base: str = "https://analysiscenter.veracode.com") -> dict:
    auth = _get_auth()
    url = f"{api_base}/api/5.0/detailedreport.do"
    resp = requests.post(url, data={"build_id": str(build_id)}, auth=auth, timeout=180)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    report = {"build_id": build_id, "app_name": root.attrib.get("app_name", ""), "flaws": []}
    for flaw in root.findall(".//{*}flaw"):
        report["flaws"].append({
            "issueid": flaw.attrib.get("issueid", ""),
            "severity": flaw.attrib.get("severity", ""),
            "cweid": flaw.attrib.get("cweid", ""),
            "categoryname": flaw.attrib.get("categoryname", ""),
            "sourcefile": flaw.attrib.get("sourcefile", ""),
            "line": flaw.attrib.get("line", ""),
            "description": flaw.attrib.get("description", ""),
        })
    return report


def _get_rest_findings(app_id: str, sandbox_id: str | None, scan_type: str) -> dict:
    """Fetch static/SCA findings via REST API v2."""
    settings = get_settings()
    auth = _get_auth()
    url = f"{settings.veracode_rest_base.rstrip('/')}/appsec/v2/applications/{app_id}/findings"
    
    params: dict[str, str] = {"size": "500", "scan_type": scan_type}
    if sandbox_id: params["context"] = sandbox_id

    resp = requests.get(url, params=params, auth=auth, timeout=120)
    resp.raise_for_status()
    findings = resp.json().get("_embedded", {}).get("findings", [])
    return {"findings": findings, "total": len(findings), "scan_type": scan_type}


def get_static_findings(app_id: str, sandbox_id: str | None = None) -> dict:
    return _get_rest_findings(app_id, sandbox_id, "STATIC")


def get_sca_findings(app_id: str, sandbox_id: str | None = None) -> dict:
    return _get_rest_findings(app_id, sandbox_id, "SCA")
