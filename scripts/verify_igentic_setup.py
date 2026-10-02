#!/usr/bin/env python3
"""
scripts/verify_igentic_setup.py

Diagnostic verification script for iGentic Autonomous Agent setup.
Tests reachability and authentication against the unified iGentic executor URL.
Reports:
1. Environment configuration presence (URL, App ID, API Key, Bearer Token, Username)
2. JWT Bearer token validity and expiration timestamp
3. Live executor ping test with real HTTP status
4. Explicit dashboard instructions if 401 Unauthorized occurs.
"""

import sys
import os
import time
import asyncio
from pathlib import Path
import jwt
import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))
os.chdir(ROOT_DIR / "backend")

from app.core.config import get_settings
from app.services.igentic_client import igentic_client


async def run_diagnostics() -> None:
    settings = get_settings()
    print("=" * 80)
    print("        iGentic Autonomous Agent Setup & Authentication Validator")
    print("=" * 80)

    results: list[tuple[str, str, str]] = []
    manual_steps: list[str] = []

    # 1. Check env presence
    print("\n[*] Validating iGentic configuration variables in backend/.env...")
    for var_name, val in [
        ("IGENTIC_EXECUTOR_URL", settings.igentic_executor_url),
        ("IGENTIC_APP_ID", settings.igentic_app_id),
        ("IGENTIC_API_KEY", settings.igentic_api_key),
        ("IGENTIC_BEARER_TOKEN", settings.igentic_bearer_token),
        ("IGENTIC_USERNAME", settings.igentic_username),
    ]:
        if val:
            results.append((f"Config '{var_name}'", "PASS", f"Configured (length: {len(val)})"))
        else:
            results.append((f"Config '{var_name}'", "FAIL", "Missing in backend/.env"))
            manual_steps.append(f"Set {var_name} in backend/.env with your iGentic credentials.")

    # 2. Check JWT expiration of bearer token
    token = settings.igentic_bearer_token or ""
    if token:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            exp = unverified.get("exp")
            if exp:
                now = time.time()
                time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(exp))
                if exp < now:
                    diff_mins = int((now - exp) / 60)
                    results.append(("Bearer Token Expiration", "FAIL", f"EXPIRED at {time_str} ({diff_mins} minutes ago)"))
                    manual_steps.append(
                        "Your IGENTIC_BEARER_TOKEN has expired! "
                        "Obtain a fresh bearer token from your iGentic / Entra ID dashboard and update IGENTIC_BEARER_TOKEN in backend/.env."
                    )
                else:
                    diff_hours = round((exp - now) / 3600, 1)
                    results.append(("Bearer Token Expiration", "PASS", f"Valid until {time_str} (~{diff_hours} hours remaining)"))
            else:
                results.append(("Bearer Token Expiration", "WARN", "Decoded JWT has no 'exp' claim"))
        except Exception as e:
            results.append(("Bearer Token Expiration", "WARN", f"Non-JWT or unparseable token: {e}"))

    # 3. Live Ping against Executor
    print("\n[*] Sending test ping to iGentic executor...")
    if settings.igentic_executor_url and settings.igentic_bearer_token:
        try:
            body = {
                "userInput": "Ping diagnostic test",
                "UserInputType": "",
                "sessionId": "diagnostic-session-001",
                "executionId": "",
                "connectionID": "",
                "isStreaming": False,
                "Username": settings.igentic_username,
            }
            headers = igentic_client._get_headers(session_id="diagnostic-session-001")
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(settings.igentic_executor_url, json=body, headers=headers)
                if resp.status_code == 200:
                    results.append(("Live Executor Ping", "PASS", f"HTTP 200 OK - Executor responsive"))
                elif resp.status_code == 401:
                    results.append(("Live Executor Ping", "FAIL", f"HTTP 401 Unauthorized: Executor rejected credentials"))
                    manual_steps.append(
                        "iGentic executor returned HTTP 401 Unauthorized. "
                        "Double-check in the iGentic dashboard: "
                        "1) IGENTIC_BEARER_TOKEN (likely expired), "
                        "2) IGENTIC_API_KEY, "
                        "3) IGENTIC_APP_ID matches the executor URL path, "
                        "4) IGENTIC_USERNAME matches your authorized account."
                    )
                else:
                    results.append(("Live Executor Ping", "WARN", f"HTTP {resp.status_code}: {resp.text[:120]}"))
        except Exception as e:
            results.append(("Live Executor Ping", "FAIL", f"Network connection failed: {e}"))
    else:
        results.append(("Live Executor Ping", "FAIL", "Skipped due to missing URL or token"))

    # Print Summary Table
    print("\n" + "=" * 80)
    print(f"{'CHECK / ITEM':<40} | {'STATUS':<8} | {'DETAILS'}")
    print("-" * 80)
    has_failure = False
    for item, status_val, details in results:
        if status_val == "FAIL":
            has_failure = True
        print(f"{item:<40} | {status_val:<8} | {details}")
    print("=" * 80)

    if manual_steps:
        print("\n[!] REQUIRED ACTION STEPS:")
        for idx, step in enumerate(manual_steps, 1):
            print(f"  {idx}. {step}")
        print()

    if has_failure:
        print("[-] iGentic verification FAILED. Follow the action steps above.\n")
        sys.exit(1)
    else:
        print("[+] iGentic verification PASSED! Agent integration is operational.\n")


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
