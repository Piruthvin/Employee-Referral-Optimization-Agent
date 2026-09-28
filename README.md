# Employee-Referral-Optimization-Agent

An enterprise-grade, AI-driven Employee Referral & Recruitment Operations platform built with **FastAPI**, **React (TypeScript + Vite + Tailwind CSS)**, **Zoho Recruit REST API (India DC)**, **Microsoft Graph**, and **iGentic Multi-Agent AI**.

---

## 1. System Architecture

```text
+-----------------------------------------------------------------------------------+
|                           Azure Static Web Apps (Frontend)                        |
|   React 19 + TypeScript + Vite + Tailwind CSS + Zustand (In-Memory Auth Only)     |
+-----------------------------------------+-----------------------------------------+
                                          |
                        HTTPS + Bearer JWT| (Dual Auth: JWT or X-Agent-Key)
                                          v
+-----------------------------------------------------------------------------------+
|                        Azure Container Apps (FastAPI Backend)                     |
|                                                                                   |
|  +------------------+  +-------------------+  +--------------------------------+  |
|  |   Auth Service   |  |  Referral Intake  |  |      Job Match Service         |  |
|  | (Stateless OTP)  |  |  (3-Field Form)   |  |   (Deterministic Python)       |  |
|  +------------------+  +-------------------+  +--------------------------------+  |
|  | Approval Service |  | Interview Service |  |       Analytics Service        |  |
|  |  (Recruiter Gate)|  | (Teams Mtg + .ics)|  |    (Funnel KPIs & SLA Trends)  |  |
|  +------------------+  +-------------------+  +--------------------------------+  |
+---------+--------------------+------------------------------+---------------------+
          |                    |                              |
          v                    v                              v
+-------------------+ +------------------+     +-------------------------------+
|    Zoho Recruit   | | Microsoft Graph  |     |         iGentic Platform      |
|    India DC v2    | |     (App-Only)   |     |                               |
| - Candidates DB   | | - Teams Meetings |     |  [Chat Streaming (SSE)]       |
| - Attachments     | | - Email (sendMail| <-> |  Group Chat Manager           |
| - Notes & Fields  | |   OTP & Invites) |     |  |-- Referral_Agent (8 tools) |
| - Active Users    | | - RFC 5545 .ics  |     |  |-- Analytics_Agent (5 tools)|
+-------------------+ +------------------+     |                               |
                                               |  [Resume Parser Agent]        |
                                               |  Single-agent fallback parser |
                                               +-------------------------------+
```

---

## 2. Key Architectural Decisions
- **Zero Database / Zero Blob Storage**: Zoho Recruit is the single source of truth. Candidates are stored in the Candidates module, resumes in candidate attachments, and full parsed JSON profiles in candidate notes.
- **Zoho Active Users Authentication**: Roles (`employee`, `recruiter`, `hiring_manager`) are dynamically derived from Zoho Recruit Users (`Setup -> Users`). No arbitrary role selector. No legacy Contacts module or tenure restrictions.
- **Stateless OTP Authentication**: Login uses email challenge tokens signed via HMAC-SHA256 with 5-attempt windows. One-time codes are sent via Microsoft Graph and never stored in memory or databases.
- **No Functions Proxy**: The FastAPI backend communicates directly with the iGentic executor and relays real-time Server-Sent Events (SSE) to the frontend.
- **Strict Recruiter Gate**: Interview scheduling is blocked (HTTP 409) until candidate referral approval state is `Approved`.
- **Compensating Rollbacks**: If candidate creation succeeds in Zoho but attachment upload fails, the candidate is automatically rolled back to prevent orphaned records.

---

## 3. Repository Structure

