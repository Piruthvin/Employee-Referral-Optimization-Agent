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
    name: str
    email: str
    referred_by: str
    referred_date: str | None = None
    approval_status: str
    candidate_status: str
    referral_score: float | None = None
    best_match_title: str | None = None


class ReferralListResponse(BaseModel):
    total: int
    data: list[ReferralListItem]


# ── Approvals Models ──────────────────────────────────────────────────────────

class PendingApprovalItem(BaseModel):
    candidate_id: str
    name: str
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
    candidate: dict[str, Any]
    parsed_profile: dict[str, Any] | None = None
    match_details: dict[str, Any] | None = None
    has_identity_mismatch: bool = False
    identity_mismatch_details: str | None = None
    approval_status: str


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
    matched_skills: list[str]
    missing_skills: list[str]
    experience_fit: bool
    department: str | None = None


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


class JobOpeningsResponse(BaseModel):
    total: int
    data: list[JobOpeningItem]


# ── Employee Models ───────────────────────────────────────────────────────────

class EmployeePointsResponse(BaseModel):
    email: str
    referral_count: int
    approved_count: int
    points: int
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
    interviewer_emails: list[str] | None = Field(default=None, description="Optional extra interviewer email addresses")
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
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    message: str = Field(..., description="Email body content (markdown or plain text)")
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


class ConversionMetricsResponse(BaseModel):
    total_referrals: int
    approved: int
    scheduled: int
    hired: int
    referral_to_approved_percent: float
    approved_to_interview_percent: float
    overall_hire_conversion_percent: float


class PendingReferralsResponse(BaseModel):
    count: int
    threshold_days: int
    referrals: list[dict[str, Any]]


class ReferralTrendsResponse(BaseModel):
    periods: list[dict[str, Any]]


class TopCandidatesResponse(BaseModel):
    role: str
    candidates: list[dict[str, Any]]


# ── Chat Models ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to the multi-agent chat platform")
    conversation_id: str | None = Field(default=None, description="Session / conversation ID for continuity")


class ChatResponse(BaseModel):
    response: str
    conversation_id: str | None = None
