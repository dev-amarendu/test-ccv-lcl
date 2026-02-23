"""This script normalizes Veracode XML API responses for consistent processing."""
import json
import xml.etree.ElementTree as ET

# normalizing createbuild_response.xml
def normalize_createbuild_response_to_json(xml_file):
    """Normalize the createbuild_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Remove namespaces for easier access
    for elem in root.iter():
        elem.tag = elem.tag.split('}')[-1]

    normalized = []

    # Extract relevant information
    build_info = {
        'buildinfo_version': root.attrib.get('buildinfo_version'),
        'account_id': root.attrib.get('account_id'),
        'app_id': root.attrib.get('app_id'),
        'sandbox_id': root.attrib.get('sandbox_id'),
        'build_id': root.attrib.get('build_id'),
        'build_version': root.find('.//build').attrib.get('version'),
        'submitter': root.find('.//build').attrib.get('submitter'),
        'platform': root.find('.//build').attrib.get('platform'),
        'lifecycle_stage': root.find('.//build').attrib.get('lifecycle_stage'),
        'results_ready': root.find('.//build').attrib.get('results_ready'),
        'policy_name': root.find('.//build').attrib.get('policy_name'),
        'policy_version': root.find('.//build').attrib.get('policy_version'),
        'policy_compliance_status': root.find('.//build').attrib.get('policy_compliance_status'),
        'rules_status': root.find('.//build').attrib.get('rules_status'),
        'grace_period_expired': root.find('.//build').attrib.get('grace_period_expired'),
        'scan_overdue': root.find('.//build').attrib.get('scan_overdue'),
        'legacy_scan_engine': root.find('.//build').attrib.get('legacy_scan_engine'),
        'analysis_type': root.find('.//analysis_unit').attrib.get('analysis_type'),
        'analysis_status': root.find('.//analysis_unit').attrib.get('status')
    }
    normalized.append(build_info)

    return normalized

# normalizing uploadfile_response.xml
def normalize_uploadfile_response_to_json(xml_file):
    """Normalize the uploadfile_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Remove namespaces for easier access
    for elem in root.iter():
        elem.tag = elem.tag.split('}')[-1]

    normalized = []

    # Extract relevant information from each file element
    for file_elem in root.findall('.//file'):
        file_info = {
            'filelist_version': root.attrib.get('filelist_version'),
            'account_id': root.attrib.get('account_id'),
            'app_id': root.attrib.get('app_id'),
            'sandbox_id': root.attrib.get('sandbox_id'),
            'build_id': root.attrib.get('build_id'),
            'file_id': file_elem.attrib.get('file_id'),
            'file_name': file_elem.attrib.get('file_name'),
            'file_status': file_elem.attrib.get('file_status')
        }
        normalized.append(file_info)

    return normalized

# normalizing beginprescan_response.xml
def normalize_beginprescan_response_to_json(xml_file):
    """Normalize the beginprescan_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Remove namespaces for easier access
    for elem in root.iter():
        elem.tag = elem.tag.split('}')[-1]

    normalized = []

    # Extract relevant information
    build_info = {
        'buildinfo_version': root.attrib.get('buildinfo_version'),
        'account_id': root.attrib.get('account_id'),
        'app_id': root.attrib.get('app_id'),
        'sandbox_id': root.attrib.get('sandbox_id'),
        'build_id': root.attrib.get('build_id'),
        'build_version': root.find('.//build').attrib.get('version'),
        'submitter': root.find('.//build').attrib.get('submitter'),
        'platform': root.find('.//build').attrib.get('platform'),
        'lifecycle_stage': root.find('.//build').attrib.get('lifecycle_stage'),
        'results_ready': root.find('.//build').attrib.get('results_ready'),
        'policy_name': root.find('.//build').attrib.get('policy_name'),
        'policy_version': root.find('.//build').attrib.get('policy_version'),
        'policy_compliance_status': root.find('.//build').attrib.get('policy_compliance_status'),
        'rules_status': root.find('.//build').attrib.get('rules_status'),
        'grace_period_expired': root.find('.//build').attrib.get('grace_period_expired'),
        'scan_overdue': root.find('.//build').attrib.get('scan_overdue'),
        'legacy_scan_engine': root.find('.//build').attrib.get('legacy_scan_engine'),
        'analysis_type': root.find('.//analysis_unit').attrib.get('analysis_type'),
        'analysis_status': root.find('.//analysis_unit').attrib.get('status')
    }
    normalized.append(build_info)

    return normalized

# normalizing getprescanresults_response.xml
def normalize_getprescanresults_response_to_json(xml_file):
    """Normalize the getprescanresults_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Remove namespaces for easier access
    for elem in root.iter():
        elem.tag = elem.tag.split('}')[-1]

    normalized = []

    # Extract relevant information from each module element
    for module_elem in root.findall('.//module'):
        module_info = {
            'prescanresults_version': root.attrib.get('prescanresults_version'),
            'account_id': root.attrib.get('account_id'),
            'app_id': root.attrib.get('app_id'),
            'sandbox_id': root.attrib.get('sandbox_id'),
            'build_id': root.attrib.get('build_id'),
            'module_id': module_elem.attrib.get('id'),
            'module_name': module_elem.attrib.get('name'),
            'app_file_id': module_elem.attrib.get('app_file_id'),
            'platform': module_elem.attrib.get('platform'),
            'size': module_elem.attrib.get('size'),
            'status': module_elem.attrib.get('status'),
            'has_fatal_errors': module_elem.attrib.get('has_fatal_errors'),
            'is_dependency': module_elem.attrib.get('is_dependency'),
            'issue_details': module_elem.find('.//issue').attrib.get('details') if module_elem.find('.//issue') is not None else None
        }
        normalized.append(module_info)

    return normalized

