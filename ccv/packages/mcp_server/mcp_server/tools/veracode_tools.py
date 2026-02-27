"""Veracode MCP tools — wrapping Upload XML API + Findings REST API.

Uses VeracodeClient for all HTTP calls with HMAC auth.
"""

from __future__ import annotations

import io
from typing import Any
from xml.etree.ElementTree import Element

import httpx
from defusedxml import ElementTree as DET

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)


# ── Veracode HMAC Client Adapter ─────────────────────────────────────────────


class VeracodeClient:
    """HTTP client with Veracode HMAC authentication.

    Uses the `veracode-api-signing` library to sign requests for both
    XML Upload API and REST API endpoints.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.analysis_base = self.settings.veracode_analysis_base.rstrip("/")
        self.rest_base = self.settings.veracode_rest_base.rstrip("/")
        self.api_key_id = self.settings.veracode_api_key_id
        self.api_key_secret = self.settings.veracode_api_key_secret

    def _get_hmac_headers(self, url: str, method: str = "GET") -> dict[str, str]:
        """Generate Veracode HMAC auth headers.

        Requires veracode-api-signing to be installed. Falls back to
        empty headers in mock/dev mode.
        """
        if not self.api_key_id or not self.api_key_secret:
            logger.warning("veracode_hmac_no_credentials", msg="No Veracode API credentials configured")
            return {}

        try:
            from veracode_api_signing.plugin_requests import generate_veracode_hmac_header

            return {"Authorization": generate_veracode_hmac_header(url, method)}
        except ImportError:
            logger.warning("veracode_hmac_import_error", msg="veracode-api-signing not installed")
            return {}

    async def xml_request(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        files: dict | None = None,
        data: dict | None = None,
    ) -> Element:
        """Make a signed request to the Veracode XML (Upload) API and parse XML response."""
        url = f"{self.analysis_base}/api/5.0/{path}"
        headers = self._get_hmac_headers(url, method)

        async with httpx.AsyncClient(timeout=120) as client:
            if method.upper() == "POST":
                resp = await client.post(url, headers=headers, params=params, data=data, files=files)
            else:
                resp = await client.get(url, headers=headers, params=params)

        resp.raise_for_status()
        return DET.fromstring(resp.content)

    async def rest_request(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """Make a signed request to the Veracode REST API and return JSON."""
        url = f"{self.rest_base}{path}"
        headers = self._get_hmac_headers(url, method)
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=120) as client:
            if method.upper() == "POST":
                resp = await client.post(url, headers=headers, params=params, json=json_body)
            else:
                resp = await client.get(url, headers=headers, params=params)

        resp.raise_for_status()
        return resp.json()


_client: VeracodeClient | None = None


def _get_client() -> VeracodeClient:
    global _client
    if _client is None:
        _client = VeracodeClient()
    return _client


# ── Tool: veracode.upload_artifact ────────────────────────────────────────────


async def veracode_upload_artifact(params: dict[str, Any]) -> dict:
    """Upload a file to Veracode using uploadfile.do.

    Params:
        app_id: str — Veracode application profile ID
        file_path: str — local path to the file to upload
        sandbox_id: str (optional)
    """
    client = _get_client()
    app_id = params["app_id"]
    file_path = params["file_path"]
    sandbox_id = params.get("sandbox_id")

    request_params: dict[str, str] = {"app_id": app_id}
    if sandbox_id:
        request_params["sandbox_id"] = sandbox_id

    try:
        with open(file_path, "rb") as f:
            file_content = f.read()
    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}

    file_name = file_path.rsplit("/", 1)[-1]
    files = {"file": (file_name, io.BytesIO(file_content), "application/octet-stream")}

    root = await client.xml_request("uploadfile.do", method="POST", params=request_params, files=files)
    file_list = []
    for f_elem in root.iter():
        if "file" in f_elem.tag.lower():
            file_list.append({
                "name": f_elem.get("file_name", ""),
                "status": f_elem.get("file_status", ""),
            })

    logger.info("veracode_upload_complete", app_id=app_id, files=len(file_list))
    return {"status": "uploaded", "files": file_list}


# ── Tool: veracode.start_prescan ──────────────────────────────────────────────


async def veracode_start_prescan(params: dict[str, Any]) -> dict:
    """Start a prescan using beginprescan.do.

    Params:
        app_id: str
        sandbox_id: str (optional)
        auto_scan: bool (default False) — if True, automatically start scan after prescan
    """
    client = _get_client()
    app_id = params["app_id"]
    sandbox_id = params.get("sandbox_id")
    auto_scan = params.get("auto_scan", False)

    request_params: dict[str, str] = {
        "app_id": app_id,
        "auto_scan": str(auto_scan).lower(),
    }
    if sandbox_id:
        request_params["sandbox_id"] = sandbox_id

    root = await client.xml_request("beginprescan.do", method="POST", params=request_params)
    build_id = root.get("build_id", "")

    logger.info("veracode_prescan_started", app_id=app_id, build_id=build_id)
    return {"status": "prescan_started", "build_id": build_id}


# ── Tool: veracode.get_prescan_results ────────────────────────────────────────


async def veracode_get_prescan_results(params: dict[str, Any]) -> dict:
    """Get prescan results using getprescanresults.do.

    Params:
        app_id: str
        build_id: str (optional)
        sandbox_id: str (optional)
    """
    client = _get_client()
    app_id = params["app_id"]
    build_id = params.get("build_id")
    sandbox_id = params.get("sandbox_id")

    request_params: dict[str, str] = {"app_id": app_id}
    if build_id:
        request_params["build_id"] = build_id
    if sandbox_id:
        request_params["sandbox_id"] = sandbox_id

    root = await client.xml_request("getprescanresults.do", params=request_params)

    modules = []
    for module in root.iter():
        if "module" in module.tag.lower():
            modules.append({
                "name": module.get("name", ""),
                "status": module.get("status", ""),
                "has_fatal_errors": module.get("has_fatal_errors", "false"),
            })

    return {"status": "prescan_complete", "modules": modules}


# ── Tool: veracode.start_final_scan ───────────────────────────────────────────


async def veracode_start_final_scan(params: dict[str, Any]) -> dict:
    """Start the final scan using beginscan.do (scan_all_top_level_modules=true).

    Params:
        app_id: str
        sandbox_id: str (optional)
        scan_all_top_level_modules: bool (default True)
    """
    client = _get_client()
    app_id = params["app_id"]
    sandbox_id = params.get("sandbox_id")
    scan_all = params.get("scan_all_top_level_modules", True)

    request_params: dict[str, str] = {
        "app_id": app_id,
        "scan_all_top_level_modules": str(scan_all).lower(),
    }
    if sandbox_id:
        request_params["sandbox_id"] = sandbox_id

    root = await client.xml_request("beginscan.do", method="POST", params=request_params)
    build_id = root.get("build_id", "")

    logger.info("veracode_scan_started", app_id=app_id, build_id=build_id)
    return {"status": "scan_started", "build_id": build_id}


# ── Tool: veracode.get_final_scan_status ──────────────────────────────────────


async def veracode_get_final_scan_status(params: dict[str, Any]) -> dict:
    """Get scan status using getbuildinfo.do.

    Params:
        app_id: str
        build_id: str (optional)
        sandbox_id: str (optional)

    Returns status string such as 'Results Ready', 'Scan In Progress', etc.
    """
    client = _get_client()
    app_id = params["app_id"]
    build_id = params.get("build_id")
    sandbox_id = params.get("sandbox_id")

    request_params: dict[str, str] = {"app_id": app_id}
    if build_id:
        request_params["build_id"] = build_id
    if sandbox_id:
        request_params["sandbox_id"] = sandbox_id

    root = await client.xml_request("getbuildinfo.do", params=request_params)

    # Parse build status from XML
    status = "unknown"
    for elem in root.iter():
        if "analysis_unit" in elem.tag.lower():
            status = elem.get("status", "unknown")
            break

    is_complete = status.lower() in ("results ready",)
    return {"status": status, "complete": is_complete}


# ── Tool: veracode.get_final_results ──────────────────────────────────────────


async def veracode_get_final_results(params: dict[str, Any]) -> dict:
    """Fetch final scan findings using the Findings REST API v2.

    Params:
        app_id: str (GUID for REST API, or legacy id)
        sandbox_id: str (optional)
        use_reporting_api: bool (default False) — if True, use Reporting API instead
    """
    client = _get_client()
    app_id = params["app_id"]
    sandbox_id = params.get("sandbox_id")
    use_reporting = params.get("use_reporting_api", False)

    if use_reporting:
        # Reporting API path
        path = f"/appsec/v1/applications/{app_id}/findings"
    else:
        # Findings REST API v2
        path = f"/appsec/v2/applications/{app_id}/findings"

    request_params: dict[str, str] = {"size": "500"}
    if sandbox_id:
        request_params["context"] = sandbox_id

    result = await client.rest_request(path, params=request_params)

    findings = result.get("_embedded", {}).get("findings", [])
    logger.info("veracode_findings_fetched", app_id=app_id, count=len(findings))
    return {"findings": findings, "total": len(findings)}


# ── Tool: veracode.list_recent_scans ──────────────────────────────────────────


async def veracode_list_recent_scans(params: dict[str, Any]) -> dict:
    """List completed scans/builds since a given timestamp or build_id.

    Params:
        app_id: str — Veracode application profile ID
        since_timestamp: str (ISO format, optional) — only return builds after this time
        since_build_id: str (optional) — only return builds after this build id

    Uses Veracode XML Upload API: getbuildlist.do
    Returns: list of scan summaries [{build_id, status, created_at, ...}]
    """
    client = _get_client()
    app_id = params["app_id"]
    since_timestamp = params.get("since_timestamp")
    since_build_id = params.get("since_build_id")

    request_params: dict[str, str] = {"app_id": app_id}

    root = await client.xml_request("getbuildlist.do", params=request_params)

    builds: list[dict[str, Any]] = []
    for elem in root.iter():
        tag = elem.tag.lower() if isinstance(elem.tag, str) else ""
        if "build" in tag:
            build_id = elem.get("build_id", "")
            if not build_id:
                continue

            build_info: dict[str, Any] = {
                "build_id": build_id,
                "version": elem.get("version", ""),
            }
            builds.append(build_info)

    # Fetch detailed status for each build using getbuildinfo.do
    enriched: list[dict[str, Any]] = []
    for build in builds:
        try:
            info_params: dict[str, str] = {
                "app_id": app_id,
                "build_id": build["build_id"],
            }
            info_root = await client.xml_request("getbuildinfo.do", params=info_params)

            status = "unknown"
            created_at = ""
            for info_elem in info_root.iter():
                info_tag = info_elem.tag.lower() if isinstance(info_elem.tag, str) else ""
                if "analysis_unit" in info_tag:
                    status = info_elem.get("status", "unknown")
                if "build" in info_tag:
                    created_at = info_elem.get("build_id", created_at)
                    # Try to extract policy dates
                    created_at = info_elem.get("grace_period_expired", created_at)

            build["status"] = status
            build["created_at"] = created_at
            enriched.append(build)
        except Exception as exc:
            logger.warning(
                "veracode_build_info_failed",
                build_id=build["build_id"],
                error=str(exc),
            )
            build["status"] = "fetch_error"
            build["created_at"] = ""
            enriched.append(build)

    # Filter by since_build_id: only include builds that come after the given id
    if since_build_id:
        filtered = []
        found_marker = False
        for b in enriched:
            if found_marker:
                filtered.append(b)
            if b["build_id"] == since_build_id:
                found_marker = True
        enriched = filtered

    # Filter by since_timestamp if provided
    if since_timestamp:
        from datetime import datetime, timezone

        try:
            cutoff = datetime.fromisoformat(since_timestamp.replace("Z", "+00:00"))
        except ValueError:
            cutoff = None

        if cutoff:
            filtered_by_time = []
            for b in enriched:
                # If we can't parse created_at, include the build to be safe
                if not b.get("created_at"):
                    filtered_by_time.append(b)
                    continue
                try:
                    build_time = datetime.fromisoformat(
                        b["created_at"].replace("Z", "+00:00")
                    )
                    if build_time >= cutoff:
                        filtered_by_time.append(b)
                except (ValueError, TypeError):
                    filtered_by_time.append(b)
            enriched = filtered_by_time

    logger.info(
        "veracode_list_recent_scans",
        app_id=app_id,
        total=len(enriched),
    )
    return {"scans": enriched, "total": len(enriched)}


# ── Tool: veracode.get_scan_metadata ──────────────────────────────────────────


async def veracode_get_scan_metadata(params: dict[str, Any]) -> dict:
    """Get metadata for a specific scan/build.

    Params:
        app_id: str — Veracode application profile ID
        build_id: str — the specific build/scan ID

    Uses getbuildinfo.do
    Returns: scan metadata dict with build details, analysis units, policy info.
    """
    client = _get_client()
    app_id = params["app_id"]
    build_id = params["build_id"]

    request_params: dict[str, str] = {
        "app_id": app_id,
        "build_id": build_id,
    }

    root = await client.xml_request("getbuildinfo.do", params=request_params)

    metadata: dict[str, Any] = {
        "app_id": app_id,
        "build_id": build_id,
    }

    # Parse build-level attributes
    for elem in root.iter():
        tag = elem.tag.lower() if isinstance(elem.tag, str) else ""

        if "build" in tag and "analysis" not in tag:
            metadata["version"] = elem.get("version", "")
            metadata["build_id"] = elem.get("build_id", build_id)
            metadata["submitter"] = elem.get("submitter", "")
            metadata["platform"] = elem.get("platform", "")
            metadata["lifecycle_stage"] = elem.get("lifecycle_stage", "")
            metadata["policy_name"] = elem.get("policy_name", "")
            metadata["policy_version"] = elem.get("policy_version", "")
            metadata["policy_compliance_status"] = elem.get(
                "policy_compliance_status", ""
            )
            metadata["grace_period_expired"] = elem.get(
                "grace_period_expired", ""
            )

        if "analysis_unit" in tag:
            metadata["analysis_type"] = elem.get("analysis_type", "")
            metadata["status"] = elem.get("status", "")
            metadata["engine_version"] = elem.get("engine_version", "")
            metadata["published_date"] = elem.get("published_date", "")

    logger.info(
        "veracode_get_scan_metadata",
        app_id=app_id,
        build_id=build_id,
        status=metadata.get("status", "unknown"),
    )
    return metadata


# ── Tool: veracode.create_build ───────────────────────────────────────────────


async def veracode_create_build(params: dict[str, Any]) -> dict:
    """Create a new build (version) using createbuild.do.

    Params:
        app_id: str — Veracode application profile ID
        version: str — unique build version name (e.g., 'scan_abc123_20260227')
        sandbox_id: str (optional)
    """
    client = _get_client()
    app_id = params["app_id"]
    version = params["version"]
    sandbox_id = params.get("sandbox_id")

    request_params: dict[str, str] = {
        "app_id": app_id,
        "version": version,
    }
    if sandbox_id:
        request_params["sandbox_id"] = sandbox_id

    root = await client.xml_request("createbuild.do", method="POST", params=request_params)
    build_id = root.get("build_id", "")

    logger.info("veracode_build_created", app_id=app_id, build_id=build_id, version=version)
    return {"status": "build_created", "build_id": build_id, "version": version}


# ── Tool: veracode.get_detailed_report ────────────────────────────────────────


async def veracode_get_detailed_report(params: dict[str, Any]) -> dict:
    """Download the Detailed Report XML using detailedreport.do.

    Params:
        build_id: str — the build ID to get the report for
    """
    client = _get_client()
    build_id = params["build_id"]

    root = await client.xml_request("detailedreport.do", params={"build_id": build_id})

    # Parse top-level report metadata
    report: dict[str, Any] = {
        "build_id": build_id,
        "app_name": root.get("app_name", ""),
        "total_flaws": root.get("total_flaws", "0"),
        "flaws_not_mitigated": root.get("flaws_not_mitigated", "0"),
    }

    # Extract individual flaws
    flaws = []
    for flaw in root.iter():
        tag = flaw.tag.lower() if isinstance(flaw.tag, str) else ""
        if "flaw" in tag:
            flaws.append({
                "issueid": flaw.get("issueid", ""),
                "severity": flaw.get("severity", ""),
                "cweid": flaw.get("cweid", ""),
                "categoryname": flaw.get("categoryname", ""),
                "sourcefile": flaw.get("sourcefile", ""),
                "line": flaw.get("line", ""),
                "remediation_status": flaw.get("remediation_status", ""),
                "description": flaw.get("description", ""),
            })

    report["flaws"] = flaws
    logger.info("veracode_detailed_report", build_id=build_id, flaw_count=len(flaws))
    return report


# ── Tool: veracode.get_static_findings ────────────────────────────────────────


async def veracode_get_static_findings(params: dict[str, Any]) -> dict:
    """Fetch static scan findings using the Findings REST API v2.

    Params:
        app_id: str — Veracode application GUID
        sandbox_id: str (optional)
    """
    client = _get_client()
    app_id = params["app_id"]
    sandbox_id = params.get("sandbox_id")

    path = f"/appsec/v2/applications/{app_id}/findings"
    request_params: dict[str, str] = {"size": "500", "scan_type": "STATIC"}
    if sandbox_id:
        request_params["context"] = sandbox_id

    result = await client.rest_request(path, params=request_params)
    findings = result.get("_embedded", {}).get("findings", [])

    logger.info("veracode_static_findings_fetched", app_id=app_id, count=len(findings))
    return {"findings": findings, "total": len(findings), "scan_type": "STATIC"}


# ── Tool: veracode.get_sca_findings ───────────────────────────────────────────


async def veracode_get_sca_findings(params: dict[str, Any]) -> dict:
    """Fetch SCA (Software Composition Analysis) findings using the Findings REST API v2.

    Params:
        app_id: str — Veracode application GUID
        sandbox_id: str (optional)
    """
    client = _get_client()
    app_id = params["app_id"]
    sandbox_id = params.get("sandbox_id")

    path = f"/appsec/v2/applications/{app_id}/findings"
    request_params: dict[str, str] = {"size": "500", "scan_type": "SCA"}
    if sandbox_id:
        request_params["context"] = sandbox_id

    result = await client.rest_request(path, params=request_params)
    findings = result.get("_embedded", {}).get("findings", [])

    logger.info("veracode_sca_findings_fetched", app_id=app_id, count=len(findings))
    return {"findings": findings, "total": len(findings), "scan_type": "SCA"}
