from http.client import HTTPException
import os
import shutil
import subprocess
import sys
import zipfile
import time
import xml.etree.ElementTree as ET
import pathlib
from pathlib import Path
from io import BytesIO
import re
import requests
from dotenv import load_dotenv
from typing import Optional, Tuple
from veracode_api_signing.plugin_requests import RequestsAuthPluginVeracodeHMAC
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))  # Ensure current directory is in sys.path for imports
from packages.shared.shared.normalize_xml_functions import *
from packages.shared.shared.finding_functions import fetch_veracode_sca_scan_results, fetch_veracode_static_scan_results
from packages.shared.shared.firestore_client import FirestoreClientHandler

load_dotenv()

api_key_id = os.getenv("VERACODE_API_KEY_ID")
api_key_secret = os.getenv("VERACODE_API_KEY_SECRET")
app_id = os.getenv("VERACODE_APP_ID")
sandbox_id = os.getenv("VERACODE_SANDBOX_ID")
auth = RequestsAuthPluginVeracodeHMAC(
    api_key_id=api_key_id,
    api_key_secret=api_key_secret
)

# Initializing Firestore client
firestore_client = FirestoreClientHandler()

# --------------------------------------------------------- Download ZIP from Bitbucket ---------------------------------------------------------
def _auth_headers(token: str, scheme: str) -> dict:
    return {"Authorization": f"{scheme} {token}"}

def _get_stream_with_token(url: str, token: str, params: dict, verify_ssl: bool = True) -> requests.Response:
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
    return last_resp

def _safe_filename(name: str) -> str:
    # keep it filesystem-safe
    name = name.strip().replace("\n", " ")
    name = re.sub(r'[^A-Za-z0-9._-]+', "_", name)
    return name or "archive.zip"

def _filename_from_cd(content_disposition: str | None) -> str | None:
    if not content_disposition:
        return None
    # handles: attachment; filename="repo.zip"
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, re.IGNORECASE)
    return m.group(1) if m else None

def download_repo_zip_to_path(
    repo_id: str,
    branch: str,
    base_url: str = "https://coxrepo.corp.cox.com/stash",
    project: str = "CCPT",
    out_dir: str = None,
    filename: str = None,
    overwrite: bool = False,
    insecure: bool = False,
):
    token = os.getenv("BITBUCKET_TOKEN")
    if not token:
        raise ValueError("BITBUCKET_TOKEN environment variable is required for authentication.")
 
    base_url = base_url.rstrip("/")
    archive_url = f"{base_url}/rest/api/1.0/projects/{project}/repos/{repo_id}/archive"
 
    params = {"format": "zip"}
    if branch:
        params["at"] = branch
 
    resp = _get_stream_with_token(archive_url, token, params=params, verify_ssl=(not insecure))
 
    if resp.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Auth failed. Check token and REPO_READ permission.")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Not found. Check base_url/project/repo and 'at'.")
    resp.raise_for_status()
 
    # Decide output filename
    cd_name = _filename_from_cd(resp.headers.get("Content-Disposition"))
    out_name = filename or cd_name or f"{repo_id}-{(branch or 'default')}.zip"
    out_name = _safe_filename(out_name)
 
    # Ensure output directory exists
    out_path = pathlib.Path(out_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)
 
    file_path = out_path / out_name
 
    if file_path.exists() and not overwrite:
        raise HTTPException(
            status_code=409,
            detail=f"File already exists: {str(file_path)} (set overwrite=true or change filename)",
        )
 
    # Stream to disk
    bytes_written = 0
    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                bytes_written += len(chunk)
 
    return str(file_path)

# --------------------------------------------------------- Veracode Scan Pipeline Functions ---------------------------------------------------------

def unzip_file(zip_path: str):
    """
    Unzips the given ZIP file into the specified directory.
    
    Parameters:
        zip_path (str): Path to the downloaded ZIP file.
        extract_to (str): Directory where files will be extracted.

    Notes:
        - Creates the extract directory if it does not exist.
        - Overwrites existing files if same names exist.
    """

    zip_path = Path(zip_path)
    extract_folder = "unzipped_output"

    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    extract_to = zip_path.parent / extract_folder
    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Unzipped files to: {extract_to}")
    return extract_to.resolve()