```text
Referral Agent/
├── agent-prompts/             # iGentic system prompts, tool configs, and test scenarios
│   ├── Group_Chat_Manager.md
│   ├── Referral_Agent.md
│   ├── Analytics_Agent.md
│   ├── Resume_Parser_Agent.md
│   ├── TOOLS_CONFIG.md
│   └── TEST_PROMPTS.md
├── backend/                   # FastAPI backend application
│   ├── app/
│   │   ├── api/v1/            # 30 API endpoints & tool aliases
│   │   ├── core/              # Config, Security (JWT/OTP), Auth Dependencies
│   │   ├── domain/            # Pydantic models & resume schema
│   │   ├── infrastructure/    # Zoho OAuth refresh manager & retry logic
│   │   ├── services/          # Business logic (Zoho, Resume, Matching, Graph, iGentic)
│   │   └── main.py            # FastAPI entry point & middlewares
│   ├── tests/                 # Automated pytest suite (31 unit & integration tests)
│   ├── Dockerfile             # Multi-stage non-root container image
│   └── requirements.txt
├── frontend/                  # React 19 + TypeScript + Vite + Tailwind frontend
│   ├── src/
│   │   ├── api/               # Axios client with in-memory auth interceptor
│   │   ├── components/        # Navbar, ProtectedRoute, ReferralModal (3 fields)
│   │   ├── pages/             # LoginPage, EmployeeDashboard, RecruiterDashboard, Detail, Chat
│   │   ├── store/             # Zustand in-memory auth store (NO localStorage)
│   │   └── types/             # TypeScript definitions
│   ├── staticwebapp.config.json # Azure Static Web Apps SPA routing & security headers
│   └── tailwind.config.js
├── deploy/                    # Azure deployment automation
│   ├── deploy-backend.ps1 / .sh
│   ├── update-backend.ps1 / .sh
│   ├── deploy-frontend.ps1 / .sh
│   ├── smoke-test.ps1
│   └── post-deploy-checklist.md
├── docs/                      # Documentation
│   ├── REFERENCE_FINDINGS.md
│   ├── BUILD_REPORT.md
│   ├── TEST_CHECKLIST.md
│   ├── ZOHO_SETUP.md
│   └── TEAMS_SETUP.md
├── scripts/                   # Setup and verification helpers
│   ├── generate_secrets.py
│   ├── get_zoho_refresh_token.py
│   ├── verify_zoho_setup.py
│   ├── seed_test_data.py
│   └── validate_deploy_scripts.py
├── docker-compose.yml
└── README.md
```

---

## 4. Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: v18 or higher (v24 LTS tested)
- **Azure CLI (`az`)**: For container and static web app provisioning
- **Zoho Recruit (India DC)** account with Administrator access
- **Microsoft 365 Tenant** with Azure App Registration for Microsoft Graph

---

## 5. One-Time Setup Order

### Step 1: Generate Cryptographic Secrets
Generate a 256-bit `JWT_SECRET_KEY` and high-entropy `AGENT_API_KEY`:
```bash
python scripts/generate_secrets.py
```
This automatically updates `backend/.env`.

### Step 2: Configure Environment Credentials
Open `backend/.env` and supply your API credentials:
```ini
ZOHO_CLIENT_ID=<from-api-console.zoho.in>
ZOHO_CLIENT_SECRET=<from-api-console.zoho.in>
MS_TENANT_ID=<your-azure-ad-tenant-id>
MS_CLIENT_ID=<your-app-registration-client-id>
MS_CLIENT_SECRET=<your-app-registration-secret>
MS_ORGANIZER_UPN=<organizer-mailbox@yourdomain.com>
MS_SENDER_UPN=<sender-mailbox@yourdomain.com>
IGENTIC_EXECUTOR_URL=https://api.igentic.ai/v1/agent-executions
IGENTIC_APP_ID=<your-igentic-chat-app-id>
IGENTIC_API_KEY=<your-igentic-api-key>
```

### Step 3: Obtain Zoho Recruit Refresh Token
Run the interactive India DC OAuth exchange script:
```bash
python scripts/get_zoho_refresh_token.py
```
Open the generated consent URL in your browser, approve permissions, copy the one-time code, and paste it into the prompt. The script stores `ZOHO_REFRESH_TOKEN` directly into `backend/.env`.

### Step 4: Verify Zoho Recruit Configuration
Validate that all custom fields (`Referred_By`, `Referred_Date`, `Referral_Score`, `Referral_Approval_Status`), picklist values (`Employee Referral`), and users match system requirements:
```bash
python scripts/verify_zoho_setup.py
```
*(If any fields are missing, refer to `docs/ZOHO_SETUP.md` for exact manual setup steps).*

