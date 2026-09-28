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

from app.core.dependencies import get_auth_or_agent_user
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
    role: str = Field(..., description="Job role, title, or skill to filter top candidates by")
    requester_email: str | None = Field(default=None, description="Requester email for agent tool auth")


class ToolAnalyticsRequest(BaseModel):
    requester_email: str | None = None


class ToolPendingReferralsRequest(BaseModel):
    threshold_days: int = 7
    requester_email: str | None = None


@router.get(
    "/dashboard",
    response_model=DashboardMetricsResponse,
    summary="Get dashboard metrics (Tool Endpoint)",
    description="Calculates comprehensive referral KPIs: total referrals, pending reviews, approvals, rejections, interviews, points, and conversion rates. Accessible via JWT or X-Agent-Key.",
)
@router.post(
    "/dashboard",
    response_model=DashboardMetricsResponse,
    summary="Get dashboard metrics (POST Tool Endpoint)",
    description="Calculates comprehensive referral KPIs. POST variant for iGentic tools.",
)
async def get_dashboard_metrics(
    req: ToolAnalyticsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> DashboardMetricsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_dashboard_metrics()


@router.get(
    "/conversion",
    response_model=ConversionMetricsResponse,
    summary="Get conversion funnel (Tool Endpoint)",
    description="Calculates conversion percentage across hiring funnel stages: submitted -> approved -> interview -> hired.",
)
@router.post(
    "/conversion",
    response_model=ConversionMetricsResponse,
    summary="Get conversion funnel (POST Tool Endpoint)",
    description="Calculates conversion percentage across hiring funnel stages. POST variant for iGentic tools.",
)
async def get_conversion_rate(
    req: ToolAnalyticsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ConversionMetricsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_conversion_metrics()


@router.get(
    "/pending",
    response_model=PendingReferralsResponse,
    summary="Get pending referrals (Tool Endpoint)",
    description="Returns referrals waiting for recruiter review exceeding the threshold number of days.",
)
@router.post(
    "/pending",
    response_model=PendingReferralsResponse,
    summary="Get pending referrals (POST Tool Endpoint)",
    description="Returns referrals waiting for recruiter review exceeding the threshold number of days. POST variant for iGentic tools.",
)
async def get_pending_referrals(
    threshold_days: int = Query(default=7, ge=1, le=180, description="Minimum days pending approval"),
    req: ToolPendingReferralsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> PendingReferralsResponse:
    _assert_recruiter_or_manager(current_user)
    days = req.threshold_days if req and req.threshold_days else threshold_days
    return await analytics_service.get_pending_referrals(days)


@router.get(
    "/trends",
    response_model=ReferralTrendsResponse,
    summary="Get referral trends (Tool Endpoint)",
    description="Provides monthly and chronological volume trends for submissions, approvals, and hires.",
)
@router.post(
    "/trends",
    response_model=ReferralTrendsResponse,
    summary="Get referral trends (POST Tool Endpoint)",
    description="Provides monthly and chronological volume trends for submissions, approvals, and hires. POST variant for iGentic tools.",
)
async def get_referral_trends(
    req: ToolAnalyticsRequest | None = None,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> ReferralTrendsResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_referral_trends()


@router.post(
    "/top-candidates",
    response_model=TopCandidatesResponse,
    summary="Get top referrals by role (Tool Endpoint)",
    description="Retrieves the highest-ranked candidates for a specific role or skill set based on match score.",
)
async def get_top_candidates(
    req: TopCandidatesRequest,
    current_user: dict[str, Any] = Depends(get_auth_or_agent_user),
) -> TopCandidatesResponse:
    _assert_recruiter_or_manager(current_user)
    return await analytics_service.get_top_candidates_by_role(req.role)