def run_maven_build_simple(project_dir: str):
    """
    Runs the exact Maven command:
        mvn clean package -DskipTests -Djib.skip="true"
    in the specified project directory.
    """

    project_path = Path(project_dir).resolve()
    pom_file = project_path / "pom.xml"

    if not pom_file.exists():
        raise FileNotFoundError(f"pom.xml not found in: {project_path}")

    # Exact command you run manually in Windows
    command = 'mvn clean package -DskipTests -Djib.skip="true"'

    print(f"Running Maven in {project_path} ...")
    print("Command:", command)

    # Run the command (shell=True is allowed on Windows for mvn usage)
    result = subprocess.run(
        command,
        cwd=str(project_path),
        shell=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Maven build failed with exit code {result.returncode}"
        )

    print("Maven build SUCCESS.")
    target_jar = project_path / "target"
    jar_files = list(target_jar.glob("*.jar"))
    if jar_files:
        # Large jar file found, print its name
        print(f"Generated JAR file: {jar_files[0].name}")
        large_jar_path = target_jar / jar_files[0].name
        print(f"Size of generated JAR: {large_jar_path.stat().st_size} bytes")
    return large_jar_path

def create_new_build(
    app_id: str,
    sandbox_id: str,
    version: str,
    auth=None,
    api_base: str = "https://analysiscenter.veracode.com"
):
    """
    Creates a new build (version) in the specified sandbox using createbuild.do.
    Saves the XML response to 'createbuild_response.xml'.

    Veracode XML API:
      - Endpoint: /api/5.0/createbuild.do
      - Required: app_id
      - Optional: sandbox_id
      - version: unique build name (e.g., 'testscan_3')
    """
    endpoint = "api/5.0/createbuild.do"
    url = f"{api_base}/{endpoint}"

    # Send fields as form data (let 'requests' set Content-Type)
    data = {
        "app_id": str(app_id),
        "version": version
    }
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)

    resp = requests.post(url, data=data, auth=auth, timeout=120)
    resp.raise_for_status()

    # with open("createbuild_response.xml", "w", encoding="utf-8") as f:
    #     f.write(resp.text)
    
    try:
        # Parse XML response to extract build_id
        root = ET.fromstring(resp.text)
        build_id = root.attrib.get("build_id")
    except ET.ParseError:
        print("Failed to parse XML response for build_id.")

    return build_id

def find_jar(target_dir: str) -> Tuple[Path, int]:
    """
    Recursively search target_dir for .jar files and return the path and size (bytes)
    of the largest one. Raises FileNotFoundError if none found.
    """
    target_path = Path(target_dir).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f"Target directory not found: {target_path}")

    jars = list(target_path.rglob("*.jar"))
    if not jars:
        raise FileNotFoundError(f"No .jar files found under: {target_path}")

    largest = max(jars, key=lambda p: p.stat().st_size)
    return largest, largest.stat().st_size

def upload_file(
    app_id: str | int,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    sandbox_id: Optional[str | int] = None,
    target_dir: Optional[str] = None,
    timeout_seconds: int = 900,
) -> str:
    """
    Uploads a file to Veracode using uploadfile.do with HMAC auth.
    - Sends parameters as multipart form fields (NOT query params).
    - Lets `requests` set Content-Type and boundaries.
    """

    # Locate JAR
    if not target_dir:
        raise ValueError("target_dir must be provided for upload_file.")

    file_path, file_size = find_jar(target_dir)

    # 2) Prepare endpoint and params per Veracode docs
    endpoint = "api/5.0/uploadfile.do"
    url = f"{api_base}/{endpoint}" # US region default; change base for EU/Fed as needed

    # Build form fields (only include sandbox_id if provided)
    data = {"app_id": str(app_id)}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    
    # Use a filename so the service sees the correct name
    filename = os.path.basename(file_path)

    # Do NOT set Content-Type yourself; requests will handle boundary correctly
    with open(file_path, "rb") as f:
        files = {"file": (filename, f)}  # multipart/form-data part
        resp = requests.post(url, data=data, files=files, auth=auth, timeout=300)

    # Raise for HTTP errors; persist response XML
    resp.raise_for_status()
    # with open("uploadfile_response.xml", "w", encoding="utf-8") as out:
    #     out.write(resp.text)

    return f"File uploaded successfully."

