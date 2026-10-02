"""
Resume parsing service orchestrator.
Manages mode selection (auto, agent, python), calls the iGentic Resume_Parser_Agent
via the unified iGentic executor, validates against ParsedResume Pydantic model,
and falls back gracefully to deterministic Python parser.
"""

import json
import logging
import re
from typing import Any, Tuple

from app.core.config import get_settings
from app.domain.resume_schema import ParsedResume
from app.services.igentic_client import igentic_client
from app.services.resume_parser_python import python_resume_parser

logger = logging.getLogger(__name__)


class ResumeParserService:
    async def parse_resume(
        self,
        raw_text: str,
        candidate_email: str | None = None,
        candidate_name: str | None = None,
    ) -> Tuple[ParsedResume, str]:
        """
        Parses resume text according to configured RESUME_PARSER_MODE (auto | agent | python).
        When mode is 'agent' or 'auto', invokes the unified iGentic executor which routes to
        Resume_Parser_Agent via RULE 1.

        Returns:
            (parsed_resume: ParsedResume, parser_used: "agent" | "python")
        """
        settings = get_settings()
        mode = settings.resume_parser_mode.lower().strip()

        # Direct python mode
        if mode == "python":
            logger.info("Using deterministic Python resume parser (mode=python).")
            return self._parse_with_python(raw_text)

        # Attempt agent if configured
        if mode in ("agent", "auto"):
            if settings.igentic_executor_url and settings.igentic_app_id:
                try:
                    logger.info("Calling iGentic Resume_Parser_Agent via unified executor...")
                    raw_result = await igentic_client.parse_resume(
                        raw_text=raw_text,
                        candidate_email=candidate_email,
                        candidate_name=candidate_name,
                    )
                    if raw_result:
                        data_dict = self._unmarshal_json(raw_result)
                        parsed = ParsedResume.model_validate(data_dict)
                        logger.info("Successfully parsed resume via iGentic Resume_Parser_Agent.")
                        return parsed, "agent"
                except Exception as e:
                    logger.warning("Agent resume parser failed: %s", e)
                    if mode == "agent":
                        raise RuntimeError(f"iGentic Resume_Parser_Agent execution failed: {str(e)}")
            else:
                if mode == "agent":
                    raise ValueError(
                        "RESUME_PARSER_MODE=agent configured but IGENTIC_EXECUTOR_URL or "
                        "IGENTIC_APP_ID is missing."
                    )
                logger.info("iGentic executor credentials not configured. Falling back to Python parser.")

        # Fallback to python parser
        logger.info("Using deterministic Python resume parser (fallback/auto).")
        return self._parse_with_python(raw_text)

    def _parse_with_python(self, raw_text: str) -> Tuple[ParsedResume, str]:
        raw_dict = python_resume_parser.parse(raw_text)
        validated = ParsedResume.model_validate(raw_dict)
        return validated, "python"

    def _unmarshal_json(self, raw_output: Any) -> dict:
        """
        Robustly parses JSON from LLM output.
        Handles:
        - Python dict directly
        - Raw JSON string
        - JSON wrapped in ```json ... ``` or ``` ... ``` code fences
        - Extra conversational prose before or after the JSON payload
        """
        if isinstance(raw_output, dict):
            return raw_output

        if not isinstance(raw_output, str):
            raise ValueError(f"Expected JSON string or dict, got {type(raw_output).__name__}")

        cleaned = raw_output.strip()

        # 1. Strip markdown code fences if present
        if "```" in cleaned:
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
            if fence_match:
                cleaned = fence_match.group(1).strip()
            else:
                # Strip individual fence delimiter lines
                lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()

        # 2. Try direct JSON parsing
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # 3. Extract JSON object substring between outermost braces if surrounded by prose
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate_substr = cleaned[start_idx : end_idx + 1]
            try:
                parsed = json.loads(candidate_substr)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        # 4. Final attempt to raise standard JSONDecodeError with helpful context
        return json.loads(cleaned)


resume_parser_service = ResumeParserService()
