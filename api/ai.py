"""AI-assisted workflows using the OpenAI API."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from services import OpenAIServiceError, get_openai_service

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _service():
    return get_openai_service()


@bp.get("/status")
@jwt_required(optional=True)
def status():
    service = _service()
    return jsonify({
        "enabled": service.enabled,
        "model": service.model if service.enabled else None,
    })


@bp.post("/study-plan")
@jwt_required(optional=True)
def generate_study_plan():
    payload = request.get_json() or {}
    profile = payload.get("profile", {})
    courses = payload.get("courses", [])
    timeframe = payload.get("timeframe", "upcoming term")
    preferences = payload.get("preferences")

    service = _service()
    if not service.enabled:
        return jsonify({"error": "OpenAI integration is not configured."}), 503
    try:
        result = service.generate_study_plan(profile, courses, timeframe, preferences)
    except OpenAIServiceError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(result)


@bp.post("/summaries")
@jwt_required(optional=True)
def summarise():
    payload = request.get_json() or {}
    text = payload.get("text")
    if not text:
        return jsonify({"error": "'text' is required"}), 400
    audience = payload.get("audience")
    service = _service()
    if not service.enabled:
        return jsonify({"error": "OpenAI integration is not configured."}), 503
    try:
        summary = service.summarise_text(text, audience)
    except OpenAIServiceError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(summary)


@bp.post("/mood-check")
@jwt_required(optional=True)
def mood_check():
    payload = request.get_json() or {}
    entries = payload.get("entries") or []
    if not isinstance(entries, list) or not entries:
        return jsonify({"error": "'entries' must be a non-empty list"}), 400
    service = _service()
    if not service.enabled:
        return jsonify({"error": "OpenAI integration is not configured."}), 503
    try:
        result = service.mood_check([str(item) for item in entries])
    except OpenAIServiceError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(result)

