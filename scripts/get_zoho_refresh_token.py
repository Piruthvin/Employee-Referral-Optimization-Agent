#!/usr/bin/env python3
"""
scripts/get_zoho_refresh_token.py

Interactive helper to generate a Zoho Recruit OAuth2 Refresh Token for the India Data Center (DC).
Reads ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET from backend/.env,
constructs the consent URL, prompts for the authorization code, exchanges it,
and updates ZOHO_REFRESH_TOKEN in backend/.env.
"""

import sys
import urllib.parse
from pathlib import Path
import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT_DIR / "backend" / ".env"

# Required Zoho Recruit v2 OAuth2 scopes
# Consolidated list granting full access for records, users directory, and field metadata/settings
SCOPES = [
    "ZohoRecruit.users.ALL",
    "ZohoRecruit.users.READ",
    "ZohoRecruit.candidates.ALL",
    "ZohoRecruit.jobopenings.ALL",
    "ZohoRecruit.modules.ALL",
    "ZohoRecruit.settings.ALL",
    "ZohoRecruit.settings.fields.READ",
    "ZohoRecruit.setup.ALL",
    "ZohoRecruit.org.ALL",
]


def load_env_vars() -> dict[str, str]:
    if not ENV_FILE.exists():
        print(f"[-] Error: {ENV_FILE} does not exist. Run scripts/generate_secrets.py first.")
        sys.exit(1)

    vars_dict: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            vars_dict[k.strip()] = v.strip()
    return vars_dict


def update_env_file(key: str, val: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={val}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={val}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"[+] Successfully wrote {key} to {ENV_FILE}")


def main() -> None:
    print("=" * 70)
    print("   Zoho Recruit India DC OAuth2 Token Generation Helper")
    print("=" * 70)

    env_vars = load_env_vars()
    client_id = env_vars.get("ZOHO_CLIENT_ID")
    client_secret = env_vars.get("ZOHO_CLIENT_SECRET")
    accounts_base = env_vars.get("ZOHO_ACCOUNTS_BASE_URL", "https://accounts.zoho.in").rstrip("/")

    if not client_id or not client_secret:
        print("[-] ZOHO_CLIENT_ID or ZOHO_CLIENT_SECRET is missing in backend/.env.")
        print("    Please enter your credentials from https://api-console.zoho.in below:")
        client_id = input("Zoho Client ID: ").strip()
        client_secret = input("Zoho Client Secret: ").strip()
        if client_id and client_secret:
            update_env_file("ZOHO_CLIENT_ID", client_id)
            update_env_file("ZOHO_CLIENT_SECRET", client_secret)
        else:
            print("[-] Both Client ID and Client Secret are required. Aborting.")
            sys.exit(1)

    # Prompt or use registered redirect URI
    redirect_uri = input("Registered Redirect URI [default: http://localhost:8000/zoho/callback]: ").strip()
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/zoho/callback"

    scope_str = ",".join(SCOPES)
    auth_params = {
        "scope": scope_str,
        "client_id": client_id,
        "response_type": "code",
        "access_type": "offline",
        "redirect_uri": redirect_uri,
        "prompt": "consent",
    }
    auth_url = f"{accounts_base}/oauth/v2/auth?{urllib.parse.urlencode(auth_params)}"

    print("\n" + "-" * 70)
    print("STEP 1: Open the following URL in your browser to grant authorization:")
    print("-" * 70)
    print(auth_url)
    print("-" * 70)
    print("Log in to your Zoho Recruit account and click 'Accept' / 'Allow'.")
    print("You will be redirected to your redirect URI with a '?code=...' parameter.")
    print("⚠️  IMPORTANT: The authorization code expires in minutes! Copy and paste it immediately.\n")

    code = input("Paste the 'code' parameter from the redirected URL: ").strip()
    if not code:
        print("[-] No code entered. Aborting.")
        sys.exit(1)

    # Clean code if user pasted entire URL
    if "code=" in code:
        parsed = urllib.parse.urlparse(code)
        qs = urllib.parse.parse_qs(parsed.query)
        if "code" in qs:
            code = qs["code"][0]

    token_url = f"{accounts_base}/oauth/v2/token"
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }

    print(f"\n[*] Exchanging authorization code at {token_url}...")
    try:
        resp = httpx.post(token_url, data=token_payload, timeout=20.0)
        resp_data = resp.json()

        if "error" in resp_data:
            print(f"[-] Zoho error: {resp_data.get('error')}")
            print(f"    Details: {resp_data}")
            sys.exit(1)

        refresh_token = resp_data.get("refresh_token")
        if not refresh_token:
            print("[-] Warning: No 'refresh_token' was returned in response.")
            print(f"    Response payload: {resp_data}")
            print("    Note: Zoho only returns a refresh token if 'access_type=offline' and consent was given.")
            sys.exit(1)

        update_env_file("ZOHO_REFRESH_TOKEN", refresh_token)
        print("\n[+] SUCCESS! Zoho OAuth2 refresh token retrieved and saved to backend/.env.")
        print(f"    Access Token preview: {resp_data.get('access_token', '')[:10]}...")
        print(f"    Expires in: {resp_data.get('expires_in')} seconds.")

    except Exception as e:
        print(f"[-] Network error exchanging token: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
