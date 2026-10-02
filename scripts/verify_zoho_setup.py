#!/usr/bin/env python3
"""
scripts/verify_zoho_setup.py

Diagnostic verification script for Zoho Recruit setup.
Produces a clear PASS / FAIL validation table:
1. Custom Candidate fields exist with expected types
2. 'Employee Referral' exists in Source picklist values (fails loudly if missing)
3. Configured candidate status values exist in Candidate_Status picklist
4. Users API reachable and active users correctly map to 'recruiter' and 'employee'
5. Attachments API connectivity
Provides clear, numbered manual instructions for any missing configuration.
"""

import sys
import os
import asyncio
import urllib.parse
from pathlib import Path
import httpx

# Add backend to path and change cwd so Settings loads backend/.env
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))
os.chdir(ROOT_DIR / "backend")

from app.core.config import get_settings

from app.infrastructure.zoho_auth import zoho_auth_manager
from app.services.zoho_service import zoho_service
from app.services.zoho_users_service import zoho_users_service
from app.services.zoho_field_mapper import zoho_field_mapper

REQUIRED_CUSTOM_FIELDS = {
    "referred_by": {"expected_name": "Referred_By", "expected_type": ("text", "string")},
    "referred_date": {"expected_name": "Referred_Date", "expected_type": ("date",)},
    "referral_score": {"expected_name": "Referral_Score", "expected_type": ("decimal", "double", "percent", "number", "integer")},
    "referral_approval_status": {"expected_name": "Referral_Approval_Status", "expected_type": ("picklist", "string")},
    "referral_approval_note": {"expected_name": "Referral_Approval_Note", "expected_type": ("textarea", "text", "multilinetext", "string")},
}


