# api/calendar.py
from __future__ import annotations
from datetime import datetime, date, time, timedelta, timezone
from uuid import UUID

from flask import Blueprint, Response, request, abort
from flask_jwt_extended import jwt_required, get_jwt

from lms_models import db, ClassMeeting, CourseOffering, Term, Enrollment, Subject, User

bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")

# Kuwait has no DST, UTC+3
KUWAIT_TZ = timezone(timedelta(hours=3))

def _uuid_or_400(v: str, field: str) -> UUID:
    try:
        return UUID(v)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

def _daterange_by_weekday(start: date, end: date, weekday: int):
    """Yield all dates between start..end matching weekday (0=Mon..6=Sun)."""
    if start.weekday() != weekday:
        start = start + timedelta(days=(weekday - start.weekday()) % 7)
    d = start
    while d <= end:
        yield d
        d += timedelta(days=7)

def _combine_local_to_utc(d: date, t: time):
    """Treat (date,time) as Asia/Kuwait local and convert to UTC aware dt."""
    local = datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=KUWAIT_TZ)
    return local.astimezone(timezone.utc)

def _ics_header(cal_name: str) -> str:
    return (
        "BEGIN:VCALENDAR\r\n"
        "PRODID:-//YourLMS//Calendar//EN\r\n"
        "VERSION:2.0\r\n"
        f"X-WR-CALNAME:{cal_name}\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
    )

def _ics_footer() -> str:
    return "END:VCALENDAR\r\n"

def _escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def _vevent(uid: str, dtstart_utc: datetime, dtend_utc: datetime, summary: str, location: str = "", description: str = "") -> str:
    # RFC5545 timestamps in UTC (Z suffix). Also include DTSTAMP now.
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = dtstart_utc.strftime("%Y%m%dT%H%M%SZ")
    dtend = dtend_utc.strftime("%Y%m%dT%H%M%SZ")
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:{_escape(summary)}\r\n"
        + (f"LOCATION:{_escape(location)}\r\n" if location else "")
        + (f"DESCRIPTION:{_escape(description)}\r\n" if description else "")
        + "END:VEVENT\r\n"
    )

def _offering_title(offering: CourseOffering, subject: Subject) -> str:
    sec = f" (Section {offering.section})" if offering.section else ""
    return f"{subject.code or 'COURSE'} - {subject.name or ''}{sec}"

def _room_label(meeting: ClassMeeting) -> str:
    # you may have Room model; if not, keep ID or blank
    return ""  # adjust later if you add Room lookups

def _term_window(offering: CourseOffering) -> tuple[date, date]:
    term = Term.query.get(offering.term_id)
    if not term or not term.start_date or not term.end_date:
        abort(400, description="Term start_date/end_date missing for this offering")
    return term.start_date, term.end_date

def _ics_response(body: str, filename: str) -> Response:
    resp = Response(body, mimetype="text/calendar; charset=utf-8")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

# ------------------------------------------------------------------------------------
# 1) Offering calendar: /api/calendar/offering/<offering_id>.ics
# ------------------------------------------------------------------------------------
@bp.get("/offering/<uuid:offering_id>.ics")
@jwt_required(optional=True)
def offering_calendar(offering_id):
    offering: CourseOffering = CourseOffering.query.get_or_404(offering_id)
    subject: Subject = Subject.query.get_or_404(offering.subject_id)

    # Anyone can download for now. Lock it down later if needed.

    start_date, end_date = _term_window(offering)
    # allow override window via ?from=YYYY-MM-DD&to=YYYY-MM-DD
    q_from = request.args.get("from")
    q_to = request.args.get("to")
    if q_from:
        start_date = max(start_date, datetime.strptime(q_from, "%Y-%m-%d").date())
    if q_to:
        end_date = min(end_date, datetime.strptime(q_to, "%Y-%m-%d").date())

    meetings = ClassMeeting.query.filter_by(course_offering_id=offering_id).all()
    title = _offering_title(offering, subject)

    ics = _ics_header(f"{title} Schedule")
    for m in meetings:
        # expand weekly into VEVENTs
        for d in _daterange_by_weekday(start_date, end_date, m.day_of_week):
            dtstart_utc = _combine_local_to_utc(d, m.start_time)
            dtend_utc = _combine_local_to_utc(d, m.end_time)
            uid = f"{m.id}-{d.isoformat()}@yourlms"
            location = _room_label(m)
            ics += _vevent(uid, dtstart_utc, dtend_utc, title, location=location)
    ics += _ics_footer()

    return _ics_response(ics, f"offering_{offering_id}.ics")

# ------------------------------------------------------------------------------------
# 2) Student calendar: /api/calendar/student/<student_id>.ics?term_id=...
#    Exports all enrolled offerings' meetings for that term
# ------------------------------------------------------------------------------------
@bp.get("/student/<uuid:student_id>.ics")
@jwt_required()
def student_calendar(student_id):
    claims = get_jwt() or {}
    roles = set(claims.get("roles", []))
    if "admin" not in roles and "staff" not in roles and str(student_id) != claims.get("sub"):
        abort(403, description="not allowed")

    term_id_s = request.args.get("term_id")
    if not term_id_s:
        abort(400, description="term_id is required")

    term_id = _uuid_or_400(term_id_s, "term_id")
    term = Term.query.get_or_404(term_id)
    if not term.start_date or not term.end_date:
        abort(400, description="term missing start_date/end_date")

    # Get the offerings the student is enrolled in for this term
    enrollments = (
        db.session.query(Enrollment)
        .join(CourseOffering, CourseOffering.id == Enrollment.course_offering_id)
        .filter(Enrollment.student_id == student_id, CourseOffering.term_id == term_id)
        .all()
    )

    # basic name
    user = User.query.get(student_id)
    cal_name = f"{user.first_name or 'Student'} {user.last_name or ''} - {term.name or 'Term'}"

    ics = _ics_header(cal_name)

    for e in enrollments:
        offering = CourseOffering.query.get(e.course_offering_id)
        subject = Subject.query.get(offering.subject_id)
        title = _offering_title(offering, subject)

        meetings = ClassMeeting.query.filter_by(course_offering_id=offering.id).all()
        for m in meetings:
            for d in _daterange_by_weekday(term.start_date, term.end_date, m.day_of_week):
                dtstart_utc = _combine_local_to_utc(d, m.start_time)
                dtend_utc = _combine_local_to_utc(d, m.end_time)
                uid = f"{m.id}-{d.isoformat()}-{student_id}@yourlms"
                location = _room_label(m)
                desc = f"{subject.code or ''} {subject.name or ''}"
                ics += _vevent(uid, dtstart_utc, dtend_utc, title, location=location, description=desc)

    ics += _ics_footer()
    return _ics_response(ics, f"student_{student_id}_{term_id}.ics")
