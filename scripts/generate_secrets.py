#!/usr/bin/env python3
"""
scripts/generate_secrets.py

Generates cryptographically secure secrets (JWT_SECRET_KEY, AGENT_API_KEY)
and updates backend/.env if missing or empty.
"""

import os
import secrets
from pathlib import Path


def generate_secret_hex(length: int = 32) -> str:
    return secrets.token_hex(length)


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    backend_env_example = root_dir / "backend" / ".env.example"
    backend_env = root_dir / "backend" / ".env"
    frontend_env_example = root_dir / "frontend" / ".env.example"
    frontend_env = root_dir / "frontend" / ".env"

    backend_dir = root_dir / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir = root_dir / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)

    jwt_secret = generate_secret_hex(32)
    agent_api_key = generate_secret_hex(32)

    # 1. Handle backend/.env
    if not backend_env.exists():
        if backend_env_example.exists():
            content = backend_env_example.read_text(encoding="utf-8")
        else:
            content = ""

        # Replace or add secrets
        if "JWT_SECRET_KEY=" in content:
            lines = []
            for line in content.splitlines():
                if line.startswith("JWT_SECRET_KEY=") and not line.split("=", 1)[1].strip():
                    lines.append(f"JWT_SECRET_KEY={jwt_secret}")
                elif line.startswith("AGENT_API_KEY=") and not line.split("=", 1)[1].strip():
                    lines.append(f"AGENT_API_KEY={agent_api_key}")
                else:
                    lines.append(line)
            content = "\n".join(lines) + "\n"
        else:
            content += f"\nJWT_SECRET_KEY={jwt_secret}\nAGENT_API_KEY={agent_api_key}\n"

        backend_env.write_text(content, encoding="utf-8")
        print(f"[+] Created {backend_env} with newly generated secrets.")
    else:
        # File exists - check if secrets are missing or empty
        content = backend_env.read_text(encoding="utf-8")
        updated = False
        new_lines = []
        for line in content.splitlines():
            if line.startswith("JWT_SECRET_KEY="):
                val = line.split("=", 1)[1].strip()
                if not val:
                    new_lines.append(f"JWT_SECRET_KEY={jwt_secret}")
                    updated = True
                else:
                    new_lines.append(line)
            elif line.startswith("AGENT_API_KEY="):
                val = line.split("=", 1)[1].strip()
                if not val:
                    new_lines.append(f"AGENT_API_KEY={agent_api_key}")
                    updated = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        if updated:
            backend_env.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            print(f"[+] Updated existing {backend_env} with generated secrets.")
        else:
            print(f"[i] Secrets already set in {backend_env}.")

    # 2. Handle frontend/.env
    if not frontend_env.exists() and frontend_env_example.exists():
        frontend_env.write_text(frontend_env_example.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[+] Created {frontend_env} from example.")


if __name__ == "__main__":
    main()
