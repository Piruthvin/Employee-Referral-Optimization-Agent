"""
Analytics and reporting service.
Computes recruitment funnel metrics, approval turnaround, referral trends,
and derived employee points purely from Zoho Recruit Candidate records.
"""

from typing import Any
from datetime import datetime, date
from collections import defaultdict

from app.core.config import get_settings
from app.services.zoho_service import zoho_service
from app.domain.models import (
    DashboardMetricsResponse,
    ConversionMetricsResponse,
    FunnelStageItem,
    PendingReferralsResponse,
    ReferralTrendsResponse,
    TopCandidatesResponse,
)


class AnalyticsService:
    async def get_dashboard_metrics(self) -> DashboardMetricsResponse:
        """Calculates top-level KPI metrics across all referral candidates."""
        settings = get_settings()
        candidates = await zoho_service.get_all_candidates_cached()

        total = 0
        pending = 0
        approved = 0
        rejected = 0
        scheduled = 0
        hired = 0
        approval_durations: list[int] = []

        for c in candidates:
            referred_by = c.get("Referred_By")
            source = (c.get("Source") or "").lower()
            if not (referred_by or "referral" in source):
                continue

            total += 1
            app_status = (c.get("Referral_Approval_Status") or "Pending").strip().lower()
            cand_status = (c.get("Candidate_Status") or "").strip().lower()

            if app_status == "approved":
                approved += 1
            elif app_status == "rejected":
                rejected += 1
            else:
                pending += 1

            if "interview" in cand_status:
                scheduled += 1
            if "hire" in cand_status:
                hired += 1

            # Approval turnaround time calculation
            ref_date = c.get("Referred_Date")
            mod_date = c.get("Modified_Time")
            if app_status in ("approved", "rejected") and ref_date and mod_date:
                try:
                    d1 = datetime.strptime(ref_date[:10], "%Y-%m-%d").date()
                    d2 = datetime.strptime(mod_date[:10], "%Y-%m-%d").date()
                    diff = max(0, (d2 - d1).days)
                    approval_durations.append(diff)
                except Exception:
                    pass

        avg_days = round(sum(approval_durations) / len(approval_durations), 1) if approval_durations else 0.0
        conversion_rate = round((hired / total * 100.0), 1) if total > 0 else 0.0
        total_points = total * settings.points_per_referral

        return DashboardMetricsResponse(
            total_referrals=total,
            pending_approvals=pending,
            approved_referrals=approved,
            rejected_referrals=rejected,
            interviews_scheduled=scheduled,
            total_points_awarded=total_points,
            conversion_rate_percent=conversion_rate,
            avg_approval_days=avg_days,
        )

    async def get_conversion_metrics(self) -> ConversionMetricsResponse:
        """Calculates funnel conversion ratios and 5-stage drop-off metrics."""
        candidates = await zoho_service.get_all_candidates_cached()

        total = 0
        approved = 0
        scheduled = 0
        offer = 0
        hired = 0

        for c in candidates:
            referred_by = c.get("Referred_By")
            source = (c.get("Source") or "").lower()
            if not (referred_by or "referral" in source):
                continue

            total += 1
            app_status = (c.get("Referral_Approval_Status") or "").strip().lower()
            cand_status = (c.get("Candidate_Status") or "").strip().lower()

            is_hired = "hire" in cand_status or "joined" in cand_status
            is_offer = is_hired or ("offer" in cand_status)
            is_interview = is_offer or ("interview" in cand_status or "scheduled" in cand_status)
            is_approved = is_interview or (app_status == "approved" or "in-review" in cand_status)

            if is_approved:
                approved += 1
            if is_interview:
                scheduled += 1
            if is_offer:
                offer += 1
            if is_hired:
                hired += 1

        ref_to_app = round((approved / total * 100.0), 1) if total > 0 else 0.0
        app_to_int = round((scheduled / approved * 100.0), 1) if approved > 0 else 0.0
        hire_conv = round((hired / total * 100.0), 1) if total > 0 else 0.0

        # Build 5-stage recruitment funnel per TOOLS_CONFIG.md and RecruiterDashboard
        # 1. Referral (100% baseline)
        stage_referral_conv = 100.0 if total > 0 else 0.0
        # 2. Approved (conversion from Referral)
        stage_approved_conv = ref_to_app
        # 3. Interview (conversion from Approved)
        stage_interview_conv = app_to_int
        # 4. Offer (conversion from Interview)
        stage_offer_conv = round((offer / scheduled * 100.0), 1) if scheduled > 0 else 0.0
        # 5. Hire (conversion from Offer, or Interview if no intermediate offer stage)
        if offer > 0:
            stage_hire_conv = round((hired / offer * 100.0), 1)
        elif scheduled > 0:
            stage_hire_conv = round((hired / scheduled * 100.0), 1)
        else:
            stage_hire_conv = 0.0

        funnel_stages = [
            FunnelStageItem(stage="Referral", count=total, conversion_from_previous=stage_referral_conv),
            FunnelStageItem(stage="Approved", count=approved, conversion_from_previous=stage_approved_conv),
            FunnelStageItem(stage="Interview", count=scheduled, conversion_from_previous=stage_interview_conv),
            FunnelStageItem(stage="Offer", count=offer, conversion_from_previous=stage_offer_conv),
            FunnelStageItem(stage="Hire", count=hired, conversion_from_previous=stage_hire_conv),
        ]
        overall_hire_rate = round((hired / total * 100.0), 1) if total > 0 else 0.0

        return ConversionMetricsResponse(
            total_referrals=total,
            approved=approved,
            scheduled=scheduled,
            hired=hired,
            referral_to_approved_percent=ref_to_app,
            approved_to_interview_percent=app_to_int,
            overall_hire_conversion_percent=hire_conv,
            funnel_stages=funnel_stages,
            overall_hire_rate=overall_hire_rate,
        )

    async def get_pending_referrals(self, threshold_days: int = 7) -> PendingReferralsResponse:
        """Retrieves referrals awaiting approval exceeding the specified day threshold."""
        candidates = await zoho_service.get_all_candidates_cached()
        overdue: list[dict[str, Any]] = []

        today = date.today()
        for c in candidates:
            app_status = (c.get("Referral_Approval_Status") or "Pending").strip().lower()
            referred_by = c.get("Referred_By")
            source = (c.get("Source") or "").lower()
            if not (referred_by or "referral" in source):
                continue

            if app_status == "pending" or not app_status:
                ref_date_str = c.get("Referred_Date")
                days_pending = 0
                if ref_date_str:
                    try:
                        ref_d = datetime.strptime(ref_date_str[:10], "%Y-%m-%d").date()
                        days_pending = (today - ref_d).days
                    except Exception:
                        pass

                if days_pending >= threshold_days:
                    fn = c.get("First_Name") or ""
                    ln = c.get("Last_Name") or ""
                    overdue.append({
                        "candidate_id": str(c.get("id")),
                        "name": f"{fn} {ln}".strip() or "Candidate",
                        "email": c.get("Email"),
                        "referred_by": referred_by,
                        "days_pending": days_pending,
                        "referral_score": c.get("Referral_Score"),
                    })

        overdue.sort(key=lambda x: x["days_pending"], reverse=True)
        return PendingReferralsResponse(
            count=len(overdue),
            threshold_days=threshold_days,
            referrals=overdue,
            overdue_referrals=overdue,
        )

    async def get_referral_trends(self) -> ReferralTrendsResponse:
        """Groups referrals by month to compute trend trajectories."""
        candidates = await zoho_service.get_all_candidates_cached()
        month_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "approved": 0, "hired": 0})

        for c in candidates:
            referred_by = c.get("Referred_By")
            source = (c.get("Source") or "").lower()
            if not (referred_by or "referral" in source):
                continue

            ref_date = c.get("Referred_Date") or c.get("Created_Time")
            period = ref_date[:7] if ref_date and len(ref_date) >= 7 else "Unknown"

            month_counts[period]["total"] += 1
            app_st = (c.get("Referral_Approval_Status") or "").lower()
            cand_st = (c.get("Candidate_Status") or "").lower()
            if app_st == "approved":
                month_counts[period]["approved"] += 1
            if "hire" in cand_st:
                month_counts[period]["hired"] += 1

        periods_data = [
            {"period": k, **v}
            for k, v in sorted(month_counts.items(), key=lambda x: x[0])
            if k != "Unknown"
        ]

        return ReferralTrendsResponse(periods=periods_data)

    async def get_top_candidates_by_role(self, role: str) -> TopCandidatesResponse:
        """Finds top-scored candidates filtered by role or job title."""
        candidates = await zoho_service.get_all_candidates_cached()
        matching: list[dict[str, Any]] = []

        query = role.strip().lower()
        for c in candidates:
            cand_title = (c.get("Current_Job_Title") or "").lower()
            skills_raw = str(c.get("Skill_Set") or "").lower()

            if query in cand_title or query in skills_raw:
                fn = c.get("First_Name") or ""
                ln = c.get("Last_Name") or ""
                matching.append({
                    "candidate_id": str(c.get("id")),
                    "name": f"{fn} {ln}".strip() or "Candidate",
                    "email": c.get("Email"),
                    "job_title": c.get("Current_Job_Title"),
                    "referral_score": c.get("Referral_Score") or 0.0,
                    "experience_years": c.get("Experience_in_Years"),
                    "approval_status": c.get("Referral_Approval_Status") or "Pending",
                })

        matching.sort(key=lambda x: x["referral_score"], reverse=True)
        return TopCandidatesResponse(role=role, candidates=matching[:15])

    async def get_employee_points(self, employee_email: str) -> dict[str, Any]:
        """Calculates derived points for an employee purely from Zoho Candidates."""
        settings = get_settings()
        referrals = await zoho_service.get_candidates_by_referrer(employee_email)

        total_count = len(referrals)
        approved_count = 0

        for r in referrals:
            st = (r.get("Referral_Approval_Status") or "").strip().lower()
            if st == "approved":
                approved_count += 1

        points = total_count * settings.points_per_referral

        return {
            "email": employee_email,
            "employee_email": employee_email,
            "referral_count": total_count,
            "total_referrals": total_count,
            "approved_count": approved_count,
            "approved_referrals": approved_count,
            "points": points,
            "points_per_referral": settings.points_per_referral,
        }


analytics_service = AnalyticsService()
