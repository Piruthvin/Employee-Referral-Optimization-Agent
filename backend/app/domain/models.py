"""
Domain data transfer objects (DTOs) and Pydantic schemas for all API endpoints.
"""

from typing import Any
from pydantic import BaseModel, Field, EmailStr


# ── Auth Models ───────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Corporate or personal email of active Zoho user")


class LoginResponse(BaseModel):
    success: bool
    message: str
    challenge_token: str | None = None
    auth_mode: str = "otp"
    access_token: str | None = None
    role: str | None = None
    email: str | None = None
    name: str | None = None
    zoho_user_id: str | None = None
    user: dict[str, Any] | None = None


class VerifyRequest(BaseModel):
    challenge_token: str = Field(..., description="Short-lived HMAC challenge token returned from login request")
    otp: str = Field(..., min_length=4, max_length=8, description="6-digit verification code sent via email")


class VerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    email: str
    name: str
    zoho_user_id: str
    user: dict[str, Any] | None = None


class UserMeResponse(BaseModel):
    email: str
    role: str
    name: str
    zoho_user_id: str


class ValidateResponse(BaseModel):
    valid: bool
    email: str
    role: str


# ── Referral Models ───────────────────────────────────────────────────────────

class ReferralSubmitResponse(BaseModel):
    success: bool
    candidate_id: str
    best_match: dict[str, Any] | None = None
    status: str = "Pending recruiter approval"
    warnings: list[str] = Field(default_factory=list)


class ReferralStatusRequest(BaseModel):
    candidate_id: str | None = Field(default=None, description="Zoho Candidate ID")
    candidate_email: str | None = Field(default=None, description="Candidate email address")
    requester_email: str | None = Field(default=None, description="Requester email (when calling via X-Agent-Key)")


class ReferralStatusResponse(BaseModel):
    candidate_id: str
    name: str
    email: str
    referred_by: str
    referred_date: str | None = None
    approval_status: str
    candidate_status: str
    referral_score: float | None = None
    best_match: dict[str, Any] | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)


class ReferralListItem(BaseModel):
    candidate_id: str
    name: str = ""
    full_name: str = ""
    email: str = ""
    referred_by: str = ""
    referred_date: str = ""
    approval_status: str = "Pending"
    candidate_status: str = "New"
    referral_score: float = 0.0
    best_match: dict[str, Any] | None = None
    best_match_title: str | None = None


class ReferralListResponse(BaseModel):
    total: int
    data: list[ReferralListItem]


# ── Approvals Models ──────────────────────────────────────────────────────────

class PendingApprovalItem(BaseModel):
    candidate_id: str
    name: str = ""
    full_name: str = ""
    email: str
    referred_by: str
    referred_date: str | None = None
    referral_score: float | None = None
    best_match: dict[str, Any] | None = None
    current_employer: str | None = None
    current_job_title: str | None = None
    experience_years: float | None = None
    top_skills: list[str] = Field(default_factory=list)
    days_pending: int = 0


class ApprovalDetailResponse(BaseModel):
    candidate_id: str
    full_name: str = ""
    email: str = ""
    alternate_email: str | None = None
    phone: str | None = None
    candidate_status: str = "New"
    approval_status: str = "Pending"
    approval_note: str | None = None
    referred_by: str = ""
    referred_date: str | None = None
    referral_score: float | None = None
    identity_mismatch: bool = False
    has_identity_mismatch: bool = False
    identity_mismatch_details: str | None = None
    candidate: dict[str, Any] = Field(default_factory=dict)
    parsed_profile: dict[str, Any] | None = None
    match_details: dict[str, Any] | None = None
    best_match: dict[str, Any] | None = None


class ApproveRejectRequest(BaseModel):
    note: str | None = Field(default=None, description="Optional or required recruiter note for approval/rejection")
    requester_email: str | None = Field(default=None, description="Requester email (for X-Agent-Key tool calls)")


class ApprovalActionResponse(BaseModel):
    success: bool
    candidate_id: str
    approval_status: str
    message: str


# ── Job Models ────────────────────────────────────────────────────────────────

class JobMatchRequest(BaseModel):
    candidate_id: str | None = Field(default=None, description="Candidate ID to match")
    candidate_email: str | None = Field(default=None, description="Candidate email to match")
    min_match: int = Field(default=0, ge=0, le=100, description="Minimum match percentage filter")
    requester_email: str | None = Field(default=None, description="Requester email for agent tool auth")