def begin_prescan(app_id: str, sandbox_id: str, auth, api_base="https://analysiscenter.veracode.com",
                  auto_scan: bool = False,
                  scan_all_nonfatal_top_level_modules: bool = False,
                  include_new_modules: bool = False):
    """
    Starts a prescan on the most recent build for the given app (and optional sandbox).
    Saves the XML response as 'beginprescan_response.xml'.

    Parameters map to Veracode XML API:
      - app_id (required)
      - sandbox_id (optional)
      - auto_scan (optional): if True, a full scan starts automatically after prescan
      - scan_all_nonfatal_top_level_modules (optional): used when auto_scan=True
      - include_new_modules (optional): used when auto_scan=True and scan_all_nonfatal_top_level_modules=True
    """
    endpoint = "api/5.0/beginprescan.do"
    url = f"{api_base}/{endpoint}"

    # Build form fields (send as multipart/form-data or application/x-www-form-urlencoded; requests handles both)
    data = {
        "app_id": str(app_id),
        "auto_scan": "true" if auto_scan else "false",
    }
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    if auto_scan:
        data["scan_all_nonfatal_top_level_modules"] = "true" if scan_all_nonfatal_top_level_modules else "false"
        if scan_all_nonfatal_top_level_modules:
            data["include_new_modules"] = "true" if include_new_modules else "false"

    # Important: do NOT set Content-Type manually; let 'requests' set it.
    resp = requests.post(url, data=data, auth=auth, timeout=120)
    resp.raise_for_status()

    # with open("beginprescan_response.xml", "w", encoding="utf-8") as f:
    #     f.write(resp.text)

    return f"Prescan started."

def poll_prescan_until_complete(
    app_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    sandbox_id: str | None = None,
    build_id: str | None = None,
    poll_interval: int = 15,     # seconds between polls
    timeout: int = 900,          # overall timeout in seconds (e.g., 15 minutes)
    save_every_poll: bool = False
):
    """
    Repeatedly calls getprescanresults.do until prescan completes or times out.
    Saves the final XML to 'getprescanresults_response.xml'.

    Parameters map to Veracode XML API:
      - app_id (required)
      - sandbox_id (optional)
      - build_id (optional)
    """
    endpoint = "api/5.0/getprescanresults.do"
    url = f"{api_base}/{endpoint}"
    IN_PROGRESS_STATES = {"Queued", "Pre-Scan Submitted", "Pre-Scan Running"}

    data = {"app_id": str(app_id)}
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    if build_id:
        data["build_id"] = str(build_id)

    start = time.time()
    attempt = 0

    while True:
        attempt += 1
        resp = requests.post(url, data=data, auth=auth, timeout=60)
        # Retry briefly on transient 5xx/429
        if resp.status_code in (429, 502, 503, 504):
            time.sleep(min(5 * attempt, 30))
            continue

        resp.raise_for_status()
        xml_text = resp.text

        # Optionally persist each poll for troubleshooting
        if save_every_poll:
            with open(f"getprescanresults_poll_{attempt}.xml", "w", encoding="utf-8") as tmp:
                tmp.write(xml_text)

        # Parse <prescanresults> and inspect module statuses
        root = ET.fromstring(xml_text)
        # modules are <module ... status="...">
        module_statuses = {m.attrib.get("status", "").strip() for m in root.findall(".//{*}module")}

        # If there are no modules yet, keep polling briefly (prescan queueing)
        if not module_statuses:
            if time.time() - start > timeout:
                break
            time.sleep(poll_interval)
            continue

        # If ANY module is still in an in-progress state, keep waiting
        if any(status in IN_PROGRESS_STATES for status in module_statuses):
            # Stop if we exceed the timeout
            if time.time() - start > timeout:
                break
            time.sleep(poll_interval)
            continue

        # Otherwise, prescan has completed (successfully or with errors)
        # with open("getprescanresults_response.xml", "w", encoding="utf-8") as f:
        #     f.write(xml_text)

        time.sleep(5)  # brief pause to ensure file is fully written before normalization

        # normalized_result = normalize_getprescanresults_response_to_json("getprescanresults_response.xml")  # Normalize for easier consumption
        # with open("normalized_getprescanresults_response.json", "w") as f:
        #     json.dump(normalized_result, f, indent=4)

        return {
            "message": "Prescan completed.",
            "statuses": list(module_statuses),
            "polls": attempt
        }

    # If we exited the loop due to timeout, save the latest we have
    # with open("getprescanresults_response.xml", "w", encoding="utf-8") as f:
    #         f.write(xml_text)

    time.sleep(10)  # brief pause to ensure file is fully written before normalization

    normalized_result = normalize_getprescanresults_response_to_json("getprescanresults_response.xml")  # Normalize for easier consumption
    with open("normalized_getprescanresults_response_timeout.json", "w") as f:
        json.dump(normalized_result, f, indent=4)

    return {
        "message": "Timed out while waiting for prescan to complete.",
        "statuses": list(module_statuses) if 'module_statuses' in locals() else [],
        "polls": attempt
    }

