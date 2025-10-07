# api/my_day.py
from __future__ import annotations
from datetime import datetime, date, time, timedelta, timezone
from uuid import UUID

from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import and_

from lms_models import db, Enrollment, ClassMeeting, Assignment, CourseOffering

bp = Blueprint("my_day", __name__, url_prefix="/api/myday")

def _uuid_or_400(v: str, field: str) -> UUID:
    from uuid import UUID as _UUID
    try:
        return _UUID(v)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

def _now_utc():
    return datetime.now(timezone.utc)

def _today_local_range():
    # Treat DB times as naive local day segments; adjust if you store tz-aware
    today = date.today()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)
    return start, end

@bp.get("/today")
@jwt_required(optional=True)
def today_view():
    """
    Returns:
      - today's remaining class meetings for the student
      - assignments due today (or next 24h)
    Priority: student_id query param; else JWT sub.
    """
    student_id = request.args.get("student_id")
    claims = get_jwt() or {}
    if not student_id:
        student_id = claims.get("sub")
        if not student_id:
            return jsonify({"classes": [], "due_assignments": []})

    _uuid_or_400(student_id, "student_id")

    # Enrolled offerings
    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    offering_ids = [e.course_offering_id for e in enrollments]
    if not offering_ids:
        return jsonify({"classes": [], "due_assignments": []})

    # Today weekday 0..6
    dow = datetime.now().weekday()

    # Remaining classes today
    now_time = datetime.now().time()
    classes = (
        ClassMeeting.query
        .filter(
            ClassMeeting.course_offering_id.in_(offering_ids),
            ClassMeeting.day_of_week == dow,
            ClassMeeting.end_time >= now_time
        )
        .order_by(ClassMeeting.start_time)
        .all()
    )

    # Assignments due today (next 24h)
    now = _now_utc()
    next24 = now + timedelta(hours=24)
    due = (
        Assignment.query
        .filter(
            Assignment.course_offering_id.in_(offering_ids),
            Assignment.due_at != None,            # noqa: E711
            Assignment.due_at >= now,
            Assignment.due_at <= next24,
        )
        .order_by(Assignment.due_at)
        .all()
    )

    # Dump as simple JSON (no schemas to keep it lightweight)
    return jsonify({
        "classes": [
            {
                "id": str(c.id),
                "course_offering_id": str(c.course_offering_id),
                "room_id": str(c.room_id) if c.room_id else None,
                "day_of_week": c.day_of_week,
                "start_time": str(c.start_time),
                "end_time": str(c.end_time),
            } for c in classes
        ],
        "due_assignments": [
            {
                "id": str(a.id),
                "course_offering_id": str(a.course_offering_id),
                "title": a.title,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "max_points": float(a.max_points) if a.max_points is not None else None,
            } for a in due
        ]
    })

@bp.get("/next")
@jwt_required(optional=True)
def next_view():
    """
    Next N days (default 7): returns upcoming classes and due assignments.
    query:
      - days (int, default 7, max 30)
      - student_id (optional if JWT present)
    """
    days = request.args.get("days", "7")
    try:
        days = max(1, min(30, int(days)))
    except Exception:
        days = 7

    student_id = request.args.get("student_id")
    claims = get_jwt() or {}
    if not student_id:
        student_id = claims.get("sub")
        if not student_id:
            return jsonify({"classes": [], "due_assignments": []})

    _uuid_or_400(student_id, "student_id")

    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    offering_ids = [e.course_offering_id for e in enrollments]
    if not offering_ids:
        return jsonify({"classes": [], "due_assignments": []})

    # Collect meetings for the next N days (by weekday match)
    today = datetime.now().date()
    upcoming_classes = []
    for d in range(days):
        day_date = today + timedelta(days=d)
        dow = day_date.weekday()
        ms = (
            ClassMeeting.query
            .filter(
                ClassMeeting.course_offering_id.in_(offering_ids),
                ClassMeeting.day_of_week == dow
            )
            .order_by(ClassMeeting.start_time)
            .all()
        )
        for m in ms:
            upcoming_classes.append({
                "id": str(m.id),
                "on_date": day_date.isoformat(),
                "course_offering_id": str(m.course_offering_id),
                "room_id": str(m.room_id) if m.room_id else None,
                "day_of_week": m.day_of_week,
                "start_time": str(m.start_time),
                "end_time": str(m.end_time),
            })

    now = _now_utc()
    horizon = now + timedelta(days=days)
    due = (
        Assignment.query
        .filter(
            Assignment.course_offering_id.in_(offering_ids),
            Assignment.due_at != None,            # noqa: E711
            Assignment.due_at >= now,
            Assignment.due_at <= horizon,
        )
        .order_by(Assignment.due_at)
        .all()
    )

    return jsonify({
        "classes": upcoming_classes,
        "due_assignments": [
            {
                "id": str(a.id),
                "course_offering_id": str(a.course_offering_id),
                "title": a.title,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "max_points": float(a.max_points) if a.max_points is not None else None,
            } for a in due
        ]
    })
