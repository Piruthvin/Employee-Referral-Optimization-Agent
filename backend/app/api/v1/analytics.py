"""
Analytics and reporting endpoints for recruiters and Analytics_Agent tools:
- GET /analytics/dashboard (Tool: get_dashboard_metrics)
- GET /analytics/conversion (Tool: get_conversion_rate)
- GET /analytics/pending (Tool: get_pending_referrals)
- GET /analytics/trends (Tool: get_referral_trends)
- POST /analytics/top-candidates (Tool: get_top_referrals_by_role)
Role enforcement: restricted to recruiters and hiring managers.
"""

from typing import Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.dependencies import get_auth_or_agent_user, get_tool_user
from app.services.analytics_service import analytics_service
from app.domain.models import (
    DashboardMetricsResponse,
    ConversionMetricsResponse,
    PendingReferralsResponse,
    ReferralTrendsResponse,
    TopCandidatesResponse,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _assert_recruiter_or_manager(user: dict[str, Any]) -> None:
    role = user.get("role", "")
    if role not in ("recruiter", "hiring_manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Analytics operations require recruiter or hiring manager role. Current role is '{role}'.",
        )


class TopCandidatesRequest(BaseModel):
    role: str | None = Field(default=None, description="Job role, title, or skill to filter top candidates by")
    job_title: str | None = Field(default=None, description="Target job title (alias for role)")
    limit: int = Field(default=5, ge=1, le=50, description="Max candidates to return (default: 5)")
    requester_email: str | None = Field(default=None, description="Requester email for agent tool auth")


class ToolAnalyticsRequest(BaseModel):
    requester_email: str | None = None


class ToolPendingReferralsRequest(BaseModel):
    threshold_days: int | None = Field(default=None, description="Days pending threshold")
    days_threshold: int | None = Field(default=None, description="Days pending threshold (alias)")
    requester_email: str | None = None


@router.get(
    "/dashboard",
    response_model=DashboardMetricsResponse,
    summary="Get dashboard metrics",
    description="Calculates comprehensive referral KPIs: total referrals, pending reviews, approvals, rejections, interviews, points, and conversion rates. Accessible via JWT or X-Agent-Key.",
)
async def get_dashboard_metrics_get(
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> DashboardMetricsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_dashboard_metrics()


@router.post(
    "/dashboard",
    response_model=DashboardMetricsResponse,
    tags=["Agent Tools"],
    summary="Tool 9: Get Dashboard Metrics",
    description="Calculates comprehensive recruitment KPIs (total referrals, pending, approved, rejected, interview count, conversion %). Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_dashboard_metrics_post(
    req: ToolAnalyticsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> DashboardMetricsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_dashboard_metrics()


@router.get(
    "/conversion",
    response_model=ConversionMetricsResponse,
    summary="Get conversion funnel",
    description="Calculates conversion percentage across hiring funnel stages: submitted -> approved -> interview -> hired.",
)
async def get_conversion_rate_get(
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ConversionMetricsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_conversion_metrics()


@router.post(
    "/conversion",
    response_model=ConversionMetricsResponse,
    tags=["Agent Tools"],
    summary="Tool 10: Get Conversion Rate",
    description="Calculates conversion percentage across hiring funnel stages (Referral -> Approved -> Interview -> Offer -> Hire). Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_conversion_rate_post(
    req: ToolAnalyticsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> ConversionMetricsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_conversion_metrics()


@router.get(
    "/pending",
    response_model=PendingReferralsResponse,
    summary="Get pending referrals",
    description="Returns referrals waiting for recruiter review exceeding the threshold number of days.",
)
async def get_pending_referrals_get(
    threshold_days: int = Query(default=7, ge=1, le=180, description="Minimum days pending approval"),
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> PendingReferralsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_pending_referrals(threshold_days)


@router.post(
    "/pending",
    response_model=PendingReferralsResponse,
    tags=["Agent Tools"],
    summary="Tool 11: Get Pending Referrals",
    description="Returns referrals waiting for recruiter review exceeding the threshold number of days. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_pending_referrals_post(
    req: ToolPendingReferralsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> PendingReferralsResponse:
    _assert_recruiter_or_manager(current_user)
    days = 5
    if req:
        if req.days_threshold is not None:
            days = req.days_threshold
        elif req.threshold_days is not None:
            days = req.threshold_days
    return await analytics_service.get_pending_referrals(days)


@router.get(
    "/trends",
    response_model=ReferralTrendsResponse,
    summary="Get referral trends",
    description="Provides monthly and chronological volume trends for submissions, approvals, and hires.",
)
async def get_referral_trends_get(
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ReferralTrendsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_referral_trends()


@router.post(
    "/trends",
    response_model=ReferralTrendsResponse,
    tags=["Agent Tools"],
    summary="Tool 13: Get Referral Trends",
    description="Provides monthly and chronological volume trends for submissions, approvals, and hires. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_referral_trends_post(
    req: ToolAnalyticsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> ReferralTrendsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_referral_trends()


@router.post(
    "/top-candidates",
    response_model=TopCandidatesResponse,
    tags=["Agent Tools"],
    summary="Tool 12: Get Top Referrals by Role",
    description="Retrieves the highest-ranked candidates for a specific role or skill set based on match score. Restricted to recruiters and hiring managers. Callable with no authentication, a valid frontend JWT, or X-Agent-Key — see agent-prompts/TOOLS_CONFIG.md.",
)
async def get_top_candidates(
    req: TopCandidatesRequest,
    current_user: dict[str, Any] = Depends(get_tool_user),
) -> TopCandidatesResponse:
    _assert_recruiter_or_manager(current_user)
    target_role = (req.role or req.job_title or "").strip()
    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role or job_title is required.",
        )
    res = await analytics_service.get_top_candidates_by_role(target_role)
    if isinstance(res, dict):
        candidates = res.get("candidates", [])
        if req.limit and len(candidates) > req.limit:
            res["candidates"] = candidates[:req.limit]
        return TopCandidatesResponse(**res)
    else:
        if req.limit and len(res.candidates) > req.limit:
            res.candidates = res.candidates[:req.limit]
        return res