def begin_final_scan(
    app_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    sandbox_id: str | None = None,
    # Choose one of the module-selection strategies below:
    scan_all_top_level_modules: bool = True,
    scan_previously_selected_modules: bool = False,
    # If you want to select explicit modules, pass a comma-separated string via `modules`
    modules: str | None = None
):
    """
    Initiates a full static scan using beginscan.do and saves the XML response
    to 'beginscan_response.xml'.

    Requirements:
      - app_id (required)
      - One of:
          * scan_all_top_level_modules (true/false)
          * scan_previously_selected_modules (true/false)
          * modules (comma-separated module names)
      - sandbox_id (optional)
    """
    endpoint = "api/5.0/beginscan.do"
    url = f"{api_base}/{endpoint}"

    # Build form fields (let 'requests' set Content-Type automatically)
    data = {
        "app_id": str(app_id),
    }

    # Module selection (ensure at least one strategy is provided)
    if modules:
        data["modules"] = modules
    else:
        # Default to scanning all top-level modules unless user overrides
        data["scan_all_top_level_modules"] = "true" if scan_all_top_level_modules else "false"
        if scan_previously_selected_modules:
            data["scan_previously_selected_modules"] = "true"

    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)

    resp = requests.post(url, data=data, auth=auth, timeout=180)
    resp.raise_for_status()

    # with open("beginscan_response.xml", "w", encoding="utf-8") as f:
    #     f.write(resp.text)

    return "Final scan started."

def poll_final_scan_until_complete(
    app_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    sandbox_id: str | None = None,
    build_id: str | None = None,
    poll_interval: int = 20,      # seconds between polls
    timeout: int = 3600           # 1 hour timeout
):
    """
    Polls getbuildinfo.do until results_ready="true".
    Saves the final XML response to 'getbuildinfo_response.xml'.
    """

    endpoint = "api/5.0/getbuildinfo.do"
    url = f"{api_base}/{endpoint}"

    # Required parameter
    data = {"app_id": str(app_id)}

    # Optional parameters
    if sandbox_id:
        data["sandbox_id"] = str(sandbox_id)
    if build_id:
        data["build_id"] = str(build_id)

    start = time.time()
    attempt = 0

    while True:
        attempt += 1
        resp = requests.post(url, data=data, auth=auth, timeout=60)

        # Handle transient failures
        if resp.status_code in (429, 502, 503, 504):
            time.sleep(min(5 * attempt, 30))
            continue

        resp.raise_for_status()
        xml_text = resp.text
        root = ET.fromstring(xml_text)

        # Extract <build ... results_ready="..."> attribute
        build_elem = root.find(".//{*}build")
        if build_elem is None:
            # No build information yet — keep polling
            if time.time() - start > timeout:
                break
            time.sleep(poll_interval)
            continue

        results_ready = build_elem.attrib.get("results_ready", "").lower()

        # Stop when results_ready="true"
        if results_ready == "true":
            # Save last XML in timeout case
            # with open("getfinalscanresults_response.xml", "w", encoding="utf-8") as f:
            #     f.write(xml_text)

            time.sleep(5)  # brief pause to ensure file is fully written before normalization

            # normalized_result = normalize_getfinalscanresults_response_to_json("getfinalscanresults_response.xml")  # Normalize for easier consumption
            # with open("normalized_getfinalscanresults_response.json", "w") as f:
            #     json.dump(normalized_result, f, indent=4)
            return {
                "message": "Final scan completed successfully.",
                "attempts": attempt,
                "results_ready": results_ready
            }

        # Timeout?
        if time.time() - start > timeout:
            break

        # Not ready yet — wait and poll again
        time.sleep(poll_interval)

    # Save last XML in timeout case
    with open("getfinalscanresults_response.xml", "w", encoding="utf-8") as f:
        f.write(xml_text)
    time.sleep(5)  # brief pause to ensure file is fully written before normalization

    normalized_result = normalize_getfinalscanresults_response_to_json("getfinalscanresults_response.xml")  # Normalize for easier consumption
    with open("normalized_getfinalscanresults_response_timeout.json", "w") as f:
        json.dump(normalized_result, f, indent=4)

    return {
        "message": "Timed out before full scan completed.",
        "attempts": attempt,
        "results_ready": results_ready if 'results_ready' in locals() else None
    }

