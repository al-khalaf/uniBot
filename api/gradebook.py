# api/gradebook.py
from __future__ import annotations
from uuid import UUID

from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func

from api.roles_guard import roles_required
from lms_models import db, Enrollment, Assignment, Grade, User

bp = Blueprint("gradebook", __name__, url_prefix="/api/gradebook")

def _uuid_or_400(v: str, field: str) -> UUID:
    try:
        return UUID(v)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

def _letter(pct: float) -> str:
    if pct >= 90: return "A"
    if pct >= 80: return "B"
    if pct >= 70: return "C"
    if pct >= 60: return "D"
    return "F"

@bp.get("/course/<uuid:offering_id>")
@jwt_required()
def course_gradebook(offering_id):
    """
    Returns per-student totals for a course offering.
    admin/staff only (or students will be rejected).
    """
    roles = set((get_jwt() or {}).get("roles", []))
    if not ({"admin", "staff"} & roles):
        return jsonify({"error": "requires admin or staff"}), 403

    # total possible points for this offering
    totals = (
        db.session.query(
            func.coalesce(func.sum(Assignment.max_points), 0.0)
        )
        .filter(Assignment.course_offering_id == offering_id)
        .scalar()
    )
    totals = float(totals or 0)

    # get enrolled students
    enrolls = (
        db.session.query(Enrollment.student_id, User.first_name, User.last_name, User.email)
        .join(User, User.id == Enrollment.student_id)
        .filter(Enrollment.course_offering_id == offering_id)
        .all()
    )
    if not enrolls:
        return jsonify({"total_points": totals, "students": []})

    # sum of earned points per student
    earned_rows = (
        db.session.query(Grade.student_id, func.coalesce(func.sum(Grade.score), 0.0))
        .join(Assignment, Assignment.id == Grade.assignment_id)
        .filter(Assignment.course_offering_id == offering_id)
        .group_by(Grade.student_id)
        .all()
    )
    earned_map = {sid: float(s) for sid, s in earned_rows}

    students = []
    for sid, fn, ln, email in enrolls:
        earned = earned_map.get(sid, 0.0)
        pct = (earned / totals * 100.0) if totals > 0 else 0.0
        students.append({
            "student_id": str(sid),
            "name": f"{fn or ''} {ln or ''}".strip() or email,
            "email": email,
            "earned": earned,
            "possible": totals,
            "percent": round(pct, 2),
            "letter": _letter(pct)
        })

    students.sort(key=lambda x: (-x["percent"], x["name"]))
    return jsonify({"total_points": totals, "students": students})

@bp.get("/mine")
@jwt_required()
def my_gradebook():
    """
    Roll up per-course percentages for the authenticated student.
    """
    sub = (get_jwt() or {}).get("sub")
    if not sub:
        return jsonify({"courses": []})

    # total possible per offering
    possible_rows = (
        db.session.query(
            Assignment.course_offering_id,
            func.coalesce(func.sum(Assignment.max_points), 0.0)
        )
        .group_by(Assignment.course_offering_id)
        .all()
    )
    possible = {oid: float(s) for oid, s in possible_rows}

    # earned per offering for this student
    earned_rows = (
        db.session.query(
            Assignment.course_offering_id,
            func.coalesce(func.sum(Grade.score), 0.0)
        )
        .join(Grade, Grade.assignment_id == Assignment.id)
        .filter(Grade.student_id == sub)
        .group_by(Assignment.course_offering_id)
        .all()
    )
    earned = {oid: float(s) for oid, s in earned_rows}

    # which courses the student is enrolled in
    course_ids = [e.course_offering_id for e in Enrollment.query.filter_by(student_id=sub).all()]

    result = []
    for oid in course_ids:
        poss = possible.get(oid, 0.0)
        ear = earned.get(oid, 0.0)
        pct = (ear / poss * 100.0) if poss > 0 else 0.0
        result.append({
            "course_offering_id": str(oid),
            "earned": ear,
            "possible": poss,
            "percent": round(pct, 2),
            "letter": _letter(pct)
        })

    result.sort(key=lambda x: x["course_offering_id"])
    return jsonify({"courses": result})
