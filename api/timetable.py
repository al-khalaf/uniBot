from datetime import time
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import and_
from lms_models import db, Enrollment, ClassMeeting, CourseOffering, Subject, User

bp = Blueprint("timetable", __name__)

def _resolve_student_id():
    # Allow ?student_id=... for admins/staff; students can use /me or omit and we infer from token
    q_student_id = request.args.get("student_id")
    claims = get_jwt() if "Authorization" in request.headers else {}
    roles = set(claims.get("roles", []))
    sub = claims.get("sub")

    if q_student_id:
        if roles & {"admin", "staff"} or (sub and sub == q_student_id):
            return q_student_id
        return None  # not allowed
    return sub  # default to the caller
        

def _serialize_time(t: time | None):
    return t.strftime("%H:%M") if t else None

@bp.get("/me")
@jwt_required(optional=True)
def my_timetable():
    student_id = _resolve_student_id()
    if not student_id:
        return jsonify({"error": "student_id required or login as a student"}), 400
    return _timetable_for(student_id)

@bp.get("/")
@jwt_required(optional=True)
def timetable_for_student():
    student_id = _resolve_student_id()
    if not student_id:
        return jsonify({"error": "not allowed to view this student's timetable"}), 403
    return _timetable_for(student_id)

def _timetable_for(student_id: str):
    # enrollments -> offerings -> subjects + meetings
    q = (
        db.session.query(
            ClassMeeting.id.label("meeting_id"),
            ClassMeeting.day_of_week,
            ClassMeeting.start_time,
            ClassMeeting.end_time,
            ClassMeeting.room_id,
            CourseOffering.id.label("offering_id"),
            CourseOffering.section,
            Subject.code.label("subject_code"),
            Subject.name.label("subject_name"),
        )
        .join(CourseOffering, CourseOffering.id == ClassMeeting.course_offering_id)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
        .filter(Enrollment.student_id == student_id)
        .order_by(ClassMeeting.day_of_week, ClassMeeting.start_time)
    )

    rows = q.all()

    # group by day_of_week
    days = {i: [] for i in range(7)}
    for r in rows:
        days[int(r.day_of_week)].append({
            "meeting_id": str(r.meeting_id),
            "offering_id": str(r.offering_id),
            "subject_code": r.subject_code,
            "subject_name": r.subject_name,
            "section": r.section,
            "room_id": str(r.room_id) if r.room_id else None,
            "start": _serialize_time(r.start_time),
            "end": _serialize_time(r.end_time),
        })

    out = [{"day_of_week": d, "meetings": days[d]} for d in range(7)]
    return jsonify(out)

# -------- clash detector --------

def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    # classic half-open overlap: [start, end)
    return a_start < b_end and b_start < a_end

@bp.get("/conflicts")
@jwt_required(optional=True)
def timetable_conflicts():
    student_id = _resolve_student_id()
    if not student_id:
        return jsonify({"error": "not allowed to view this student's conflicts"}), 403

    meetings = (
        db.session.query(
            ClassMeeting.id,
            ClassMeeting.day_of_week,
            ClassMeeting.start_time,
            ClassMeeting.end_time,
            CourseOffering.id.label("offering_id"),
            Subject.code.label("subject_code"),
            CourseOffering.section.label("section"),
        )
        .join(CourseOffering, CourseOffering.id == ClassMeeting.course_offering_id)
        .join(Subject, Subject.id == CourseOffering.subject_id)
        .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
        .filter(Enrollment.student_id == student_id)
        .order_by(ClassMeeting.day_of_week, ClassMeeting.start_time)
        .all()
    )

    # check pairwise per day
    conflicts = []
    by_day = {}
    for m in meetings:
        by_day.setdefault(int(m.day_of_week), []).append(m)

    for day, items in by_day.items():
        # bubble through sorted list
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if _overlaps(a.start_time, a.end_time, b.start_time, b.end_time):
                    conflicts.append({
                        "day_of_week": day,
                        "a": {
                            "meeting_id": str(a.id),
                            "subject": a.subject_code,
                            "section": a.section,
                            "start": _serialize_time(a.start_time),
                            "end": _serialize_time(a.end_time),
                        },
                        "b": {
                            "meeting_id": str(b.id),
                            "subject": b.subject_code,
                            "section": b.section,
                            "start": _serialize_time(b.start_time),
                            "end": _serialize_time(b.end_time),
                        },
                    })

    return jsonify(conflicts)

# -------- guardrails for creating meetings (optional server-side) --------

@bp.get("/can-schedule")
@jwt_required(optional=True)
def can_schedule():
    """
    Quick check before creating a meeting. Query params:
      student_id (optional, check conflicts for that student's enrolled classes),
      offering_id (required),
      day (0-6),
      start=HH:MM,
      end=HH:MM
    """
    from datetime import datetime as dt

    offering_id = request.args.get("offering_id")
    day = request.args.get("day", type=int)
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    if not (offering_id and start_str and end_str and day is not None):
        return jsonify({"error": "offering_id, day, start, end are required"}), 400

    start = dt.strptime(start_str, "%H:%M").time()
    end = dt.strptime(end_str, "%H:%M").time()

    # Check existing meetings on same day for this offering
    existing = ClassMeeting.query.filter_by(
        course_offering_id=offering_id, day_of_week=day
    ).all()
    for m in existing:
        if _overlaps(m.start_time, m.end_time, start, end):
            return jsonify({"ok": False, "reason": "offering time overlaps its own meeting"})

    # Optionally check against enrolled students' other classes (heavy but fine for now)
    student_id = request.args.get("student_id")
    if student_id:
        # find all meetings for that student on that day excluding this offering
        q = (
            db.session.query(ClassMeeting)
            .join(CourseOffering, CourseOffering.id == ClassMeeting.course_offering_id)
            .join(Enrollment, Enrollment.course_offering_id == CourseOffering.id)
            .filter(
                Enrollment.student_id == student_id,
                ClassMeeting.day_of_week == day,
                ClassMeeting.course_offering_id != offering_id,
            )
        )
        for m in q.all():
            if _overlaps(m.start_time, m.end_time, start, end):
                return jsonify({"ok": False, "reason": "student time overlaps another class"})

    return jsonify({"ok": True})