def get_detailed_report(
    build_id: str,
    auth,
    api_base: str = "https://analysiscenter.veracode.com",
    timeout: int = 180
):
    """
    Downloads the Detailed Report XML for the specified build and saves it
    to `output_file`.

    Veracode XML API:
      - Endpoint: /api/5.0/detailedreport.do
      - Required: build_id
      - Returns: <detailedreport ...> XML
    """
    endpoint = "api/5.0/detailedreport.do"
    url = f"{api_base}/{endpoint}"

    # Send required field as form data (do NOT set Content-Type manually)
    data = {"build_id": str(build_id)}

    # requests will automatically set Accept-Encoding to handle gzip if supported
    resp = requests.post(url, data=data, auth=auth, timeout=timeout)
    resp.raise_for_status()

    normalized_result = normalize_detailedreport_response_to_json(xml_text=resp.text)  # Normalize for easier consumption
    normalized_result = {"results": normalized_result}
    # with open(output_file, "w") as f:
    #     json.dump(normalized_result, f, indent=4)
    
    # Save to Firestore
    collection_name = "sample_collection_veracode_response"
    document_id = f"detailed_report_{build_id}"  # You can customize this ID as needed
    firestore_client.write_scan_result(collection_name, document_id, normalized_result)

    return f"Detailed report saved to Firestore with collection_name={collection_name}, document_id={document_id}"

def get_static_report(build_id: str):
    # Placeholder for fetching static scan report if needed
    findings_static = fetch_veracode_static_scan_results(is_sandbox_scan=True)
    data = {"results": findings_static}
    collection_name = "sample_collection_veracode_response"
    document_id = f"static_report_{build_id}"  # You can customize this ID as needed

    # with open("static_scan_findings.json", "w") as f:
    #     json.dump(findings, f, indent=4)

    # Save to Firestore
    firestore_client.write_scan_result(collection_name, document_id, data)

    return f"Static scan findings saved to Firestore with collection_name={collection_name}, document_id={document_id}"

def get_sca_report(build_id: str):
    # Placeholder for fetching SCA scan report if needed
    findings_sca = fetch_veracode_sca_scan_results(is_sandbox_scan=True)
    data = {"results": findings_sca}
    collection_name = "sample_collection_veracode_response"
    document_id = f"sca_report_{build_id}"  # You can customize this ID as needed

    # with open("sca_scan_findings.json", "w") as f:
    #     json.dump(findings, f, indent=4)

    # Save to Firestore
    firestore_client.write_scan_result(collection_name, document_id, data)
    return f"SCA scan findings saved to Firestore with collection_name={collection_name}, document_id={document_id}"

def create_master_report():
    # Placeholder for creating a master report that combines static, SCA, and detailed report findings
    pass

def clear_directory(target_dir: str):
    """
    Deletes:
    - All ZIP files inside target_dir
    - All folders inside target_dir (regardless of name)

    Leaves all non-ZIP files untouched.
    """

    if not os.path.isdir(target_dir):
        raise ValueError(f"Directory not found: {target_dir}")

    for item in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item)

        # Delete zip files
        if item.lower().endswith(".zip") and os.path.isfile(item_path):
            print(f"Deleting ZIP file: {item_path}")
            os.remove(item_path)
            continue

        # Delete any folder
        if os.path.isdir(item_path):
            print(f"Deleting folder: {item_path}")
            shutil.rmtree(item_path)
            continue

    print("Directory cleanup completed!")

