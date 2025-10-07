from flask import Blueprint, request, jsonify, abort
from flask_jwt_extended import jwt_required, get_jwt
from api.roles_guard import roles_required
from lms_models import db, Enrollment, User, CourseOffering
from schemas.core import EnrollmentSchema
from uuid import UUID

bp = Blueprint("enrollments", __name__)
schema = EnrollmentSchema()
many = EnrollmentSchema(many=True)

def _uuid_or_400(val: str, field: str) -> UUID:
    try:
        return UUID(val)
    except Exception:
        abort(400, description=f"Invalid {field}: must be UUID")

@bp.get("/")
def list_enrollments():
    q = Enrollment.query
    student_id = request.args.get("student_id")
    course_offering_id = request.args.get("course_offering_id")
    if student_id:
        _uuid_or_400(student_id, "student_id")
        q = q.filter_by(student_id=student_id)
    if course_offering_id:
        _uuid_or_400(course_offering_id, "course_offering_id")
        q = q.filter_by(course_offering_id=course_offering_id)
    return jsonify(many.dump(q.all()))

@bp.get("/mine")
@jwt_required()
def my_enrollments():
    """List enrollments for the user in the JWT (by sub)."""
    sub = get_jwt().get("sub")
    if not sub:
        return jsonify([])  # shouldn’t happen with @jwt_required
    q = Enrollment.query.filter_by(student_id=sub)
    return jsonify(many.dump(q.all()))

@bp.post("/")
@jwt_required()
def enroll():
    """
    Allow:
      - admin/staff to enroll anyone
      - students to enroll themselves (student_id must match token 'sub')
    """
    payload = request.get_json() or {}
    claims = get_jwt()
    roles = set(claims.get("roles", []))
    is_admin_or_staff = bool({"admin", "staff"} & roles)

    # student self-enroll check
    is_self = False
    if payload.get("student_id") and claims.get("sub"):
        is_self = str(payload["student_id"]) == claims["sub"]

    if not (is_admin_or_staff or is_self):
        return jsonify({"error": "not allowed"}), 403

    obj = schema.load(payload, session=db.session)  # pass session to avoid “requires a session”
    db.session.add(obj)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "could not enroll", "detail": str(e)}), 400
    return jsonify(schema.dump(obj)), 201

@bp.delete("/<uuid:enrollment_id>")
@jwt_required()
def drop(enrollment_id):
    """
    Allow:
      - admin/staff to drop any enrollment
      - students to drop their own enrollment
    """
    e = Enrollment.query.get_or_404(enrollment_id)
    claims = get_jwt()
    roles = set(claims.get("roles", []))
    is_admin_or_staff = bool({"admin", "staff"} & roles)
    is_self = str(e.student_id) == claims.get("sub")

    if not (is_admin_or_staff or is_self):
        return jsonify({"error": "not allowed"}), 403

    db.session.delete(e)
    db.session.commit()
    return jsonify({"dropped": True})

# ---------- DEMO SEEDER ----------
@bp.post("/seed_demo")
@jwt_required()
@roles_required("admin")
def seed_demo():
    """
    Creates a demo student user and enrolls them in ALL current offerings.
    Returns the student_id so you can hit /api/timetable using it.
    """
    student = User.query.filter_by(email="student@demo.school").first()
    if not student:
        student = User(
            email="student@demo.school",
            password_hash="demo",   # not used unless you implement password auth
            first_name="Demo",
            last_name="Student",
            roles=["student"],
        )
        db.session.add(student)
        db.session.commit()

    offs = CourseOffering.query.all()
    created = 0
    for o in offs:
        exists = Enrollment.query.filter_by(student_id=student.id, course_offering_id=o.id).first()
        if not exists:
            db.session.add(Enrollment(student_id=student.id, course_offering_id=o.id))
            created += 1
    db.session.commit()

    # return final enrollments list
    enrolled = Enrollment.query.filter_by(student_id=student.id).all()
    return jsonify({
        "student_id": str(student.id),
        "enrollments_created": created,
        "enrolled_offerings": [str(e.course_offering_id) for e in enrolled]
    }), 201