# normalizing beginscan_response.xml
def normalize_beginscan_response_to_json(xml_file):
    """Normalize the beginscan_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Remove namespaces for easier access
    for elem in root.iter():
        elem.tag = elem.tag.split('}')[-1]

    normalized = []

    # Extract relevant information
    build_info = {
        'buildinfo_version': root.attrib.get('buildinfo_version'),
        'account_id': root.attrib.get('account_id'),
        'app_id': root.attrib.get('app_id'),
        'sandbox_id': root.attrib.get('sandbox_id'),
        'build_id': root.attrib.get('build_id'),
        'build_version': root.find('.//build').attrib.get('version'),
        'submitter': root.find('.//build').attrib.get('submitter'),
        'platform': root.find('.//build').attrib.get('platform'),
        'lifecycle_stage': root.find('.//build').attrib.get('lifecycle_stage'),
        'sca_results_ready': root.find('.//build').attrib.get('sca_results_ready'),
        'results_ready': root.find('.//build').attrib.get('results_ready'),
        'policy_name': root.find('.//build').attrib.get('policy_name'),
        'policy_version': root.find('.//build').attrib.get('policy_version'),
        'policy_compliance_status': root.find('.//build').attrib.get('policy_compliance_status'),
        'rules_status': root.find('.//build').attrib.get('rules_status'),
        'grace_period_expired': root.find('.//build').attrib.get('grace_period_expired'),
        'scan_overdue': root.find('.//build').attrib.get('scan_overdue'),
        'legacy_scan_engine': root.find('.//build').attrib.get('legacy_scan_engine'),
        'analysis_type': root.find('.//analysis_unit').attrib.get('analysis_type'),
        'analysis_status': root.find('.//analysis_unit').attrib.get('status'),
        'engine_version': root.find('.//analysis_unit').attrib.get('engine_version')
    }

    normalized.append(build_info)
    return normalized

# normalizing getfinalscanresults_response.xml
def normalize_getfinalscanresults_response_to_json(xml_file):
    """Normalize the getfinalscanresults_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Remove namespaces for easier access
    for elem in root.iter():
        elem.tag = elem.tag.split('}')[-1]

    normalized = []

    # Extract relevant information
    build_info = {
        'buildinfo_version': root.attrib.get('buildinfo_version'),
        'account_id': root.attrib.get('account_id'),
        'app_id': root.attrib.get('app_id'),
        'sandbox_id': root.attrib.get('sandbox_id'),
        'build_id': root.attrib.get('build_id'),
        'build_version': root.find('.//build').attrib.get('version'),
        'submitter': root.find('.//build').attrib.get('submitter'),
        'platform': root.find('.//build').attrib.get('platform'),
        'lifecycle_stage': root.find('.//build').attrib.get('lifecycle_stage'),
        'sca_results_ready': root.find('.//build').attrib.get('sca_results_ready'),
        'results_ready': root.find('.//build').attrib.get('results_ready'),
        'policy_name': root.find('.//build').attrib.get('policy_name'),
        'policy_version': root.find('.//build').attrib.get('policy_version'),
        'policy_compliance_status': root.find('.//build').attrib.get('policy_compliance_status'),
        'rules_status': root.find('.//build').attrib.get('rules_status'),
        'grace_period_expired': root.find('.//build').attrib.get('grace_period_expired'),
        'scan_overdue': root.find('.//build').attrib.get('scan_overdue'),
        'legacy_scan_engine': root.find('.//build').attrib.get('legacy_scan_engine'),
        'analysis_type': root.find('.//analysis_unit').attrib.get('analysis_type'),
        'published_date': root.find('.//analysis_unit').attrib.get('published_date'),
        'published_date_sec': root.find('.//analysis_unit').attrib.get('published_date_sec'),
        'analysis_status': root.find('.//analysis_unit').attrib.get('status'),
        'engine_version': root.find('.//analysis_unit').attrib.get('engine_version')
    }

    normalized.append(build_info)
    return normalized