def vercode_pipeline_scan(
    app_id: str,
    sandbox_id: str,
    repo_id: str,
    branch: str,
    commit_sha: Optional[str],
    download_dir: str,
    scan_type: str = "STATIC",
    api_base: str = "https://analysiscenter.veracode.com",
    version: str=None,
    auto_scan: bool = False,
    scan_all_nonfatal_top_level_modules: bool = False,
    include_new_modules: bool = False,
    poll_interval: int = 15,
    prescan_timeout: int = 900,
    final_scan_timeout: int = 3600
    ):
    """
    Runs the full Veracode scan pipeline:
      1) Create a new build (version) in the specified sandbox
      2) Find and upload the largest JAR from zip_path
      3) Start a prescan and wait for it to complete
      4) Optionally start a full scan after prescan
      5) Wait for the full scan to complete
      6) Download the detailed report XML
    """
    print(f"Starting Veracode scan pipeline for app_id={app_id}, sandbox_id={sandbox_id}, version={version}")
    print("I am here")
    try:
        # Step 1: Download source code as ZIP from Bitbucket repository
        # <Placeholder: You can implement this step using Bitbucket's API or by other means as needed.>
        zip_path = download_repo_zip_to_path(out_dir=download_dir, repo_id=repo_id, branch=branch)
        print(f"Step 1 Passed: Downloaded ZIP from Bitbucket successfully to: {zip_path}")

        # Step 2: Unzip the target directory if it's a ZIP file (optional, based on your workflow)
        try:
            unzip_dir = unzip_file(zip_path)
            print(f"Step 2 Passed: Unzipped target directory successfully to: {unzip_dir}")
        except Exception as e:
            raise ValueError(f"Failed to unzip target directory: {e}")

        # Step 3: Run Maven build to generate JARs
        try:
            jar_path = run_maven_build_simple(unzip_dir)
            print(f"Step 3 Passed: Maven build completed successfully. JAR found at: {jar_path}")
        except Exception as e:
            raise ValueError(f"Failed to run Maven build: {e}")

        # Step 4: Create a new build in Veracode
        try:
            build_id = create_new_build(app_id, sandbox_id, version, auth=auth, api_base=api_base)
            print(f"Step 4 Passed: Created new build in Veracode with build_id: {build_id}")
        except Exception as e:
            raise ValueError(f"Failed to create new build: {e}")

        # Step 5: Upload the JAR to Veracode
        try:
            upload_file(app_id=app_id, sandbox_id=sandbox_id, auth=auth, api_base=api_base, target_dir=unzip_dir)
            print(f"Step 5 Passed: Uploaded JAR to Veracode successfully.")
        except Exception as e:
            raise ValueError(f"Failed to upload JAR: {e}")

        # Step 6: Start prescan
        try:
            begin_prescan(app_id, sandbox_id, auth=auth, api_base=api_base, auto_scan=auto_scan,
                        scan_all_nonfatal_top_level_modules=scan_all_nonfatal_top_level_modules,
                        include_new_modules=include_new_modules)
            print(f"Step 6 Passed: Prescan started successfully.")
        except Exception as e:
            raise ValueError(f"Failed to start prescan: {e}")

        # Step 7: Poll until prescan completes
        try:
            poll_prescan_until_complete(app_id, auth=auth, api_base=api_base, sandbox_id=sandbox_id, build_id=build_id,
                                       poll_interval=poll_interval, timeout=prescan_timeout)
            print(f"Step 7 Passed: Prescan completed successfully.")
        except Exception as e:
            raise ValueError(f"Failed to poll prescan completion: {e}")

        # Step 8: Optionally start the full scan
        try:
            begin_final_scan(app_id, auth=auth, api_base=api_base, sandbox_id=sandbox_id,
                             scan_all_top_level_modules=True,  # or False if you want to specify modules
                             scan_previously_selected_modules=False)
            print(f"Step 8 Passed: Final scan started successfully.")
        except Exception as e:
            raise ValueError(f"Failed to start final scan: {e}")

        # Step 9: Poll until full scan completes
        try:
            poll_final_scan_until_complete(app_id, auth=auth, api_base=api_base, sandbox_id=sandbox_id, build_id=build_id,
                                       poll_interval=poll_interval, timeout=final_scan_timeout)
            print(f"Step 9 Passed: Final scan completed successfully.")
        except Exception as e:
            raise ValueError(f"Failed to poll final scan completion: {e}")

        # Step 10: Get the detailed report JSON
        try:
            get_detailed_report(build_id, auth=auth, api_base=api_base)
            print(f"Step 10 Passed: Detailed report saved to firestore successfully.")
        except Exception as e:
            raise ValueError(f"Failed to get detailed report: {e}")
        
        # Step 11: Get Static findings JSON
        try:
            get_static_report(build_id)
            print(f"Step 11 Passed: Static scan report saved to firestore successfully.")
        except Exception as e:
            raise ValueError(f"Failed to get static scan findings: {e}")
        
        # Step 12: Get SCA findings JSON
        try:
            get_sca_report(build_id)
            print(f"Step 12 Passed: SCA scan report saved to firestore successfully.")
        except Exception as e:
            raise ValueError(f"Failed to get SCA scan findings: {e}")
        
        # Step 13: (Optional) Create a master report combining all findings
        # <Placeholder: Implement as needed based on your reporting requirements.>

        # Step 14: (Optional) Clean up any temporary files or directories if needed
        clear_directory(download_dir)

        return {
            "status": "success",
            "message": "Veracode scan pipeline completed successfully."
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