class JobMatchResult(BaseModel):
    job_id: str
    job_title: str
    match_percent: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_fit: bool = True
    department: str | None = None
    job_description: str | None = None
    notes: str | None = None


class JobMatchResponse(BaseModel):
    candidate_id: str | None = None
    total_matches: int
    matches: list[JobMatchResult]


class JobOpeningItem(BaseModel):
    id: str
    title: str
    department: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    required_experience: float | None = None
    status: str
    job_description: str | None = None


class JobOpeningsResponse(BaseModel):
    total: int
    data: list[JobOpeningItem]


# ── Employee Models ───────────────────────────────────────────────────────────

class EmployeePointsResponse(BaseModel):
    email: str
    employee_email: str = ""
    referral_count: int = 0
    total_referrals: int = 0
    approved_count: int = 0
    approved_referrals: int = 0
    points: int = 0
    points_per_referral: int = 10


class EmployeeHistoryResponse(BaseModel):
    email: str
    total: int
    referrals: list[ReferralListItem]


# ── Interview Models ──────────────────────────────────────────────────────────

class InterviewScheduleRequest(BaseModel):
    candidate_id: str = Field(..., description="Candidate ID (must be in Approved status)")
    start_time: str = Field(..., description="ISO 8601 string for interview start time (e.g. 2026-10-05T14:00:00Z)")
    duration_minutes: int = Field(default=60, ge=15, le=240, description="Interview duration in minutes")
    interviewer_email: str | None = Field(default=None, description="Optional interviewer email from UI")
    interviewer_emails: list[str] | None = Field(default=None, description="Optional extra interviewer email addresses")
    subject: str | None = Field(default=None, description="Interview meeting subject")
    notes: str | None = Field(default=None, description="Optional interview agenda or recruiter notes")
    requester_email: str | None = Field(default=None, description="Requester email for X-Agent-Key tool calls")


class InterviewScheduleResponse(BaseModel):
    success: bool
    candidate_id: str
    meeting_url: str
    start_time: str
    end_time: str
    status: str
    message: str


# ── Notifications Models ──────────────────────────────────────────────────────

class EmailNotificationRequest(BaseModel):
    to_email: str | None = Field(default=None, description="Recipient email address")
    recipient_email: str | None = Field(default=None, description="Recipient email address (alias)")
    subject: str = Field(..., description="Email subject")
    message: str | None = Field(default=None, description="Email body content (markdown or plain text)")
    body_html: str | None = Field(default=None, description="HTML email content")
    body_text: str | None = Field(default=None, description="Plain text fallback email content")
    requester_email: str | None = Field(default=None, description="Requester email for agent tool auth")


class EmailNotificationResponse(BaseModel):
    success: bool
    message: str


# ── Analytics Models ──────────────────────────────────────────────────────────

class DashboardMetricsResponse(BaseModel):
    total_referrals: int
    pending_approvals: int
    approved_referrals: int
    rejected_referrals: int
    interviews_scheduled: int
    total_points_awarded: int
    conversion_rate_percent: float
    avg_approval_days: float


class FunnelStageItem(BaseModel):
    stage: str
    count: int
    conversion_from_previous: float


class ConversionMetricsResponse(BaseModel):
    total_referrals: int
    approved: int
    scheduled: int
    hired: int
    referral_to_approved_percent: float
    approved_to_interview_percent: float
    overall_hire_conversion_percent: float
    funnel_stages: list[FunnelStageItem] = Field(default_factory=list)
    overall_hire_rate: float = 0.0


class PendingReferralsResponse(BaseModel):
    count: int
    threshold_days: int
    referrals: list[dict[str, Any]]
    overdue_referrals: list[dict[str, Any]] = Field(default_factory=list)


class ReferralTrendsResponse(BaseModel):
    periods: list[dict[str, Any]]


class TopCandidatesResponse(BaseModel):
    role: str
    candidates: list[dict[str, Any]]
    total_matching: int = 0
    available_jobs: list[str] = Field(default_factory=list)
    message: str | None = None


# ── Chat Models ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to the multi-agent chat platform")
    conversation_id: str | None = Field(default=None, description="Session / conversation ID for continuity")


class ChatResponse(BaseModel):
    response: str
    conversation_id: str | None = None