# normalizing detailedreport_response.xml
def normalize_detailedreport_response_to_json(xml_file):
    """Normalize the detailedreport_response.xml file."""
    tree = ET.parse(xml_file)
    root = tree.getroot()

    normalized = []

    report_data = {
        "report_format_version": root.attrib.get("report_format_version"),
        "account_id": root.attrib.get("account_id"),
        "analysis_id": root.attrib.get("analysis_id"),
        "app_id": root.attrib.get("app_id"),
        "app_name": root.attrib.get("app_name"),
        "assurance_level": root.attrib.get("assurance_level"),
        "build_id": root.attrib.get("build_id"),
        "business_criticality": root.attrib.get("business_criticality"),
        "business_owner": root.attrib.get("business_owner"),
        "business_unit": root.attrib.get("business_unit"),
        "first_build_submitted_date": root.attrib.get("first_build_submitted_date"),
        "flaws_not_mitigated": root.attrib.get("flaws_not_mitigated"),
        "generation_date": root.attrib.get("generation_date"),
        "grace_period_expired": root.attrib.get("grace_period_expired"),
        "is_latest_build": root.attrib.get("is_latest_build"),
        "last_update_time": root.attrib.get("last_update_time"),
        "legacy_scan_engine": root.attrib.get("legacy_scan_engine"),
        "life_cycle_stage": root.attrib.get("life_cycle_stage"),
        "planned_deployment_date": root.attrib.get("planned_deployment_date"),
        "platform": root.attrib.get("platform"),
        "policy_compliance_status": root.attrib.get("policy_compliance_status"),
        "policy_name": root.attrib.get("policy_name"),
        "policy_rules_status": root.attrib.get("policy_rules_status"),
        "policy_version": root.attrib.get("policy_version"),
        "sandbox_id": root.attrib.get("sandbox_id"),
        "scan_overdue": root.attrib.get("scan_overdue"),
        "static_analysis_unit_id": root.attrib.get("static_analysis_unit_id"),
        "submitter": root.attrib.get("submitter"),
        "tags": root.attrib.get("tags"),
        "teams": root.attrib.get("teams"),
        "total_flaws": root.attrib.get("total_flaws"),
        "veracode_level": root.attrib.get("veracode_level"),
        "version": root.attrib.get("version"),
        "xsi_schemaLocation": root.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation')
    }

    static_analysis = root.find('{https://www.veracode.com/schema/reports/export/1.0}static-analysis')
    if static_analysis is not None:
        report_data["static_analysis_rating"] = static_analysis.attrib.get("rating")
        report_data["static_analysis_score"] = static_analysis.attrib.get("score")
        report_data["static_analysis_submitted_date"] = static_analysis.attrib.get("submitted_date")
        report_data["static_analysis_published_date"] = static_analysis.attrib.get("published_date")
        report_data["static_analysis_version"] = static_analysis.attrib.get("version")
        report_data["static_analysis_analysis_size_bytes"] = static_analysis.attrib.get("analysis_size_bytes")
        report_data["static_analysis_engine_version"] = static_analysis.attrib.get("engine_version")

    severity_elements = root.findall('{https://www.veracode.com/schema/reports/export/1.0}severity')
    for i, severity in enumerate(severity_elements):
        prefix = f"severity_{i}"
        report_data[f"{prefix}_level"] = severity.attrib.get("level")

        for j, category in enumerate(severity.findall('{https://www.veracode.com/schema/reports/export/1.0}category')):
            category_prefix = f"{prefix}_category_{j}"
            report_data[f"{category_prefix}_categoryid"] = category.attrib.get("categoryid")
            report_data[f"{category_prefix}_categoryname"] = category.attrib.get("categoryname")
            report_data[f"{category_prefix}_pcirelated"] = category.attrib.get("pcirelated")

            desc = category.find('{https://www.veracode.com/schema/reports/export/1.0}desc')
            if desc is not None:
                paras = desc.findall('{https://www.veracode.com/schema/reports/export/1.0}para')
                report_data[f"{category_prefix}_desc"] = " ".join([para.get('text', '') for para in paras if para.get('text')])

            recommendations = category.find('{https://www.veracode.com/schema/reports/export/1.0}recommendations')
            if recommendations is not None:
                rec_text = []
                paras = recommendations.findall('{https://www.veracode.com/schema/reports/export/1.0}para')
                for para in paras:
                    if para.get('text'):
                        rec_text.append(para.get('text'))

                    bulletitems = para.findall('{https://www.veracode.com/schema/reports/export/1.0}bulletitem')
                    for bullet in bulletitems:
                        if bullet.get('text'):
                            rec_text.append(bullet.get('text'))

                report_data[f"{category_prefix}_recommendation"] = " ".join(rec_text)

    normalized.append(report_data)
    return normalized
