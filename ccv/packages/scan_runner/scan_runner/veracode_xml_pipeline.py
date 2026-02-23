"""Bitbucket ZIP -> Maven build -> Veracode XML API scan pipeline.

This module is added to CCV zip to support:
- Downloading repository source as ZIP from Bitbucket Data Center using PAT
- Running Maven build
- Driving Veracode XML API workflow:
    createbuild -> uploadfile -> beginprescan -> poll prescan -> beginscan -> poll final -> detailedreport
- Returning BOTH:
    - raw XML (string) + saved XML file path
    - normalized JSON (as per normalize_xml_findings.py) + saved JSON file path

NOTE: detailedreport XML can be very large. Consider setting include_full_xml=False when calling.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

import requests

from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC

from .normalize_xml_findings import (
    normalize_createbuild_response_to_json,
    normalize_uploadfile_response_to_json,
    normalize_beginprescan_response_to_json,
    normalize_getprescanresults_response_to_json,
    normalize_beginscan_response_to_json,
    normalize_getfinalscanresults_response_to_json,
    normalize_detailedreport_response_to_json,
)


# -------------------------
# Bitbucket ZIP Download (Data Center/Server)
# -------------------------

def _bb_auth_headers(token: str, scheme: str) -> dict:
    return {"Authorization": f"{scheme} {token}"}

def _safe_filename(name: str) -> str:
    name = (name or "").strip().replace("\n", " ")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "archive.zip"

def _filename_from_cd(content_disposition: Optional[str]) -> Optional[str]:
    if not content_disposition:
        return None
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, re.IGNORECASE)
    return m.group(1) if m else None

def download_bitbucket_archive_zip_to_disk(
    base_url: str,
    project: str,
    repo: str,
    at: Optional[str],
    out_dir: str,
    token: str,
    insecure: bool = False,
    overwrite: bool = True,
) -> str:
    """Download Bitbucket archive ZIP to disk and return file path.

    Endpoint:
      GET /rest/api/1.0/projects/{project}/repos/{repo}/archive?format=zip&at=<ref>
    """
    base_url = base_url.rstrip("/")
    archive_url = f"{base_url}/rest/api/1.0/projects/{project}/repos/{repo}/archive"

    params: dict[str, Any] = {"format": "zip"}
    if at:
        params["at"] = at

    last_resp = None
    for scheme in ("Bearer", "Token"):
        resp = requests.get(
            archive_url,
            headers=_bb_auth_headers(token, scheme),
            params=params,
            stream=True,
            allow_redirects=True,
            timeout=300,
            verify=(not insecure),
        )
        last_resp = resp
        if resp.status_code in (401, 403):
            continue
        break

    if last_resp is None:
        raise RuntimeError("No response from Bitbucket")

    if last_resp.status_code in (401, 403):
        raise RuntimeError("Bitbucket auth failed (401/403). Check PAT permissions.")
    if last_resp.status_code == 404:
        raise RuntimeError("Bitbucket archive not found (404). Check base_url/project/repo/at.")
    last_resp.raise_for_status()

    out_path = Path(out_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    cd_name = _filename_from_cd(last_resp.headers.get("Content-Disposition"))
    default_name = f"{repo}-{(at or 'default')}.zip"
    zip_name = _safe_filename(cd_name or default_name)
    zip_file_path = out_path / zip_name

    if zip_file_path.exists() and not overwrite:
        raise RuntimeError(f"ZIP already exists: {zip_file_path}")

    bytes_written = 0
    with open(zip_file_path, "wb") as f:
        for chunk in last_resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                bytes_written += len(chunk)

    if bytes_written == 0:
        raise RuntimeError("Downloaded ZIP is empty (0 bytes).")

    return str(zip_file_path)


# -------------------------
# Workspace + IO helpers
# -------------------------

def make_run_workspace(root_dir: str, repo: str) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_id = os.urandom(4).hex()
    p = Path(root_dir).expanduser().resolve() / f"{repo}_{ts}_{run_id}"
    p.mkdir(parents=True, exist_ok=True)
    return str(p)

def save_xml_and_normalize_return(
    *,
    xml_text: str,
    xml_filename: str,
    json_filename: str,
    normalizer_fn: Callable[[str], Any],
    include_xml_in_response: bool = True,
    xml_preview_chars: Optional[int] = 2000,
) -> dict:
    """Save XML + normalize (as per provided normalizer) + return both."""
    xml_path = Path(xml_filename).resolve()
    json_path = Path(json_filename).resolve()

    xml_path.write_text(xml_text, encoding="utf-8")

    normalized = normalizer_fn(str(xml_path))

    json_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")

    out: dict[str, Any] = {
        "xml_file": str(xml_path),
        "json_file": str(json_path),
        "normalized": normalized,
    }

    if xml_preview_chars:
        out["xml_preview"] = xml_text[:xml_preview_chars]

    if include_xml_in_response:
        out["xml"] = xml_text

    return out


# -------------------------
# ZIP + Maven helpers
# -------------------------

def unzip_file(zip_path: str, extract_to: str) -> str:
    zip_path_p = Path(zip_path)
    extract_to_p = Path(extract_to)
    if not zip_path_p.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path_p}")
    extract_to_p.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path_p, "r") as z:
        z.extractall(extract_to_p)
    return str(extract_to_p.resolve())

def find_maven_root(extract_dir: str) -> str:
    base = Path(extract_dir).resolve()
    if (base / "pom.xml").exists():
        return str(base)
    for child in base.iterdir():
        if child.is_dir() and (child / "pom.xml").exists():
            return str(child)
    pom = next(iter(base.rglob("pom.xml")), None)
    if pom:
        return str(pom.parent)
    raise FileNotFoundError(f"No pom.xml found under: {base}")

def run_maven_build_simple(project_dir: str) -> None:
    project_path = Path(project_dir).resolve()
    pom_file = project_path / "pom.xml"
    if not pom_file.exists():
        raise FileNotFoundError(f"pom.xml not found in: {project_path}")
    command = 'mvn clean package -DskipTests -Djib.skip="true"'
    result = subprocess.run(command, cwd=str(project_path), shell=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Maven build failed with exit code {result.returncode}")

def find_jar(target_dir: str) -> Tuple[Path, int]:
    target_path = Path(target_dir).resolve()
    jars = list(target_path.rglob("*.jar"))
    if not jars:
        raise FileNotFoundError(f"No .jar files found under: {target_path}")
    largest = max(jars, key=lambda p: p.stat().st_size)
    return largest, largest.stat().st_size


# -------------------------
# Veracode XML API steps (each returns XML + normalized JSON)
# -------------------------

def create_new_build(
    app_id: str,
    sandbox_id: str,
    version: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    include_xml: bool = True,
) -> dict:
    url = f"{api_base}/api/5.0/createbuild.do"
    data: dict[str, Any] = {"app_id": str(app_id), "version": version}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    resp = requests.post(url, data=data, auth=auth, timeout=120)
    resp.raise_for_status()
    out = save_xml_and_normalize_return(
        xml_text=resp.text,
        xml_filename="createbuild_response.xml",
        json_filename="normalize_createbuild_response.json",
        normalizer_fn=normalize_createbuild_response_to_json,
        include_xml_in_response=include_xml,
        xml_preview_chars=2000,
    )
    out["build_id"] = (out.get("normalized") or [{}])[0].get("build_id", "unknown")
    return out

def upload_file(
    app_id: str | int,
    sandbox_id: str | int,
    target_dir: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    include_xml: bool = True,
) -> dict:
    file_path, file_size = find_jar(target_dir)
    url = f"{api_base}/api/5.0/uploadfile.do"
    data: dict[str, Any] = {"app_id": str(app_id), "sandbox_id": str(sandbox_id)}
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        files = {"file": (filename, f)}
        resp = requests.post(url, data=data, files=files, auth=auth, timeout=300)
    resp.raise_for_status()
    out = save_xml_and_normalize_return(
        xml_text=resp.text,
        xml_filename="uploadfile_response.xml",
        json_filename="normalize_uploadfile_response.json",
        normalizer_fn=normalize_uploadfile_response_to_json,
        include_xml_in_response=include_xml,
        xml_preview_chars=2000,
    )
    out["uploaded_jar"] = str(file_path)
    out["uploaded_jar_size_bytes"] = file_size
    return out

def begin_prescan(
    app_id: str,
    sandbox_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    auto_scan: bool = False,
    scan_all_nonfatal_top_level_modules: bool = False,
    include_new_modules: bool = False,
    include_xml: bool = True,
) -> dict:
    url = f"{api_base}/api/5.0/beginprescan.do"
    data: dict[str, Any] = {"app_id": str(app_id), "auto_scan": "true" if auto_scan else "false"}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    if auto_scan:
        data["scan_all_nonfatal_top_level_modules"] = "true" if scan_all_nonfatal_top_level_modules else "false"
        if scan_all_nonfatal_top_level_modules:
            data["include_new_modules"] = "true" if include_new_modules else "false"
    resp = requests.post(url, data=data, auth=auth, timeout=120)
    resp.raise_for_status()
    return save_xml_and_normalize_return(
        xml_text=resp.text,
        xml_filename="beginprescan_response.xml",
        json_filename="normalize_beginprescan_response.json",
        normalizer_fn=normalize_beginprescan_response_to_json,
        include_xml_in_response=include_xml,
        xml_preview_chars=2000,
    )

def poll_prescan_until_complete(
    app_id: str,
    sandbox_id: str,
    build_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    poll_interval: int = 15,
    timeout: int = 900,
    include_xml: bool = True,
) -> dict:
    url = f"{api_base}/api/5.0/getprescanresults.do"
    data: dict[str, Any] = {"app_id": str(app_id), "sandbox_id": str(sandbox_id), "build_id": str(build_id)}
    IN_PROGRESS_STATES = {"Queued", "Pre-Scan Submitted", "Pre-Scan Running"}
    start = time.time()
    attempt = 0
    last_xml = ""
    last_statuses: set[str] = set()

    while True:
        attempt += 1
        resp = requests.post(url, data=data, auth=auth, timeout=60)
        if resp.status_code in (429, 502, 503, 504):
            time.sleep(min(5 * attempt, 30))
            continue
        resp.raise_for_status()
        last_xml = resp.text

        root = ET.fromstring(last_xml)
        module_statuses = {m.attrib.get("status", "").strip() for m in root.findall(".//{*}module")}
        last_statuses = module_statuses

        if not module_statuses:
            if time.time() - start > timeout:
                break
            time.sleep(poll_interval)
            continue

        if any(s in IN_PROGRESS_STATES for s in module_statuses):
            if time.time() - start > timeout:
                break
            time.sleep(poll_interval)
            continue

        out = save_xml_and_normalize_return(
            xml_text=last_xml,
            xml_filename="getprescanresults_response.xml",
            json_filename="normalized_getprescanresults_response.json",
            normalizer_fn=normalize_getprescanresults_response_to_json,
            include_xml_in_response=include_xml,
            xml_preview_chars=2000,
        )
        return {"message": "Prescan completed.", "statuses": list(module_statuses), "polls": attempt, "output": out}

    # timeout
    out = save_xml_and_normalize_return(
        xml_text=last_xml,
        xml_filename="getprescanresults_response.xml",
        json_filename="normalized_getprescanresults_response_timeout.json",
        normalizer_fn=normalize_getprescanresults_response_to_json,
        include_xml_in_response=include_xml,
        xml_preview_chars=2000,
    )
    return {"message": "Timed out while waiting for prescan to complete.", "statuses": list(last_statuses), "polls": attempt, "output": out}

def begin_final_scan(
    app_id: str,
    sandbox_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    scan_all_top_level_modules: bool = True,
    scan_previously_selected_modules: bool = False,
    modules: Optional[str] = None,
    include_xml: bool = True,
) -> dict:
    url = f"{api_base}/api/5.0/beginscan.do"
    data: dict[str, Any] = {"app_id": str(app_id)}
    if modules:
        data["modules"] = modules
    else:
        data["scan_all_top_level_modules"] = "true" if scan_all_top_level_modules else "false"
        if scan_previously_selected_modules:
            data["scan_previously_selected_modules"] = "true"
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    resp = requests.post(url, data=data, auth=auth, timeout=180)
    resp.raise_for_status()
    return save_xml_and_normalize_return(
        xml_text=resp.text,
        xml_filename="beginscan_response.xml",
        json_filename="normalized_beginscan_response.json",
        normalizer_fn=normalize_beginscan_response_to_json,
        include_xml_in_response=include_xml,
        xml_preview_chars=2000,
    )

def poll_final_scan_until_complete(
    app_id: str,
    sandbox_id: str,
    build_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    poll_interval: int = 20,
    timeout: int = 3600,
    include_xml: bool = True,
) -> dict:
    url = f"{api_base}/api/5.0/getbuildinfo.do"
    data: dict[str, Any] = {"app_id": str(app_id), "sandbox_id": str(sandbox_id), "build_id": str(build_id)}
    start = time.time()
    attempt = 0
    last_xml = ""
    results_ready = None

    while True:
        attempt += 1
        resp = requests.post(url, data=data, auth=auth, timeout=60)
        if resp.status_code in (429, 502, 503, 504):
            time.sleep(min(5 * attempt, 30))
            continue
        resp.raise_for_status()
        last_xml = resp.text

        root = ET.fromstring(last_xml)
        build_elem = root.find(".//{*}build")
        if build_elem is None:
            if time.time() - start > timeout:
                break
            time.sleep(poll_interval)
            continue

        results_ready = (build_elem.attrib.get("results_ready", "") or "").lower()
        if results_ready == "true":
            out = save_xml_and_normalize_return(
                xml_text=last_xml,
                xml_filename="getfinalscanresults_response.xml",
                json_filename="normalized_getfinalscanresults_response.json",
                normalizer_fn=normalize_getfinalscanresults_response_to_json,
                include_xml_in_response=include_xml,
                xml_preview_chars=2000,
            )
            return {"message": "Final scan completed successfully.", "attempts": attempt, "results_ready": results_ready, "output": out}

        if time.time() - start > timeout:
            break
        time.sleep(poll_interval)

    out = save_xml_and_normalize_return(
        xml_text=last_xml,
        xml_filename="getfinalscanresults_response.xml",
        json_filename="normalized_getfinalscanresults_response_timeout.json",
        normalizer_fn=normalize_getfinalscanresults_response_to_json,
        include_xml_in_response=include_xml,
        xml_preview_chars=2000,
    )
    return {"message": "Timed out before full scan completed.", "attempts": attempt, "results_ready": results_ready, "output": out}

def get_detailed_report(
    build_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    output_file: str = "normalized_detailedreport_response.json",
    timeout: int = 180,
    include_full_xml: bool = False,
) -> dict:
    url = f"{api_base}/api/5.0/detailedreport.do"
    data: dict[str, Any] = {"build_id": str(build_id)}
    resp = requests.post(url, data=data, auth=auth, timeout=timeout)
    resp.raise_for_status()
    return save_xml_and_normalize_return(
        xml_text=resp.text,
        xml_filename="detailedreport_response.xml",
        json_filename=output_file,
        normalizer_fn=normalize_detailedreport_response_to_json,
        include_xml_in_response=include_full_xml,
        xml_preview_chars=5000,
    )


# -------------------------
# Full pipeline wrapper
# -------------------------

def run_bitbucket_zip_veracode_pipeline(
    *,
    bb_base_url: str,
    bb_project: str,
    bb_repo: str,
    bb_at: Optional[str],
    bb_token: str,
    bb_insecure: bool,
    workspace_root: str,

    app_id: str,
    sandbox_id: str,
    version: str,

    veracode_api_key_id: str,
    veracode_api_key_secret: str,
    veracode_api_base: str = "https://analysiscenter.veracode.com",

    poll_interval: int = 15,
    prescan_timeout: int = 900,
    final_scan_timeout: int = 3600,

    include_xml: bool = True,
    include_full_detailedreport_xml: bool = False,
    keep_workspace: bool = True,
) -> dict:
    """Run the full pipeline and return combined outputs."""
    workspace = make_run_workspace(workspace_root, bb_repo)
    zip_dir = os.path.join(workspace, "zip")
    extract_dir = os.path.join(workspace, "unzipped")

    old_cwd = os.getcwd()
    os.chdir(workspace)

    try:
        auth = RequestsAuthPluginVeracodeHMAC(
            api_key_id=veracode_api_key_id,
            api_key_secret=veracode_api_key_secret,
        )

        zip_path = download_bitbucket_archive_zip_to_disk(
            base_url=bb_base_url,
            project=bb_project,
            repo=bb_repo,
            at=bb_at,
            out_dir=zip_dir,
            token=bb_token,
            insecure=bb_insecure,
            overwrite=True,
        )

        unzip_dir = unzip_file(zip_path, extract_dir)
        maven_root = find_maven_root(unzip_dir)
        run_maven_build_simple(maven_root)

        createbuild_out = create_new_build(
            app_id=app_id,
            sandbox_id=sandbox_id,
            version=version,
            auth=auth,
            api_base=veracode_api_base,
            include_xml=include_xml,
        )
        build_id = createbuild_out.get("build_id", "unknown")

        upload_out = upload_file(
            app_id=app_id,
            sandbox_id=sandbox_id,
            target_dir=maven_root,
            auth=auth,
            api_base=veracode_api_base,
            include_xml=include_xml,
        )

        beginprescan_out = begin_prescan(
            app_id=app_id,
            sandbox_id=sandbox_id,
            auth=auth,
            api_base=veracode_api_base,
            include_xml=include_xml,
        )

        prescan_poll_out = poll_prescan_until_complete(
            app_id=app_id,
            sandbox_id=sandbox_id,
            build_id=build_id,
            auth=auth,
            api_base=veracode_api_base,
            poll_interval=poll_interval,
            timeout=prescan_timeout,
            include_xml=include_xml,
        )

        beginscan_out = begin_final_scan(
            app_id=app_id,
            sandbox_id=sandbox_id,
            auth=auth,
            api_base=veracode_api_base,
            include_xml=include_xml,
        )

        final_poll_out = poll_final_scan_until_complete(
            app_id=app_id,
            sandbox_id=sandbox_id,
            build_id=build_id,
            auth=auth,
            api_base=veracode_api_base,
            poll_interval=max(20, poll_interval),
            timeout=final_scan_timeout,
            include_xml=include_xml,
        )

        detailed_out = get_detailed_report(
            build_id=build_id,
            auth=auth,
            api_base=veracode_api_base,
            include_full_xml=include_full_detailedreport_xml,
        )

        return {
            "status": "success",
            "workspace": workspace,
            "bitbucket": {
                "zip_path": zip_path,
                "extract_dir": extract_dir,
                "maven_root": maven_root,
                "project": bb_project,
                "repo": bb_repo,
                "at": bb_at or "default",
            },
            "veracode": {
                "app_id": app_id,
                "sandbox_id": sandbox_id,
                "version": version,
                "build_id": build_id,
                "createbuild": createbuild_out,
                "uploadfile": upload_out,
                "beginprescan": beginprescan_out,
                "getprescanresults": prescan_poll_out,
                "beginscan": beginscan_out,
                "getfinalscanresults": final_poll_out,
                "detailedreport": detailed_out,
            },
        }

    except Exception as e:
        return {"status": "error", "workspace": workspace, "message": str(e)}
    finally:
        os.chdir(old_cwd)
        if not keep_workspace:
            shutil.rmtree(workspace, ignore_errors=True)
