"""
Interactive Live OTP Verification Script
Usage:
    python scripts/e2e_otp_manual.py [email]
"""

import sys
import json
import httpx

BASE_URL = "http://localhost:8000"

def run_manual_otp(email: str):
    print(f"\n=======================================================")
    print(f"Interactive Live OTP Verification for: {email}")
    print(f"Target Backend: {BASE_URL}")
    print(f"=======================================================\n")

    # Step 1: Request OTP
    print(f"[1/3] Calling POST /api/v1/auth/login/request...")
    try:
        resp = httpx.post(f"{BASE_URL}/api/v1/auth/login/request", json={"email": email}, timeout=20.0)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("Please ensure the backend is running on http://localhost:8000")
        return

    print(f"Status Code: {resp.status_code}")
    try:
        data = resp.json()
    except Exception:
        print(f"Raw response: {resp.text}")
        return

    if resp.status_code != 200 or not data.get("success"):
        print(f"\n❌ Login request failed (HTTP {resp.status_code}):")
        print(json.dumps(data, indent=2))
        if resp.status_code == 502:
            print("\n⚠️  Microsoft Graph credentials (MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, MS_SENDER_UPN)")
            print("   are missing or invalid in backend/.env. Please configure them to send real emails.")
        return

    auth_mode = data.get("auth_mode")
    challenge_token = data.get("challenge_token")
    message = data.get("message")
    print(f"Auth Mode: {auth_mode}")
    print(f"Message: {message}")

    if auth_mode == "email_only":
        print("\nℹ️  Backend is running in email_only mode. Direct session token returned:")
        print(f"Access Token: {data.get('access_token', '')[:30]}...")
        print(f"User: {data.get('user')}")
        print("✓ Verified email_only direct login path.")
        return

    # Step 2: Prompt for real OTP
    print(f"\n[2/3] Verification code has been dispatched via Microsoft Graph.")
    print(f"📬 Please check your inbox ({email}) for the 6-digit code.")
    otp = input("\nEnter the 6-digit OTP code received in your email: ").strip()

    if not otp or len(otp) != 6 or not otp.isdigit():
        print(f"❌ Invalid OTP format: '{otp}'. Must be a 6-digit number.")
        return

    # Step 3: Verify OTP
    print(f"\n[3/3] Calling POST /api/v1/auth/login/verify...")
    verify_resp = httpx.post(
        f"{BASE_URL}/api/v1/auth/login/verify",
        json={"challenge_token": challenge_token, "otp": otp},
        timeout=15.0,
    )

    print(f"Status Code: {verify_resp.status_code}")
    try:
        verify_data = verify_resp.json()
    except Exception:
        print(f"Raw response: {verify_resp.text}")
        return

    if verify_resp.status_code != 200 or not verify_data.get("success"):
        print(f"\n❌ OTP verification failed (HTTP {verify_resp.status_code}):")
        print(json.dumps(verify_data, indent=2))
        return

    print(f"\n🎉 LIVE LOGIN VERIFIED SUCCESSFULLY!")
    print(f"Session Token: {verify_data.get('access_token', '')[:35]}...")
    print(f"Authenticated Role: {verify_data.get('role')}")
    print(f"Authenticated User: {verify_data.get('name')} ({verify_data.get('email')})")
    print(f"Zoho User ID: {verify_data.get('zoho_user_id')}")

if __name__ == "__main__":
    target_email = sys.argv[1] if len(sys.argv) > 1 else "piruthvin.official.2@gmail.com"
    run_manual_otp(target_email)
