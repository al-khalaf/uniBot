# api/attendance.py
from __future__ import annotations
from uuid import UUID
from datetime import date, datetime

from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import func

from api.roles_guard import roles_required
from lms_models import db, Attendance, ClassMeeting, Enrollment, Assignment, Grade
from schemas.core import AttendanceSchema

bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")

schema = AttendanceSchema()
many = AttendanceSchema(many=True)

def _uuid_or_400(v: str, field: str) -> UUID:
    try:
        return UUID(v)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

def _parse_date(s: str, field="date") -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        abort(400, description=f"{field} must be YYYY-MM-DD")

# ---------- List / Query ----------
@bp.get("/")
@jwt_required(optional=True)
def list_attendance():
    """
    Filters: student_id, meeting_id, offering_id, from (YYYY-MM-DD), to (YYYY-MM-DD)
    """
    q = Attendance.query
    student_id = request.args.get("student_id")
    meeting_id = request.args.get("meeting_id")
    offering_id = request.args.get("offering_id")
    dt_from = request.args.get("from")
    dt_to = request.args.get("to")

    if student_id:
        _uuid_or_400(student_id, "student_id")
        q = q.filter_by(student_id=student_id)

    if meeting_id:
        _uuid_or_400(meeting_id, "meeting_id")
        q = q.filter_by(meeting_id=meeting_id)

    if offering_id:
        _uuid_or_400(offering_id, "offering_id")
        # join ClassMeeting to filter by offering
        q = q.join(ClassMeeting, ClassMeeting.id == Attendance.meeting_id)\
             .filter(ClassMeeting.course_offering_id == offering_id)

    if dt_from:
        q = q.filter(Attendance.class_date >= _parse_date(dt_from, "from"))
    if dt_to:
        q = q.filter(Attendance.class_date <= _parse_date(dt_to, "to"))

    # Students can only see their own; staff/admin can see all
    claims = get_jwt() or {}
    roles = set(claims.get("roles", []))
    if not ({"admin", "staff"} & roles):
        sub = claims.get("sub")
        if not sub:
            return jsonify({"error": "unauthorized"}), 401
        q = q.filter(Attendance.student_id == sub)

    rows = q.order_by(Attendance.class_date.desc()).all()
    return jsonify(many.dump(rows))

# ---------- Create / Update ----------
@bp.post("/mark")
@jwt_required()
def mark_single():
    """
    Body: {
      "class_date":"YYYY-MM-DD",
      "meeting_id":"<uuid>",
      "student_id":"<uuid>",
      "status":"present|late|absent|excused",
      "notes":"optional"
    }
    """
    claims = get_jwt() or {}
    roles = set(claims.get("roles", []))
    is_admin_or_staff = bool({"admin", "staff"} & roles)

    # students can only mark themselves -> realistically you'd disable this,
    # but we allow self-marking to show auth pattern.
    payload = request.get_json() or {}
    if not is_admin_or_staff:
        if str(payload.get("student_id")) != claims.get("sub"):
            return jsonify({"error": "not allowed"}), 403

    obj = schema.load(payload, session=db.session)
    # sanity: ensure meeting exists
    ClassMeeting.query.get_or_404(obj.meeting_id)
    db.session.merge(obj)  # upsert by unique constraint handled in try/except
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # try manual upsert: find existing
        existing = Attendance.query.filter_by(
            class_date=obj.class_date, meeting_id=obj.meeting_id, student_id=obj.student_id
        ).first()
        if existing:
            existing.status = obj.status
            existing.notes = obj.notes
            db.session.commit()
            return jsonify(schema.dump(existing)), 200
        return jsonify({"error": "could not save", "detail": str(e)}), 400

    return jsonify(schema.dump(obj)), 201