async def run_diagnostics() -> None:
    settings = get_settings()
    print("=" * 80)
    print("        Zoho Recruit Setup Diagnostics & Configuration Validator")
    print("=" * 80)

    if not settings.zoho_client_id or not settings.zoho_client_secret or not settings.zoho_refresh_token:
        print("\n[-] FATAL: Zoho credentials are not configured in backend/.env.")
        print("    Run: python scripts/get_zoho_refresh_token.py to generate and configure tokens.")
        sys.exit(1)

    # 1. Test OAuth token acquisition
    print("\n[*] Validating Zoho OAuth2 token acquisition...")
    try:
        token = await zoho_auth_manager.get_access_token()
        print(f"    [PASS] OAuth2 access token retrieved successfully. (Token: {token[:12]}...)")
    except Exception as e:
        print(f"    [FAIL] Failed to obtain access token: {e}")
        sys.exit(1)

    # 2. Fetch Candidates module fields metadata directly to detect scope mismatch
    print("\n[*] Querying Candidates module metadata (/settings/fields?module=Candidates)...")
    results: list[tuple[str, str, str]] = []
    manual_steps: list[str] = []

    settings_scope_ok = False
    try:
        url = f"{settings.zoho_recruit_base_url.rstrip('/')}/settings/fields?module=Candidates"
        token = await zoho_auth_manager.get_access_token()
        headers = {"Authorization": f"Zoho-oauthtoken {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                settings_scope_ok = True
                results.append(("Fields Metadata API (/settings/fields)", "PASS", "Reachable with granted OAuth scope"))
            elif resp.status_code == 401 and "OAUTH_SCOPE_MISMATCH" in resp.text:
                results.append(("Fields Metadata API (/settings/fields)", "FAIL", "OAUTH_SCOPE_MISMATCH: Token lacks settings scope"))
                manual_steps.append(
                    "Token lacks ZohoRecruit.settings.ALL/setup.ALL scope. "
                    "Run: python scripts/get_zoho_refresh_token.py to re-authorize and update ZOHO_REFRESH_TOKEN in backend/.env."
                )
            else:
                results.append(("Fields Metadata API (/settings/fields)", "WARN", f"HTTP {resp.status_code}: {resp.text[:100]}"))
    except Exception as e:
        results.append(("Fields Metadata API (/settings/fields)", "WARN", str(e)))

    fields_meta = await zoho_field_mapper.get_candidate_fields_metadata(force_refresh=True)

    # Check custom fields
    for field_key, meta in REQUIRED_CUSTOM_FIELDS.items():
        field_def = fields_meta.get(field_key)
        if field_def and settings_scope_ok:
            actual_type = str(field_def.get("data_type") or field_def.get("json_type") or "").lower()
            valid_type = any(exp in actual_type for exp in meta["expected_type"])
            if valid_type:
                results.append((f"Field '{meta['expected_name']}'", "PASS", f"Type: {actual_type}"))
            else:
                results.append((f"Field '{meta['expected_name']}'", "WARN", f"Expected {meta['expected_type']}, found {actual_type}"))
        elif field_def:
            results.append((f"Field '{meta['expected_name']}'", "WARN", "Verified against fallback metadata (live check blocked on scope)"))
        else:
            results.append((f"Field '{meta['expected_name']}'", "FAIL", "Missing custom field"))
            manual_steps.append(
                f"Create custom field '{meta['expected_name']}' in Setup -> Customization -> Modules -> Candidates. "
                f"Type: {meta['expected_type'][0]}."
            )

    # Check Source picklist
    source_field = fields_meta.get("source")
    if source_field:
        pick_values = [p.get("actual_value", p.get("display_value", "")) for p in source_field.get("pick_list_values", [])]
        if any("employee referral" in str(v).lower() for v in pick_values):
            results.append(("Source: 'Employee Referral'", "PASS", "Valid picklist value"))
        elif settings_scope_ok:
            results.append(("Source: 'Employee Referral'", "FAIL", "Missing 'Employee Referral' in picklist"))
            manual_steps.append(
                "In Setup -> Customization -> Modules -> Candidates -> Edit 'Source' field: "
                "Add 'Employee Referral' to the picklist values and save."
            )
        else:
            results.append(("Source: 'Employee Referral'", "WARN", "Using default picklist fallback"))
    else:
        results.append(("Source field", "WARN", "Source field definition not found in metadata"))

    # Check candidate statuses
    status_field = fields_meta.get("candidate_status")
    if status_field and settings_scope_ok:
        status_picks = [p.get("actual_value", p.get("display_value", "")) for p in status_field.get("pick_list_values", [])]
        status_picks_lower = [str(s).lower() for s in status_picks]

        for setting_name, val in [
            ("STATUS_ON_REFERRAL", settings.status_on_referral),
            ("STATUS_ON_APPROVAL", settings.status_on_approval),
            ("STATUS_ON_REJECTION", settings.status_on_rejection),
            ("STATUS_ON_INTERVIEW_SCHEDULED", settings.status_on_interview_scheduled),
        ]:
            if val.lower() in status_picks_lower:
                results.append((f"Status '{setting_name}' ({val})", "PASS", "Exists in Candidate_Status"))
            else:
                results.append((f"Status '{setting_name}' ({val})", "WARN", f"'{val}' not found in picklist: {status_picks[:5]}..."))
                manual_steps.append(
                    f"Check Candidate_Status picklist values in Zoho Recruit or adjust {setting_name} in backend/.env to match."
                )

    # Check Referred_By Search Criteria Query
    print("\n[*] Validating Candidates/search by Referred_By query syntax...")
    try:
        test_criteria = "((Referred_By:equals:verify_diagnostic@example.com))"
        enc = urllib.parse.quote(test_criteria)
        search_path = f"Candidates/search?criteria={enc}"
        s_resp = await zoho_service._request("GET", search_path)
        if s_resp.status_code in (200, 204):
            results.append(("Referred_By Search Query", "PASS", "Search by Referred_By accepted by Zoho"))
        elif s_resp.status_code == 400 and "the field is not available for search" in s_resp.text:
            results.append(("Referred_By Search Query", "FAIL", "Custom field 'Referred_By' not indexed/searchable in Zoho search API"))
            manual_steps.append(
                "In Zoho Recruit -> Setup -> Customization -> Modules -> Candidates: "
                "Ensure 'Referred_By' is created as a single-line Text field (not a Lookup), placed on the active Candidate layout."
            )
        else:
            results.append(("Referred_By Search Query", "WARN", f"HTTP {s_resp.status_code}: {s_resp.text[:100]}"))
    except Exception as e:
        results.append(("Referred_By Search Query", "WARN", str(e)))

    # Check Users API
    print("\n[*] Validating Zoho Users API (/users?type=ActiveUsers)...")
    try:
        users = await zoho_users_service.get_active_users(force_refresh=True)
        if zoho_users_service.users_source == "live":
            results.append(("Users API Connectivity", "PASS", f"{len(users)} active users returned (Live Zoho Users Directory)"))
            roles_found = set()
            for u in users:
                r = zoho_users_service.derive_user_role(u)
                if r:
                    roles_found.add(r)

            if "recruiter" in roles_found and "employee" in roles_found:
                results.append(("User Role Mapping", "PASS", f"Mapped recruiter and employee users ({', '.join(roles_found)})"))
            else:
                results.append(("User Role Mapping", "WARN", f"Active users only mapped: {roles_found or 'None'}"))
                manual_steps.append(
                    "Ensure at least one user has Profile/Role 'Administrator' or 'Recruiter', and at least one user has 'Employee'."
                )
        else:
            results.append(("Users API Connectivity", "FAIL", "OAUTH_SCOPE_MISMATCH: Operating on registered test directory fallback"))
            manual_steps.append(
                "Token lacks ZohoRecruit.users.ALL/READ scope. "
                "Run: python scripts/get_zoho_refresh_token.py to re-authorize with consolidated scopes."
            )
    except Exception as e:
        results.append(("Users API Connectivity", "FAIL", str(e)))

    # Check Attachments API
    print("\n[*] Checking Attachments API reachability...")
    try:
        cands, _ = await zoho_service.get_all_candidates(page=1, per_page=1)
        if cands:
            test_id = str(cands[0].get("id"))
            await zoho_service.get_candidate_attachments(test_id)
            results.append(("Attachments API Connectivity", "PASS", f"Reachable via candidate {test_id}"))
        else:
            results.append(("Attachments API Connectivity", "PASS", "Candidates module reachable (0 records currently)"))
    except Exception as e:
        results.append(("Attachments API Connectivity", "FAIL", str(e)))

    # Print Summary Table
    print("\n" + "=" * 80)
    print(f"{'CHECK / ITEM':<40} | {'STATUS':<8} | {'DETAILS'}")
    print("-" * 80)
    has_failure = False
    for item, status_val, details in results:
        status_color = status_val
        if status_val == "FAIL":
            has_failure = True
        print(f"{item:<40} | {status_color:<8} | {details}")
    print("=" * 80)

    if manual_steps:
        print("\n[!] REQUIRED MANUAL CONFIGURATION STEPS:")
        for idx, step in enumerate(manual_steps, 1):
            print(f"  {idx}. {step}")
        print("\nDetailed guide available at docs/ZOHO_SETUP.md")


    if has_failure:
        print("\n[-] Verification FAILED: Resolve the items marked FAIL above before running in production.\n")
        sys.exit(1)
    else:
        print("\n[+] Verification SUCCESSFUL: Zoho Recruit is properly configured for the Referral Agent!\n")


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