### Step 5: Configure Microsoft Teams Meeting Policy
Configure Microsoft Graph application permissions and PowerShell Application Access Policy so the app can create online meetings on behalf of `MS_ORGANIZER_UPN`. Follow the step-by-step instructions in `docs/TEAMS_SETUP.md`.

### Step 6: Create iGentic Agents & Tools
Configure the Multi-Agent Chat app and standalone Resume Parser app using the prompts and tool schemas in:
- `agent-prompts/Group_Chat_Manager.md`
- `agent-prompts/Referral_Agent.md`
- `agent-prompts/Analytics_Agent.md`
- `agent-prompts/Resume_Parser_Agent.md`
- `agent-prompts/TOOLS_CONFIG.md`

---

## 6. Running Locally

### Option A: Local Processes (Recommended for Development)

**Terminal 1 — Backend:**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Liveness Probe: [http://localhost:8000/health](http://localhost:8000/health)

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```
- Web Application: [http://localhost:5173](http://localhost:5173)

### Option B: Docker Compose
```bash
docker compose up --build
```

---

## 7. Connecting iGentic to Local Backend (Dev Tunnel)
Since iGentic agents execute in the cloud, they cannot reach `http://localhost:8000` directly. During development, expose port 8000 through an HTTPS tunnel:

**Using Microsoft Dev Tunnels:**
```bash
devtunnel host -p 8000 --allow-anonymous
```
Copy the issued HTTPS tunnel URL (e.g. `https://xxx.devtunnels.ms`) and configure it as the tool Base URL in the iGentic console (see `agent-prompts/TOOLS_CONFIG.md`).

---

## 8. Automated Testing

### Backend Unit & Integration Tests (31 Cases)
Run pytest with full test isolation (Zoho and Graph calls mocked):
```bash
python -m pytest backend/tests -v
```

### Frontend Build & Typechecking
```bash
cd frontend
npm run build
npx tsc --noEmit
npm run lint
```

### Deployment Scripts Syntax Validation
```bash
python scripts/validate_deploy_scripts.py
```

---

## 9. Production Deployment to Azure

### Deploy Backend to Azure Container Apps
```powershell
./deploy/deploy-backend.ps1 -ResourceGroup "ReferralAgentRG" -Location "southindia"
```

### Deploy Frontend to Azure Static Web Apps
```powershell
./deploy/deploy-frontend.ps1 -ResourceGroup "ReferralAgentRG"
```

### Post-Deployment Configuration
Follow `deploy/post-deploy-checklist.md` to:
1. Update `FRONTEND_BASE_URL` and `CORS_ORIGINS` in Azure Container Apps.
2. Update iGentic tool URLs from your dev tunnel to the live Azure Container App FQDN.
3. Run automated smoke tests:
   ```powershell
   ./deploy/smoke-test.ps1 -BaseUrl "https://<your-container-app-fqdn>"
   ```

---

## 10. Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **CORS Error in Browser** | `CORS_ORIGINS` does not match the frontend origin | Verify `CORS_ORIGINS` in `backend/.env` contains your exact frontend origin (e.g. `["http://localhost:5173"]` or your Static Web App URL). |
| **Zoho 401 Unauthorized** | Expired refresh token or bad client credentials | Re-run `python scripts/get_zoho_refresh_token.py` to refresh your token. Check that `ZOHO_CLIENT_ID` matches your Zoho India account. |
| **Teams 403 Forbidden** | Missing Application Access Policy | Run `New-CsApplicationAccessPolicy` and `Grant-CsApplicationAccessPolicy` in PowerShell for `MS_ORGANIZER_UPN` per `docs/TEAMS_SETUP.md`. |
| **SSE Stream Buffering** | Proxy or reverse proxy buffering chunks | Ensure headers `Cache-Control: no-cache` and `X-Accel-Buffering: no` are present (built into `api/v1/chat.py`). |
| **OTP Email Not Arriving** | Microsoft Graph Mail.Send permission pending admin consent | Check Azure Portal -> App Registrations -> API Permissions. Ensure `Mail.Send` has **Grant admin consent for <Tenant>**. In dev mode, OTP codes are logged to console. |
| **Attachment Rollback Triggered** | Resume upload failed in Zoho Recruit | Verify `attachments API` permissions (`ZohoRecruit.modules.attachments.CREATE`). The backend automatically deletes half-created candidate records to maintain clean state. |