@bp.post("/bulk_mark")
@jwt_required()
@roles_required("admin", "staff")
def bulk_mark():
    """
    Body:
    {
      "class_date":"YYYY-MM-DD",
      "meeting_id":"<uuid>",
      "records":[
        {"student_id":"<uuid>","status":"present|late|absent|excused","notes":"..."},
        ...
      ]
    }
    """
    data = request.get_json() or {}
    if "class_date" not in data or "meeting_id" not in data or "records" not in data:
        return jsonify({"error": "class_date, meeting_id and records are required"}), 400

    class_date = _parse_date(data["class_date"])
    _uuid_or_400(data["meeting_id"], "meeting_id")
    ClassMeeting.query.get_or_404(data["meeting_id"])

    payloads = []
    for r in data["records"]:
        if "student_id" not in r or "status" not in r:
            return jsonify({"error": "each record needs student_id and status"}), 400
        _uuid_or_400(r["student_id"], "student_id")
        payloads.append(Attendance(
            class_date=class_date,
            meeting_id=data["meeting_id"],
            student_id=r["student_id"],
            status=r["status"],
            notes=r.get("notes")
        ))

    # upsert logic
    for obj in payloads:
        existing = Attendance.query.filter_by(
            class_date=obj.class_date, meeting_id=obj.meeting_id, student_id=obj.student_id
        ).first()
        if existing:
            existing.status = obj.status
            existing.notes = obj.notes
        else:
            db.session.add(obj)

    db.session.commit()
    # return all for that occurrence
    rows = Attendance.query.filter_by(class_date=class_date, meeting_id=data["meeting_id"]).all()
    return jsonify(many.dump(rows))

# ---------- Stats ----------
@bp.get("/stats/course/<uuid:offering_id>")
@jwt_required()
@roles_required("admin", "staff")
def course_stats(offering_id):
    """
    Optional query: from=YYYY-MM-DD&to=YYYY-MM-DD
    Returns per-student counts + percent present (present=1, late=0.5 by default)
    """
    dt_from = request.args.get("from")
    dt_to = request.args.get("to")
    d1 = _parse_date(dt_from, "from") if dt_from else None
    d2 = _parse_date(dt_to, "to") if dt_to else None

    q = db.session.query(Attendance.student_id, Attendance.status, func.count(Attendance.id))\
                  .join(ClassMeeting, ClassMeeting.id == Attendance.meeting_id)\
                  .filter(ClassMeeting.course_offering_id == offering_id)

    if d1:
        q = q.filter(Attendance.class_date >= d1)
    if d2:
        q = q.filter(Attendance.class_date <= d2)

    q = q.group_by(Attendance.student_id, Attendance.status).all()

    # roll up
    by_student = {}
    for sid, status, n in q:
        s = by_student.setdefault(str(sid), {"present":0, "late":0, "absent":0, "excused":0})
        s[status] = s.get(status, 0) + int(n)

    # totals per student
    result = []
    for sid, counts in by_student.items():
        total = sum(counts.values())
        # weighted present%
        weighted = counts.get("present",0)*1.0 + counts.get("late",0)*0.5 + counts.get("excused",0)*1.0
        pct = (weighted / total * 100.0) if total > 0 else 0.0
        result.append({
            "student_id": sid,
            "counts": counts,
            "total_meetings": total,
            "attendance_percent": round(pct, 2)
        })

    # include enrolled with zero records
    enrolled_ids = [str(e.student_id) for e in Enrollment.query.filter_by(course_offering_id=offering_id).all()]
    have_rows = {r["student_id"] for r in result}
    for sid in enrolled_ids:
        if sid not in have_rows:
            result.append({
                "student_id": sid,
                "counts": {"present":0,"late":0,"absent":0,"excused":0},
                "total_meetings": 0,
                "attendance_percent": 0.0
            })

    result.sort(key=lambda x: (-x["attendance_percent"], x["student_id"]))
    return jsonify(result)

@bp.get("/stats/mine")
@jwt_required()
def my_stats():
    """
    Returns per-offering attendance percentage for the authenticated student.
    """
    sub = (get_jwt() or {}).get("sub")
    if not sub:
        return jsonify([])

    # get all meetings attended by me, grouped by offering
    rows = (
        db.session.query(ClassMeeting.course_offering_id,
                         Attendance.status,
                         func.count(Attendance.id))
        .join(ClassMeeting, ClassMeeting.id == Attendance.meeting_id)
        .filter(Attendance.student_id == sub)
        .group_by(ClassMeeting.course_offering_id, Attendance.status)
        .all()
    )

    roll = {}
    for oid, status, n in rows:
        r = roll.setdefault(str(oid), {"present":0,"late":0,"absent":0,"excused":0})
        r[status] = r.get(status,0) + int(n)

    out = []
    for oid, counts in roll.items():
        total = sum(counts.values())
        weighted = counts.get("present",0)*1.0 + counts.get("late",0)*0.5 + counts.get("excused",0)*1.0
        pct = (weighted / total * 100.0) if total > 0 else 0.0
        out.append({
            "course_offering_id": oid,
            "counts": counts,
            "total_meetings": total,
            "attendance_percent": round(pct, 2)
        })

    out.sort(key=lambda x: (-x["attendance_percent"], x["course_offering_id"]))
    return jsonify(out)
