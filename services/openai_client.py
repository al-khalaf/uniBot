"""OpenAI API client helpers with graceful fallbacks.

The service exposes structured helpers that wrap common operations we need in
uniBot without forcing the rest of the codebase to know about the third-party
SDK details. The functions intentionally return JSON-serialisable objects so
that the API views can respond directly.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from flask import current_app

try:  # pragma: no cover - import guard for environments without the SDK
    from openai import APIError, OpenAI
except Exception:  # pragma: no cover - fall back to sentinel when missing
    APIError = Exception  # type: ignore
    OpenAI = None  # type: ignore


LOGGER = logging.getLogger(__name__)


class OpenAIServiceError(RuntimeError):
    """Application level exception for OpenAI failures."""


@dataclass(slots=True)
class OpenAIService:
    """Lightweight wrapper that handles configuration and common prompts."""

    api_key: Optional[str]
    model: str = "gpt-4o-mini"
    timeout: Optional[float] = None

    _client: Optional["OpenAI"] = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and OpenAI is not None)

    def _ensure_client(self) -> "OpenAI":
        if not self.enabled:
            raise OpenAIServiceError(
                "OpenAI client is not configured. Provide OPENAI_API_KEY to enable AI features."
            )
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        return self._client

    # -- high level helpers -------------------------------------------------

    def generate_study_plan(self, profile: Dict[str, Any], courses: List[Dict[str, Any]], timeframe: str,
                            preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a structured study plan.

        Returns a dict with "summary", "tasks", and "recommendations" keys.
        """
        client = self._ensure_client()
        prompt = self._format_study_plan_prompt(profile, courses, timeframe, preferences)
        LOGGER.debug("Requesting study plan with payload: %s", prompt)
        try:
            response = client.responses.create(
                model=self.model,
                input=prompt,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "study_plan_response",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "summary": {"type": "string"},
                                "tasks": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "due": {"type": "string", "description": "ISO8601 date or relative label"},
                                            "effort_hours": {"type": "number"},
                                            "notes": {"type": "string"},
                                            "course_code": {"type": "string"},
                                        },
                                        "required": ["title"],
                                        "additionalProperties": False,
                                    },
                                },
                                "recommendations": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {"type": "string"},
                                            "detail": {"type": "string"},
                                        },
                                        "required": ["type", "detail"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["summary", "tasks"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
        except APIError as exc:  # pragma: no cover - depends on external API
            LOGGER.exception("OpenAI study plan generation failed")
            raise OpenAIServiceError(str(exc)) from exc

        return self._extract_json(response)

    def summarise_text(self, text: str, audience: Optional[str] = None) -> Dict[str, str]:
        """Summarise long documents, optionally tailoring to an audience."""
        client = self._ensure_client()
        instructions = (
            "Provide a concise summary with 3-5 bullet points and a friendly lead paragraph."
        )
        if audience:
            instructions += f" Tailor the tone for {audience}."
        try:
            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
        except APIError as exc:  # pragma: no cover
            LOGGER.exception("OpenAI summarisation failed")
            raise OpenAIServiceError(str(exc)) from exc
        payload = self._extract_json(response)
        if "summary" not in payload:
            payload = {"summary": payload.get("text") or json.dumps(payload)}
        return payload

    def mood_check(self, entries: List[str]) -> Dict[str, Any]:
        """Classify a list of journal entries into wellness buckets."""
        client = self._ensure_client()
        try:
            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Classify each journal entry into one of: positive, neutral, concerned. "
                            "Return actionable next steps when you see risk signals."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({"entries": entries}),
                    },
                ],
                response_format={"type": "json_schema", "json_schema": {
                    "name": "mood_screen",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "entry": {"type": "string"},
                                        "classification": {"type": "string"},
                                        "confidence": {"type": "number"},
                                        "recommended_action": {"type": "string"},
                                    },
                                    "required": ["entry", "classification"],
                                    "additionalProperties": False,
                                },
                            },
                            "escalate": {"type": "boolean"},
                            "notes": {"type": "string"},
                        },
                        "required": ["results"],
                        "additionalProperties": False,
                    },
                }},
            )
        except APIError as exc:  # pragma: no cover
            LOGGER.exception("OpenAI mood classification failed")
            raise OpenAIServiceError(str(exc)) from exc
        return self._extract_json(response)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _format_study_plan_prompt(profile: Dict[str, Any], courses: List[Dict[str, Any]], timeframe: str,
                                   preferences: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        content = {
            "profile": profile,
            "courses": courses,
            "timeframe": timeframe,
            "preferences": preferences or {},
        }
        return [
            {
                "role": "system",
                "content": (
                    "Generate a realistic and structured study plan with actionable tasks. "
                    "Balance workload, highlight critical deadlines, and respect student preferences."
                ),
            },
            {"role": "user", "content": json.dumps(content)},
        ]

    @staticmethod
    def _extract_json(response: Any) -> Dict[str, Any]:  # pragma: no cover - exercised via API
        """Best-effort extraction that tolerates SDK shape differences."""
        if response is None:
            return {}
        # New Responses API
        output = getattr(response, "output", None)
        if output:
            parts: List[str] = []
            for item in output:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", None) == "output_text" and getattr(content, "text", None):
                        parts.append(content.text)
            if parts:
                data = "".join(parts).strip()
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {"text": data}
        # Legacy completion style fallback
        choices = getattr(response, "choices", None)
        if choices:
            message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if content:
                try:
                    return json.loads(content)
                except (TypeError, json.JSONDecodeError):
                    return {"text": content}
        return {}


def init_app(app) -> OpenAIService:
    """Initialise the OpenAI service and attach it to the Flask app."""
    service = OpenAIService(
        api_key=app.config.get("OPENAI_API_KEY"),
        model=app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
        timeout=app.config.get("OPENAI_TIMEOUT"),
    )
    app.extensions["openai_service"] = service
    return service


def get_openai_service() -> OpenAIService:
    app = current_app._get_current_object()
    service: Optional[OpenAIService] = app.extensions.get("openai_service")
    if service is None:
        service = init_app(app)
    return service

