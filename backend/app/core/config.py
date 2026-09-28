"""
Core configuration settings for the Employee Referral Optimization Agent.
Loads from environment variables or .env file using pydantic-settings.
"""

from typing import Any
import json
import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = Field(default="Employee Referral Optimization Agent", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")  # development | production
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Security & Auth
    auth_mode: str = Field(default="otp", alias="AUTH_MODE")  # otp | email_only
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_expiry_hours: int = Field(default=8, alias="JWT_EXPIRY_HOURS")
    agent_api_key: str = Field(default="", alias="AGENT_API_KEY")

    # Zoho Recruit (India DC default)
    zoho_client_id: str = Field(default="", alias="ZOHO_CLIENT_ID")
    zoho_client_secret: str = Field(default="", alias="ZOHO_CLIENT_SECRET")
    zoho_refresh_token: str = Field(default="", alias="ZOHO_REFRESH_TOKEN")
    zoho_accounts_base_url: str = Field(default="https://accounts.zoho.in", alias="ZOHO_ACCOUNTS_BASE_URL")
    zoho_recruit_base_url: str = Field(default="https://recruit.zoho.in/recruit/v2", alias="ZOHO_RECRUIT_BASE_URL")

    # Microsoft Graph (Teams Meetings & Email)
    ms_tenant_id: str = Field(default="", alias="MS_TENANT_ID")
    ms_client_id: str = Field(default="", alias="MS_CLIENT_ID")
    ms_client_secret: str = Field(default="", alias="MS_CLIENT_SECRET")
    ms_organizer_upn: str = Field(default="", alias="MS_ORGANIZER_UPN")
    ms_sender_upn: str = Field(default="", alias="MS_SENDER_UPN")

    # iGentic AI Platform (Multi-Agent Chat)
    igentic_executor_url: str = Field(default="", alias="IGENTIC_EXECUTOR_URL")
    igentic_app_id: str = Field(default="", alias="IGENTIC_APP_ID")
    igentic_api_key: str = Field(default="", alias="IGENTIC_API_KEY")
    igentic_bearer_token: str = Field(default="", alias="IGENTIC_BEARER_TOKEN")
    igentic_username: str = Field(default="", alias="IGENTIC_USERNAME")

    # iGentic Resume Parser Agent (Optional separate single-agent app)
    igentic_parser_executor_url: str = Field(default="", alias="IGENTIC_PARSER_EXECUTOR_URL")
    igentic_parser_app_id: str = Field(default="", alias="IGENTIC_PARSER_APP_ID")

    # Frontend & CORS
    cors_origins: list[str] = Field(default=["http://localhost:5173"], alias="CORS_ORIGINS")
    frontend_base_url: str = Field(default="http://localhost:5173", alias="FRONTEND_BASE_URL")

    # Referral & Scoring Policy
    min_associate_match: int = Field(default=40, alias="MIN_ASSOCIATE_MATCH")
    points_per_referral: int = Field(default=10, alias="POINTS_PER_REFERRAL")
    max_resume_mb: int = Field(default=5, alias="MAX_RESUME_MB")
    resume_parser_mode: str = Field(default="auto", alias="RESUME_PARSER_MODE")  # auto | agent | python

    # Recruiter notifications (comma-separated, fallback to active Zoho recruiters)
    recruiter_notify_emails: str = Field(default="", alias="RECRUITER_NOTIFY_EMAILS")

    # Candidate Lifecycle Status Values in Zoho Recruit
    status_on_referral: str = Field(default="New", alias="STATUS_ON_REFERRAL")
    status_on_approval: str = Field(default="In-Review", alias="STATUS_ON_APPROVAL")
    status_on_rejection: str = Field(default="Rejected", alias="STATUS_ON_REJECTION")
    status_on_interview_scheduled: str = Field(default="Interview Scheduled", alias="STATUS_ON_INTERVIEW_SCHEDULED")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None:
            return ["http://localhost:5173"]
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [o.strip() for o in value.split(",") if o.strip()]
        return ["http://localhost:5173"]

    @model_validator(mode="after")
    def validate_environment_policies(self) -> "Settings":
        # Rule: AUTH_MODE=email_only is strictly prohibited when APP_ENV=production
        if self.app_env.lower() == "production" and self.auth_mode.lower() == "email_only":
            raise ValueError(
                "CRITICAL SECURITY CONFIGURATION ERROR: AUTH_MODE=email_only is strictly prohibited "
                "in production. Set AUTH_MODE=otp."
            )

        # In production, enforce presence of core required secrets
        if self.app_env.lower() == "production":
            missing: list[str] = []
            if not self.jwt_secret_key:
                missing.append("JWT_SECRET_KEY")
            if not self.agent_api_key:
                missing.append("AGENT_API_KEY")
            if not self.zoho_client_id:
                missing.append("ZOHO_CLIENT_ID")
            if not self.zoho_client_secret:
                missing.append("ZOHO_CLIENT_SECRET")
            if not self.zoho_refresh_token:
                missing.append("ZOHO_REFRESH_TOKEN")

            if missing:
                raise ValueError(
                    f"Production startup failed due to missing required environment variables: {', '.join(missing)}. "
                    "Ensure these are set in Container Apps secrets or environment configuration."
                )

        return self

    def derive_role(self, profile_name: str | None, role_name: str | None) -> str | None:
        """
        Derives application role based on Zoho Recruit user's Profile and Role.
        Rules:
          - Profile or Role = Employee -> 'employee'
          - Administrator or contains 'Recruiter' -> 'recruiter'
          - Contains 'Hiring Manager' -> 'hiring_manager'
          - Anything else -> None (role not permitted)
        """
        p = (profile_name or "").lower().strip()
        r = (role_name or "").lower().strip()

        # Check for recruiter / admin first
        if "administrator" in p or "recruiter" in p or "recruiter" in r or "admin" in r:
            return "recruiter"

        # Check for hiring manager
        if "hiring manager" in p or "hiring manager" in r:
            return "hiring_manager"

        # Check for employee
        if p == "employee" or r == "employee" or "employee" in p or "employee" in r:
            return "employee"

        return None


# Global cached settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
